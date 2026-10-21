"""צופה PDF מובנה: נפתח בעמוד ובגובה השורה של התוצאה ומסמן את המילה."""

import os

from PySide6.QtCore import QModelIndex, QPointF, QTimer

from ..opener import open_pdf_external, reveal_in_folder
from .viewer_base import HitViewer

try:
    from PySide6.QtPdf import QPdfDocument, QPdfSearchModel
    from PySide6.QtPdfWidgets import QPdfView
    AVAILABLE = True
except ImportError:  # PySide6 בלי מודול ה-PDF
    AVAILABLE = False


class PdfViewer(HitViewer):
    def __init__(self, searcher, highlight, hits, index, parent=None):
        super().__init__(searcher, highlight, hits, index, parent)
        self.fit(900, 1000)
        self.add_action("－", lambda: self._zoom(1 / 1.2), "הקטנה")
        self.add_action("＋", lambda: self._zoom(1.2), "הגדלה")
        self.add_action("פתח בתוכנה החיצונית", lambda: open_pdf_external(self.path, self.hit.page, self._word(self.hit)),
                        "Acrobat / SumatraPDF נפתחים ישר בעמוד הנכון")
        self.add_action("הצג בתיקייה", lambda: reveal_in_folder(self.path))

        self.doc = QPdfDocument(self)
        self.doc.load(self.path)
        self.view = QPdfView(self)
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.layout_.addWidget(self.view, 1)

        self.search = None
        if hasattr(self.view, "setSearchModel"):
            self.search = QPdfSearchModel(self)
            self.search.setDocument(self.doc)
            self.view.setSearchModel(self.search)
            self.search.rowsInserted.connect(self._pick_result)
            self.search.modelReset.connect(self._pick_result)
        self._target = (0, 0.0)
        self.go(index)

    @staticmethod
    def _word(hit):
        words = hit.needle.split()
        return max(words, key=len) if words else ""

    def show_hit(self, hit):
        page = max(0, (hit.page or 1) - 1)
        self._target = (page, hit.y)
        self._jump()
        for ms in (80, 300):                     # שוב אחרי שהדפים נפרסו בחלון
            QTimer.singleShot(ms, self._jump)
        self.where.setFullText(self.where.fullText() + f"   ·   {os.path.basename(self.path)}")
        if self.search is not None:
            word = self._word(hit)
            if self.search.searchString() != word:
                self.search.setSearchString(word)
            # PDFium מחזיר תוצאות במנות – בוחרים שוב כשמגיעות עוד
            for ms in (0, 150, 400, 1000, 2500):
                QTimer.singleShot(ms, self._pick_result)

    def _jump(self):
        """גלילה לגובה השורה בעמוד. QPdfView במצב רב-עמודי מתעלם מהגובה שבתוך העמוד,
        לכן מחשבים את מיקום הגלילה בעצמנו: ראש העמוד + גובה השורה × קנה המידה."""
        page, y = self._target
        self.view.pageNavigator().jump(page, QPointF(0, 0), 0)
        n = self.doc.pageCount()
        if n <= 0:
            return
        heights = [self.doc.pagePointSize(i).height() for i in range(n)]
        sb = self.view.verticalScrollBar()
        m = self.view.documentMargins()
        spacing = self.view.pageSpacing()
        content = sb.maximum() + self.view.viewport().height() - m.top() - m.bottom() - spacing * (n - 1)
        scale = content / sum(heights) if sum(heights) else 1.0
        top = m.top() + sum(h * scale + spacing for h in heights[:page])
        offset = max(0.0, y - 40) * scale if y >= 0 else 0.0
        sb.setValue(int(top + offset))

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._jump)

    def _pick_result(self, *_):
        """מבין תוצאות החיפוש של PDFium – זו שבעמוד ובגובה הקרובים ביותר לתוצאה."""
        page, y = self._target
        best, best_d = None, None
        for i in range(self.search.rowCount(QModelIndex())):
            link = self.search.resultAtIndex(i)
            if link.page() != page:
                continue
            rects = link.rectangles()
            d = abs(rects[0].y() - y) if rects and y >= 0 else 0
            if best is None or d < best_d:
                best, best_d = i, d
        if best is not None and best != self.view.currentSearchResultIndex():
            self.view.setCurrentSearchResultIndex(best)
            self._jump()          # בחירת תוצאה גוללת בעצמה – מחזירים לגובה המדויק

    def _zoom(self, factor):
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(max(0.2, min(5.0, self.view.zoomFactor() * factor)))
