"""צופה PDF מובנה: נפתח בעמוד של התוצאה ומסמן את המילים שנמצאו."""

import os

from PySide6.QtCore import QModelIndex, QPointF, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from ..opener import open_default, reveal_in_folder

try:
    from PySide6.QtPdf import QPdfDocument, QPdfSearchModel
    from PySide6.QtPdfWidgets import QPdfView
    AVAILABLE = True
except ImportError:  # PySide6 בלי מודול ה-PDF
    AVAILABLE = False


class PdfViewer(QMainWindow):
    def __init__(self, path, page, needle, title, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(f"{title} – עמוד {page}")
        self.resize(900, 1000)
        self.path, self.target = path, max(0, page - 1)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(8, 8, 8, 8)
        bar = QHBoxLayout()
        self.page_label = QLabel()
        bar.addWidget(self.page_label)
        bar.addStretch(1)
        for text, slot in (("－", lambda: self._zoom(1 / 1.2)), ("＋", lambda: self._zoom(1.2)),
                           ("הצג בתיקייה", lambda: reveal_in_folder(path)),
                           ("פתח בתוכנה החיצונית", lambda: open_default(path))):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bar.addWidget(b)
        lay.addLayout(bar)

        self.doc = QPdfDocument(self)
        self.doc.load(path)
        self.view = QPdfView(self)
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        lay.addWidget(self.view, 1)
        self.setCentralWidget(central)

        nav = self.view.pageNavigator()
        nav.currentPageChanged.connect(self._page_changed)
        nav.jump(self.target, QPointF(), 0)
        self._page_changed(self.target)

        # סימון המילים (אם PDFium מצליח לזהות את הטקסט בקובץ)
        self.search = None
        if needle and hasattr(self.view, "setSearchModel"):
            self.search = QPdfSearchModel(self)
            self.search.setDocument(self.doc)
            self.view.setSearchModel(self.search)
            self.search.rowsInserted.connect(self._results_ready)
            self.search.setSearchString(needle)

    def _results_ready(self, *_):
        for i in range(self.search.rowCount(QModelIndex())):
            if self.search.resultAtIndex(i).page() == self.target:
                self.search.rowsInserted.disconnect(self._results_ready)
                self.view.setCurrentSearchResultIndex(i)
                return

    def _page_changed(self, page):
        self.page_label.setText(f"עמוד {page + 1} מתוך {self.doc.pageCount()}   ·   {os.path.basename(self.path)}")

    def _zoom(self, factor):
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(max(0.2, min(5.0, self.view.zoomFactor() * factor)))
