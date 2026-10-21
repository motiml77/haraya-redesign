"""תצוגת התוצאות.

רשימה וירטואלית (QListView + דלגייט מצייר): רק הכרטיסים שבתצוגה מצוירים, ולכן גם אלפי תוצאות
נגללות בחלקות. תוצאות נטענות בעמודים של 30 – העמוד הבא מוכן ברקע בזמן שגוללים, בלי להקפיא
את החלון. הגלילה: אנימציה חלקה לגלגלת, פס גלילה רחב וברור, כפתור "לראש הרשימה", ומקשי
Home / End / PageUp / PageDown / חצים.
"""

from __future__ import annotations

import os
from collections import OrderedDict

from PySide6.QtCore import (
    QAbstractListModel, QEasingCurve, QEvent, QModelIndex, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer,
    Signal, Slot,
)
from PySide6.QtGui import (
    QBrush, QColor, QFontMetrics, QGuiApplication, QIcon, QPainter, QPen, QTextBlockFormat, QTextCharFormat,
    QTextCursor, QTextDocument, QTextOption,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QLabel, QListView, QMenu, QStackedLayout, QStyle, QStyledItemDelegate,
    QTextBrowser, QToolButton, QToolTip, QVBoxLayout, QWidget,
)

from ..normalize import restore_finals
from ..search import SEG_GAP, SEG_MATCH, SEG_PARA
from .icons import file_icon, ui_icon
from .theme import C, T, ui_font
from .widgets import BusyOverlay, SmoothScroller
from .workers import PAGE, SnippetJob

ROW = Qt.UserRole + 1


def ltr(s: str) -> str:
    """עוטף טקסט משמאל-לימין (נתיבים, יחידות) כדי שלא יתבלגן בתוך עברית."""
    return f"‪{s}‬"


def doc_name(path: str) -> str:
    """שם המסמך בלי סיומת – הסיומת הלטינית משבשת את כיווניות השם."""
    return os.path.splitext(os.path.basename(path))[0]


def short_path(path: str, limit=40) -> str:
    """מקצר נתיב ארוך לתיקיות האחרונות שבו: …\\מסמכים\\תורה"""
    if len(path) <= limit:
        return path
    parts = path.replace("\\", "/").rstrip("/").split("/")
    sep = "\\" if "\\" in path else "/"
    tail = parts[-1]
    for part in reversed(parts[:-1]):
        if len(tail) + len(part) + 1 > limit:
            break
        tail = part + sep + tail
    return "…" + sep + tail


def form_of(word):
    return restore_finals(word)


# ---------------------------------------------------------------- מודל
class HitModel(QAbstractListModel):
    """שורות: ("hit", Hit, מספר) או ("hdr", מזהה_קובץ, נתיב, כמות) – כותרת מסמך במיון לפי מסמך."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.all_hits = []
        self.pos = 0
        self.grouped = False
        self.counts = {}
        self._last_fid = None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.DisplayRole):
        return None

    def flags(self, index):
        if index.isValid() and self.rows[index.row()][0] == "hit":
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return Qt.ItemIsEnabled

    def reset(self, hits, grouped, counts):
        self.beginResetModel()
        self.rows, self.all_hits, self.pos = [], hits, 0
        self.grouped, self.counts, self._last_fid = grouped, counts, None
        self.endResetModel()

    def has_more(self) -> bool:
        return self.pos < len(self.all_hits)

    def next_batch(self, n=PAGE):
        return self.all_hits[self.pos:self.pos + n]

    def append(self, batch):
        rows = []
        for i, h in enumerate(batch):
            if self.grouped and h.file_id != self._last_fid:
                rows.append(("hdr", h.file_id, h.path, self.counts.get(h.file_id, 0)))
                self._last_fid = h.file_id
            rows.append(("hit", h, self.pos + i + 1))
        if rows:
            first = len(self.rows)
            self.beginInsertRows(QModelIndex(), first, first + len(rows) - 1)
            self.rows.extend(rows)
            self.endInsertRows()
        self.pos += len(batch)


# ---------------------------------------------------------------- דלגייט (ציור הכרטיסים)
class HitDelegate(QStyledItemDelegate):
    MX, MY = 8, 3                 # שוליים חיצוניים סביב כרטיס

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.docs = OrderedDict()   # id(hit) -> (רוחב, מסמך)
        self.rects = {}             # שורה -> {שם: מלבן יחסי לשורה}
        self.hover_row, self.hover_act = -1, None
        self.retheme()

    def retheme(self):
        self.f_meta = ui_font(T.caption)
        self.f_name = ui_font(T.body, 600)
        self.f_hdr = ui_font(T.title, 600)
        self.f_snip = ui_font(T.snippet)
        self.fm_meta = QFontMetrics(self.f_meta)
        self.fm_name = QFontMetrics(self.f_name)
        self.fm_hdr = QFontMetrics(self.f_hdr)
        self.pad = T.pad + 2
        self.meta_h = max(self.fm_name.height(), 20)
        self.act = T.h_ctl - 6        # צלע כפתור פעולה קטן
        self.docs.clear()
        self.rects.clear()

    # ----- מסמך הקטע -----
    def _doc(self, hit, width):
        hit_id = id(hit)
        cached = self.docs.get(hit_id)
        if cached and cached[0] == width and cached[2] is hit:
            self.docs.move_to_end(hit_id)
            return cached[1]
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(self.f_snip)
        opt = QTextOption()
        opt.setTextDirection(Qt.RightToLeft)
        opt.setAlignment(Qt.AlignLeft)             # מתחילת הפסקה: בעברית – מימין
        opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        doc.setDefaultTextOption(opt)
        cur = QTextCursor(doc)
        bf = QTextBlockFormat()
        bf.setLineHeight(150.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        bf.setLayoutDirection(Qt.RightToLeft)
        cur.setBlockFormat(bf)
        normal = QTextCharFormat()
        normal.setForeground(QColor(C.text))
        match = QTextCharFormat()
        match.setBackground(QBrush(QColor(C.marker)))
        match.setForeground(QColor(C.marker_text))
        gap = QTextCharFormat()
        gap.setForeground(QColor(C.muted))
        para = QTextCharFormat()
        para.setForeground(QColor("#b4bcc9"))
        for text, kind in hit.snippet:
            text = text.replace("\n", " ").replace("\t", " ")
            if kind == SEG_MATCH:
                cur.insertText(text, match)
            elif kind == SEG_GAP:
                cur.insertText(text, gap)
            elif kind == SEG_PARA:
                cur.insertText(" ¶ ", para)
            else:
                cur.insertText(text, normal)
        doc.setTextWidth(width)
        self.docs[hit_id] = (width, doc, hit)
        while len(self.docs) > 500:
            self.docs.popitem(last=False)
        return doc

    def _row(self, index):
        return index.model().rows[index.row()]

    # ----- גודל -----
    def sizeHint(self, option, index):
        row = self._row(index)
        w = max(200, self.view.viewport().width())
        if row[0] == "hdr":
            return QSize(w, self.hdr_height())
        hit = row[1]
        doc_w = w - 2 * self.MX - 2 * self.pad
        doc = self._doc(hit, doc_w)
        h = 2 * self.MY + self.pad + self.meta_h + 6 + int(doc.size().height() + 0.99) + self.pad
        return QSize(w, h)

    def hdr_height(self) -> int:
        return 12 + max(self.fm_hdr.height(), 20) + self.fm_meta.height() + 10

    # ----- ציור -----
    def paint(self, painter, option, index):
        row = self._row(index)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setLayoutDirection(Qt.RightToLeft)
        try:
            if row[0] == "hdr":
                self._paint_header(painter, option, index, row)
            else:
                self._paint_hit(painter, option, index, row)
        finally:
            painter.restore()

    def _paint_hit(self, painter, option, index, row):
        _, hit, number = row
        rect = option.rect
        card = rect.adjusted(self.MX, self.MY, -self.MX, -self.MY)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = index.row() == self.hover_row
        bg = C.accent_soft if selected else ("#fbfcfe" if hovered else C.surface)
        border = C.accent if selected else (C.border_strong if hovered else C.border)
        painter.setPen(QPen(QColor(border), 1.5 if selected else 1.0))
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(QRectF(card).adjusted(0.5, 0.5, -0.5, -0.5), T.radius_lg, T.radius_lg)

        pad, gap = self.pad, 6
        top = card.top() + pad
        mid_y = top + self.meta_h / 2
        rel = {}
        num = str(number)
        nw = self.fm_meta.horizontalAdvance(num)
        # ----- שמאל: פעולות, תגיות, מד התאמה (בכרטיס צר מוותרים קודם על התגיות ואז על המד) -----
        meter_w = 5 * 9
        actions_w = 2 * (self.act + 2) + gap
        budget = card.width() - 2 * pad - (nw + gap + T.icon + gap) - 3 * T.pad * 4 - actions_w
        badges = []
        if hit.exact:
            badges.append(("התאמה מדויקת", C.ok, C.ok_bg))
        total_terms = getattr(self.view, "n_terms", 0)
        if total_terms > 1 and hit.covered < total_terms:
            badges.append((f"{hit.covered} מתוך {total_terms} מילים", C.warn, C.warn_bg))
        shown = []
        for text, fg, bgc in badges:
            w = self.fm_meta.horizontalAdvance(text) + 12
            if budget - (w + 6) >= meter_w:
                shown.append((text, fg, bgc, w))
                budget -= w + 6
        show_meter = budget >= meter_w
        x = card.left() + pad
        for name, icon_name in (("folder", "folder"), ("preview", "eye")):
            r = QRect(x, int(mid_y - self.act / 2), self.act, self.act)
            active = self.hover_row == index.row() and self.hover_act == name
            if active:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(C.accent_sel))
                painter.drawRoundedRect(r, 4, 4)
            pm = ui_icon(icon_name).pixmap(QSize(T.icon, T.icon), QIcon.Active if active else QIcon.Normal)
            painter.drawPixmap(r.center().x() - T.icon // 2, r.center().y() - T.icon // 2, pm)
            rel[name] = r.translated(-rect.topLeft())
            x += self.act + 2
        x += gap
        painter.setFont(self.f_meta)
        for text, fg, bgc, w in shown:
            r = QRect(x, int(mid_y - (self.fm_meta.height() + 4) / 2), w, self.fm_meta.height() + 4)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(bgc))
            painter.drawRoundedRect(r, r.height() / 2, r.height() / 2)
            painter.setPen(QColor(fg))
            painter.drawText(r, Qt.AlignCenter, text)
            x += w + 6
        if show_meter:                     # מד התאמה: 5 נקודות
            lit = max(1, min(5, round(hit.score * 5)))
            for i in range(5):
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#22a559" if i < lit else "#d5dae3"))
                painter.drawEllipse(QRectF(x + i * 9, mid_y - 3, 6, 6))
            x += meter_w
        left_end = x + gap

        # ----- ימין: מספר, סמל, שם המסמך, מיקום -----
        xr = card.right() - pad
        painter.setFont(self.f_meta)
        painter.setPen(QColor("#a3acbb"))
        painter.drawText(QRectF(xr - nw, top, nw, self.meta_h), Qt.AlignRight | Qt.AlignVCenter, num)
        xr -= nw + gap
        ic = file_icon(hit.path)
        pm = ic.pixmap(QSize(T.icon, T.icon))
        painter.drawPixmap(xr - T.icon, int(mid_y - T.icon / 2), pm)
        xr -= T.icon + gap
        avail = xr - left_end
        loc = hit.location
        loc_w = min(self.fm_meta.horizontalAdvance(loc) + 3, max(60, avail // 2))
        loc_txt = self.fm_meta.elidedText(loc, Qt.ElideRight, loc_w)
        name = doc_name(hit.path)
        sep_w = 12
        name_w = max(40, avail - loc_w - sep_w)
        painter.setFont(self.f_name)
        painter.setPen(QColor("#1e3a8a"))
        name_txt = self.fm_name.elidedText(name, Qt.ElideRight, name_w)
        nw2 = min(name_w, self.fm_name.horizontalAdvance(name_txt))
        painter.drawText(QRectF(xr - nw2, top, nw2 + 1, self.meta_h), Qt.AlignRight | Qt.AlignVCenter, name_txt)
        xr -= nw2
        painter.setFont(self.f_meta)
        painter.setPen(QColor("#a3acbb"))
        painter.drawText(QRectF(xr - sep_w, top, sep_w, self.meta_h), Qt.AlignCenter, "·")
        xr -= sep_w
        painter.setPen(QColor(C.accent))
        painter.drawText(QRectF(xr - loc_w, top, loc_w, self.meta_h), Qt.AlignRight | Qt.AlignVCenter, loc_txt)

        # ----- הקטע -----
        doc_w = card.width() - 2 * pad
        doc = self._doc(hit, doc_w)
        painter.translate(card.left() + pad, top + self.meta_h + 6)
        doc.drawContents(painter, QRectF(0, 0, doc_w, doc.size().height() + 2))
        self.rects[index.row()] = rel

    def _paint_header(self, painter, option, index, row):
        _, fid, path, count = row
        rect = option.rect
        hovered = index.row() == self.hover_row
        x_right = rect.right() - self.MX - 4
        top = rect.top() + 12
        # סמל + שם
        isz = T.icon + 4
        painter.drawPixmap(x_right - isz, top, file_icon(path).pixmap(QSize(isz, isz)))
        x = x_right - isz - 8
        name = doc_name(path)
        word = "תוצאה" if count == 1 else "תוצאות"
        count_txt = f"{count:,} {word}"
        painter.setFont(self.f_meta)
        cw = self.fm_meta.horizontalAdvance(count_txt) + 14
        # פעולות בשמאל
        rel = {}
        acts = (("open_dir", "הצג בתיקייה"), ("open_file", "פתח מסמך"))
        xl = rect.left() + self.MX + 4
        painter.setFont(self.f_meta)
        for name_key, label in acts:
            w = self.fm_meta.horizontalAdvance(label) + 14
            r = QRect(xl, top, w, 22)
            active = hovered and self.hover_act == name_key
            if active:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(C.accent_sel))
                painter.drawRoundedRect(r, 4, 4)
            painter.setPen(QColor(C.accent))
            painter.drawText(r, Qt.AlignCenter, label)
            rel[name_key] = r.translated(-rect.topLeft())
            xl += w + 2
        avail = x - xl - cw - 8
        painter.setFont(self.f_hdr)
        nm = self.fm_hdr.elidedText(name, Qt.ElideRight, max(60, avail))
        nw = min(max(60, avail), self.fm_hdr.horizontalAdvance(nm))
        painter.setPen(QColor("#1e3a8a"))
        painter.drawText(QRectF(x - nw, top - 1, nw + 1, 24), Qt.AlignRight | Qt.AlignVCenter, nm)
        x -= nw + 8
        # כמות
        painter.setFont(self.f_meta)
        r = QRect(x - cw, top + 2, cw, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(C.accent_soft))
        painter.drawRoundedRect(r, 9, 9)
        painter.setPen(QColor(C.accent))
        painter.drawText(r, Qt.AlignCenter, count_txt)
        # נתיב התיקייה
        folder = os.path.dirname(path)
        painter.setPen(QColor(C.muted))
        painter.setFont(self.f_meta)
        pw = rect.width() - 2 * self.MX - 8
        pt = self.fm_meta.elidedText(ltr(folder), Qt.ElideMiddle, pw)
        painter.drawText(QRectF(rect.left() + self.MX + 4, top + 26, pw, self.fm_meta.height() + 2),
                         Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter, pt)
        self.rects[index.row()] = rel

    # ----- ניתוב לחיצות ורמזים -----
    def action_at(self, index, pos):
        """איזו פעולה נמצאת תחת העכבר: 'preview' / 'folder' / 'open_file' / 'open_dir' / 'card' / None."""
        if not index.isValid():
            return None
        row = self._row(index)
        rect = self.view.visualRect(index)
        rel = self.rects.get(index.row(), {})
        for name, r in rel.items():
            if r.translated(rect.topLeft()).contains(pos):
                return name
        return "card" if row[0] == "hit" else None

    def helpEvent(self, event, view, option, index):
        if event.type() == QEvent.ToolTip and index.isValid():
            act = self.action_at(index, event.pos())
            row = self._row(index)
            tips = {"preview": "תצוגה מובנית של המסמך", "folder": "הצג את הקובץ בתיקייה",
                    "open_file": "פתח את המסמך", "open_dir": "הצג בתיקייה"}
            text = tips.get(act) or (ltr(row[1].path) if row[0] == "hit" else "")
            if text:
                QToolTip.showText(event.globalPos(), text, view)
                return True
        return super().helpEvent(event, view, option, index)


# ---------------------------------------------------------------- הרשימה
class ResultsList(QListView):
    hitClicked = Signal(object)
    hitPreview = Signal(object)
    fileClicked = Signal(str)
    folderClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("results")
        self.n_terms = 0
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(28)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setUniformItemSizes(False)
        self.setResizeMode(QListView.Adjust)
        self.setSpacing(0)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.model_ = HitModel(self)
        self.setModel(self.model_)
        self.delegate = HitDelegate(self)
        self.setItemDelegate(self.delegate)
        self._press = None
        self._relayout_pending = False
        SmoothScroller(self)
        self.activated.connect(self._on_activated)
        self.customContextMenuRequested.connect(self._context)
        # כפתור "לראש הרשימה"
        self.fab = QToolButton(self.viewport())
        self.fab.setObjectName("fab")
        self.fab.setIcon(ui_icon("arrow-up"))
        self.fab.setToolTip("לראש הרשימה (Home)")
        self.fab.setCursor(Qt.PointingHandCursor)
        self.fab.clicked.connect(self.scroll_top)
        self.fab.hide()
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def retheme(self):
        self.delegate.retheme()
        self.fab.setIconSize(QSize(T.icon, T.icon))
        self.fab.setFixedSize(T.h_ctl + 4, T.h_ctl + 4)
        self.doItemsLayout()
        self.viewport().update()

    # ----- גלילה -----
    def scroll_top(self):
        bar = self.verticalScrollBar()
        anim = QPropertyAnimation(bar, b"value", self)
        anim.setDuration(260)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(bar.value())
        anim.setEndValue(0)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def _on_scroll(self, value):
        self.fab.setVisible(value > self.viewport().height())
        self._place_fab()

    def _place_fab(self):
        m = 14
        self.fab.move(m, self.viewport().height() - self.fab.height() - m)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_fab()
        # גובה כרטיס תלוי ברוחב (שבירת שורות), ו-Qt לא מחשב מחדש בשינוי רוחב ברשימה רגילה – מחשבים בעצמנו
        if e.size().width() != e.oldSize().width() and not self._relayout_pending:
            self._relayout_pending = True
            QTimer.singleShot(0, self._relayout)

    def _relayout(self):
        self._relayout_pending = False
        self.doItemsLayout()

    # ----- עכבר -----
    def mousePressEvent(self, e):
        self._press = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if e.button() != Qt.LeftButton or self._press is None:
            return
        pos = e.position().toPoint()
        moved = (pos - self._press).manhattanLength() > 6
        self._press = None
        if moved:
            return
        idx = self.indexAt(pos)
        act = self.delegate.action_at(idx, pos)
        if act is None:
            return
        row = self.model_.rows[idx.row()]
        if row[0] == "hdr":
            (self.fileClicked if act == "open_file" else self.folderClicked).emit(row[2])
            return
        hit = row[1]
        if act == "preview":
            self.hitPreview.emit(hit)
        elif act == "folder":
            self.folderClicked.emit(hit.path)
        else:
            self.hitClicked.emit(hit)

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        idx = self.indexAt(pos)
        act = self.delegate.action_at(idx, pos) if idx.isValid() else None
        row = idx.row() if idx.isValid() else -1
        d = self.delegate
        if row != d.hover_row or act != d.hover_act:
            old = d.hover_row
            d.hover_row, d.hover_act = row, act
            for r in (old, row):
                if r >= 0:
                    self.viewport().update(self.visualRect(self.model_.index(r, 0)))
        self.viewport().setCursor(Qt.PointingHandCursor if act else Qt.ArrowCursor)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        d = self.delegate
        old, d.hover_row, d.hover_act = d.hover_row, -1, None
        if old >= 0 and old < self.model_.rowCount():
            self.viewport().update(self.visualRect(self.model_.index(old, 0)))
        super().leaveEvent(e)

    def _on_activated(self, index):
        row = self.model_.rows[index.row()]
        if row[0] == "hit":
            self.hitClicked.emit(row[1])

    def _context(self, pos):
        idx = self.indexAt(pos)
        if not idx.isValid():
            return
        row = self.model_.rows[idx.row()]
        path = row[1].path if row[0] == "hit" else row[2]
        menu = QMenu(self)
        if row[0] == "hit":
            hit = row[1]
            menu.addAction(ui_icon("external"), "פתח במקום המדויק", lambda: self.hitClicked.emit(hit))
            menu.addAction(ui_icon("eye"), "תצוגה מובנית של המסמך", lambda: self.hitPreview.emit(hit))
        else:
            menu.addAction(ui_icon("external"), "פתח את המסמך", lambda: self.fileClicked.emit(path))
        menu.addAction(ui_icon("folder"), "הצג בתיקייה", lambda: self.folderClicked.emit(path))
        menu.addSeparator()
        if row[0] == "hit":
            text = "".join(t for t, _ in row[1].snippet).replace("\n", " ")
            menu.addAction(ui_icon("copy"), "העתק את הקטע", lambda: QGuiApplication.clipboard().setText(text))
        menu.addAction(ui_icon("copy"), "העתק את הנתיב", lambda: QGuiApplication.clipboard().setText(path))
        menu.exec(self.viewport().mapToGlobal(pos))


# ---------------------------------------------------------------- הודעות (פתיחה / אין תוצאות)
def _css() -> str:
    return (f"body {{ color:{C.text}; font-size:{T.body}px; }} a {{ color:{C.accent}; text-decoration:none; }} "
            f"td {{ padding: 3px 0; }} code {{ background:{C.surface_alt}; }}")


def _wrap(body: str) -> str:
    return f'<html><head><style>{_css()}</style></head><body dir="rtl">{body}</body></html>'


def syntax_table() -> str:
    rows = (("הלכ*", "כוכבית – כל רצף אותיות (הלכה, הלכות, הלכתא…)"), ("מש?", "סימן שאלה – אות אחת כלשהי (משה, משל…)"),
            ("משה|אהרן", "קו אנכי – אחת מהמילים"), ("שבת -חול", "מינוס – פסקאות עם 'שבת' שאין בהן 'חול'"))
    out = "".join(f'<tr><td align="right" style="color:{C.muted}">{d}</td>'
                  f'<td align="right"><b>&nbsp;&nbsp;{w}</b></td></tr>' for w, d in rows)
    return f'<table align="right" cellpadding="2">{out}</table>'


def welcome_html() -> str:
    steps = (("צרו סלים", "לכל סל שם משלו (שיעורים, תורה…) ובו תיקיות ומסמכי Word או PDF. אפשר גם לגרור לכאן מהסייר."),
             ("המפה נבנית לבד", "בפעם הראשונה כל מסמך נקרא פעם אחת; אחר כך רק מסמכים שהשתנו."),
             ("חפשו", "הניקוד והסימנים לא משנים. התוצאות הכי מדויקות ראשונות, ולחיצה על תוצאה פותחת את המסמך במקום."))
    rows = "".join(
        f'<tr><td align="right" valign="top"><b>{t}</b> – <span style="color:{C.text2}">{d}</span></td>'
        f'<td width="28" align="center" valign="top" style="color:{C.accent}; font-weight:600">{i}</td></tr>'
        for i, (t, d) in enumerate(steps, 1))
    return _wrap(
        f'<p style="margin-top:18px"><span style="font-size:{T.hero}px; font-weight:600; color:{C.accent}">'
        f'חיפוש במסמכים</span><br><span style="color:{C.muted}">חיפוש מהיר וגמיש בתוך מסמכי Word ו-PDF בעברית</span></p>'
        f'<table align="right" cellpadding="3" width="100%">{rows}</table>'
        f'<p style="margin-top:14px; margin-bottom:2px"><b>חיפוש מתקדם</b></p>{syntax_table()}')


def message_html(text: str, hint: str = "", color: str = C.text2) -> str:
    hint_html = f'<br><span style="color:{C.muted}; font-size:{T.caption}px">{hint}</span>' if hint else ""
    return _wrap(f'<p align="center" style="margin-top:36px; font-size:{T.title}px; color:{color}">{text}{hint_html}</p>')


# ---------------------------------------------------------------- המכל
class ResultsView(QWidget):
    """רשימת התוצאות + הודעות + שכבת התקדמות + שורת מצב."""
    hitClicked = Signal(object)
    hitPreview = Signal(object)
    fileClicked = Signal(str)
    folderClicked = Signal(str)
    linkActivated = Signal(str)
    cancelRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db_path = None
        self._highlight = frozenset()
        self._context = 20
        self._gen = 0
        self._loading = False
        self._jobs = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        host = QWidget()
        self.stack = QStackedLayout(host)
        self.text = QTextBrowser()
        self.text.setOpenLinks(False)
        self.text.setFrameShape(QFrame.NoFrame)
        self.text.anchorClicked.connect(lambda u: self.linkActivated.emit(u.toString()))
        self.text.document().setDocumentMargin(T.pad * 2)
        self.list = ResultsList()
        self.list.hitClicked.connect(self.hitClicked)
        self.list.hitPreview.connect(self.hitPreview)
        self.list.fileClicked.connect(self.fileClicked)
        self.list.folderClicked.connect(self.folderClicked)
        self.list.verticalScrollBar().valueChanged.connect(self._maybe_more)
        self.stack.addWidget(self.text)
        self.stack.addWidget(self.list)
        lay.addWidget(host, 1)
        self.footer = QLabel("")
        self.footer.setObjectName("caption")
        self.footer.setAlignment(Qt.AlignCenter)
        self.footer.setContentsMargins(0, 3, 0, 4)
        lay.addWidget(self.footer)
        self.footer.hide()
        self.overlay = BusyOverlay(host)
        self.overlay.cancelRequested.connect(self.cancelRequested)
        self.show_welcome()

    # ----- הגדרות -----
    def configure(self, db_path, context_words=20):
        self._db_path = db_path
        self._context = context_words

    def retheme(self):
        self.list.retheme()
        self.text.document().setDocumentMargin(T.pad * 2)

    # ----- הודעות -----
    def show_welcome(self):
        self._gen += 1
        self.list.model_.reset([], False, {})
        self.text.setHtml(welcome_html())
        self.stack.setCurrentWidget(self.text)
        self.footer.hide()

    def show_message(self, html: str):
        self._gen += 1
        self.list.model_.reset([], False, {})
        self.text.setHtml(html)
        self.stack.setCurrentWidget(self.text)
        self.footer.hide()

    # ----- תוצאות -----
    def show_hits(self, result, hits, grouped):
        """hits: הרשימה (אחרי סינון); grouped: כותרות מסמך. העמוד הראשון נטען מיד, השאר בגלילה."""
        self._gen += 1
        self._loading = False
        self._highlight = result.highlight
        self.list.n_terms = result.n_terms
        counts = {}
        for h in hits:
            counts[h.file_id] = counts.get(h.file_id, 0) + 1
        self.list.model_.reset(hits, grouped, counts)
        self.stack.setCurrentWidget(self.list)
        self.list.verticalScrollBar().setValue(0)
        self.list.fab.hide()
        self._request_more()

    def _request_more(self):
        model = self.list.model_
        if self._loading or not model.has_more():
            self._update_footer()
            return
        batch = model.next_batch(PAGE)
        if all(h.ready for h in batch):
            model.append(batch)
            self._after_append()
            return
        self._loading = True
        job = SnippetJob(self._db_path, batch, self._highlight, self._context, tag=self._gen)
        self._jobs.append(job)
        job.signals.finished.connect(self._on_snippets)
        job.start()
        self._update_footer()

    @Slot(object)
    def _on_snippets(self, outcome):
        self._jobs = [j for j in self._jobs if not j.is_done]
        if outcome.tag != self._gen:
            return                                   # תוצאה ישנה (חיפוש/סינון חדש התחיל בינתיים)
        self._loading = False
        if outcome.error or not outcome.result:
            return
        self.list.model_.append(outcome.result)
        self._after_append()

    def _after_append(self):
        self._update_footer()
        QTimer.singleShot(0, self._maybe_more)

    def _maybe_more(self, *_):
        model = self.list.model_
        if self._loading or not model.has_more():
            return
        bar = self.list.verticalScrollBar()
        if bar.maximum() - bar.value() < self.list.viewport().height() * 1.5:
            self._request_more()

    def _update_footer(self):
        model = self.list.model_
        total = len(model.all_hits)
        if total <= PAGE or self.stack.currentWidget() is not self.list:
            self.footer.hide()
            return
        loaded = model.pos
        if loaded >= total:
            self.footer.setText(f"הוצגו כל {total:,} התוצאות")
        else:
            self.footer.setText(f"נטענו {loaded:,} מתוך {total:,} תוצאות · המשיכו לגלול לטעינת עוד")
        self.footer.show()

    # ----- שכבת התקדמות -----
    def busy_begin(self, title="מחפש…"):
        self.overlay.begin(title)

    def busy_progress(self, frac, text=""):
        title, _, detail = text.partition("\n")
        self.overlay.set_progress(frac, title or None, detail)

    def busy_end(self):
        self.overlay.end()
