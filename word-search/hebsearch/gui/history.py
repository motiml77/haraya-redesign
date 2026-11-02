"""היסטוריית חיפוש, כמו בדפדפן ובתוכנות עבודה:

  * לחיצה על שדה חיפוש ריק, חץ למטה, או סמל השעון שבשדה – פותחים את החיפושים האחרונים.
  * הקלדה מסננת לפי כל חלק של השאילתה (לא רק לפי ההתחלה).
  * לכל חיפוש: מתי חיפשו ובכמה תוצאות; ✕ (או Delete) מוחק אותו, ובסוף "ניקוי ההיסטוריה".
  * בחירה בחיפוש מריצה אותו מיד.
"""

from __future__ import annotations

import json
import time

from PySide6.QtCore import QEvent, QModelIndex, QObject, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QCompleter, QStyle, QStyledItemDelegate

from .icons import ui_icon
from .theme import C, T, ui_font

KEY = "history2"
LIMIT = 100
ROLE_META = Qt.UserRole + 1
ROLE_KIND = Qt.UserRole + 2           # "item" או "clear"
ROLE_MATCH = Qt.UserRole + 3          # הטקסט שלפיו מסננים
CLEAR_TEXT = "ניקוי ההיסטוריה"


def when_text(ts: float, now: float | None = None) -> str:
    """"היום 14:32", "אתמול", "לפני 3 ימים", או תאריך."""
    now = now or time.time()
    t, n = time.localtime(ts), time.localtime(now)
    days = (time.mktime((n.tm_year, n.tm_mon, n.tm_mday, 0, 0, 0, 0, 0, -1))
            - time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))) / 86400
    days = int(round(days))
    if days <= 0:
        return time.strftime("היום %H:%M", t)
    if days == 1:
        return "אתמול"
    if days < 7:
        return f"לפני {days} ימים"
    return f"{t.tm_mday}.{t.tm_mon}.{t.tm_year % 100:02d}"


def count_text(n) -> str:
    if n is None:
        return ""
    if n == 0:
        return "אין תוצאות"
    return "תוצאה אחת" if n == 1 else f"{n:,} תוצאות"


class SearchHistory(QObject):
    """רשימת החיפושים (החדש ראשון), שמורה בהגדרות. [{q, t, n}]"""
    changed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.items = []
        raw = settings.value(KEY, "")
        try:
            self.items = [i for i in json.loads(raw) if isinstance(i, dict) and i.get("q")] if raw else []
        except (TypeError, ValueError):
            self.items = []
        if not self.items:                                   # רשימה ישנה של מחרוזות בלבד
            old = settings.value("history", [], list) or []
            self.items = [{"q": q, "t": 0, "n": None} for q in old if isinstance(q, str) and q.strip()]

    def queries(self):
        return [i["q"] for i in self.items]

    def add(self, query: str):
        query = query.strip()
        if not query:
            return
        self.items = [i for i in self.items if i["q"] != query]
        self.items.insert(0, {"q": query, "t": time.time(), "n": None})
        del self.items[LIMIT:]
        self._save()

    def set_count(self, query: str, n: int):
        for i in self.items:
            if i["q"] == query.strip():
                i["n"] = int(n)
                self._save()
                return

    def remove(self, query: str):
        self.items = [i for i in self.items if i["q"] != query]
        self._save()

    def clear(self):
        self.items = []
        self._save()

    def _save(self):
        self.settings.setValue(KEY, json.dumps(self.items, ensure_ascii=False))
        self.settings.remove("history")
        self.changed.emit()


class HistoryDelegate(QStyledItemDelegate):
    """שורה: שעון · השאילתה ············ מתי · כמה תוצאות  ✕ (ה-✕ במעבר עכבר)."""
    removeRequested = Signal(str)

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), T.h_ctl + 6)

    def _x_rect(self, rect: QRect) -> QRect:
        s = T.h_ctl - 8
        return QRect(rect.left() + 6, rect.center().y() - s // 2, s, s)

    def paint(self, p, option, index):
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing)
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)
        if selected or hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C.accent_soft if selected else C.hover))
            p.drawRoundedRect(r.adjusted(2, 1, -2, -1), T.radius, T.radius)
        kind = index.data(ROLE_KIND)
        isz = T.icon
        x = r.right() - 10
        if kind == "clear":
            pm = ui_icon("trash", C.danger).pixmap(QSize(isz, isz))
            p.drawPixmap(x - isz, r.center().y() - isz // 2, pm)
            p.setFont(ui_font(T.body))
            p.setPen(QColor(C.danger))
            p.drawText(QRect(r.left() + 8, r.top(), x - isz - 8 - r.left() - 8, r.height()),
                       Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter, CLEAR_TEXT)
            p.restore()
            return
        pm = ui_icon("clock", C.muted).pixmap(QSize(isz, isz))
        p.drawPixmap(x - isz, r.center().y() - isz // 2, pm)
        x -= isz + 8
        meta = index.data(ROLE_META) or ""
        fm_meta = QFontMetrics(ui_font(T.caption))
        left = r.left() + 10 + ((T.h_ctl - 8 + 6) if (hover or selected) else 0)
        meta_w = min(fm_meta.horizontalAdvance(meta) + 8, max(0, (x - left) // 2)) if meta else 0
        if meta:
            p.setFont(ui_font(T.caption))
            p.setPen(QColor(C.muted))
            p.drawText(QRect(left, r.top(), meta_w, r.height()), Qt.AlignAbsolute | Qt.AlignLeft | Qt.AlignVCenter,
                       fm_meta.elidedText(meta, Qt.ElideRight, meta_w))
        q = index.data(Qt.DisplayRole) or ""
        f = ui_font(T.body, 600 if selected else None)
        p.setFont(f)
        p.setPen(QColor(C.text))
        qw = x - (left + meta_w + 12)
        p.drawText(QRect(left + meta_w + 12, r.top(), qw, r.height()), Qt.AlignAbsolute | Qt.AlignRight | Qt.AlignVCenter,
                   QFontMetrics(f).elidedText(q, Qt.ElideLeft, qw))
        if hover or selected:
            xr = self._x_rect(r)
            pm = ui_icon("x", C.muted, C.danger).pixmap(QSize(isz - 2, isz - 2))
            p.drawPixmap(xr.center().x() - (isz - 2) // 2, xr.center().y() - (isz - 2) // 2, pm)
        p.restore()

    def editorEvent(self, event, model, option, index):
        if (event.type() == QEvent.MouseButtonRelease and index.data(ROLE_KIND) == "item"
                and self._x_rect(option.rect).contains(event.position().toPoint())):
            self.removeRequested.emit(index.data(Qt.DisplayRole))
            return True                                   # לא בוחרים את השורה
        if event.type() == QEvent.MouseButtonPress and index.data(ROLE_KIND) == "item" \
                and self._x_rect(option.rect).contains(event.position().toPoint()):
            return True
        return super().editorEvent(event, model, option, index)


class HistoryCompleter(QCompleter):
    """ההשלמה של שדה החיפוש: החיפושים האחרונים, עם סינון לפי כל חלק, מחיקה וניקוי."""
    picked = Signal(str)

    def __init__(self, history: SearchHistory, edit, parent=None):
        super().__init__(parent)
        self.history, self.edit = history, edit
        self.source = QStandardItemModel(self)
        self.setModel(self.source)
        self.setCompletionRole(ROLE_MATCH)
        self.setFilterMode(Qt.MatchContains)
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.setMaxVisibleItems(10)
        edit.setCompleter(self)
        view = self.popup()
        view.setObjectName("history")
        view.setMouseTracking(True)
        view.viewport().setAttribute(Qt.WA_Hover)
        view.setUniformItemSizes(True)
        self.delegate = HistoryDelegate(view)
        self.delegate.removeRequested.connect(self._remove)
        view.setItemDelegate(self.delegate)
        self._typed = ""
        self._last_pick = (None, 0.0)
        edit.textEdited.connect(self._edited)
        self.activated[QModelIndex].connect(self._activated)
        history.changed.connect(self.rebuild)
        self.rebuild()

    # ----- תוכן -----
    def rebuild(self):
        prefix = self.completionPrefix()
        self.source.clear()
        now = time.time()
        for i in self.history.items:
            it = QStandardItem(i["q"])
            meta = " · ".join(x for x in (when_text(i["t"], now) if i.get("t") else "", count_text(i.get("n"))) if x)
            it.setData(meta, ROLE_META)
            it.setData("item", ROLE_KIND)
            it.setData(i["q"], ROLE_MATCH)
            it.setToolTip(i["q"])
            self.source.appendRow(it)
        if self.history.items:
            it = QStandardItem("")
            it.setData("clear", ROLE_KIND)
            it.setData("", ROLE_MATCH)                     # מתאים רק כשהשדה ריק
            self.source.appendRow(it)
        self.setCompletionPrefix(prefix)

    # ----- פתיחה -----
    def show_all(self):
        """פותח את כל ההיסטוריה (שדה ריק, חץ למטה, או סמל השעון)."""
        if not self.history.items:
            return
        self.setCompletionPrefix("")
        self.complete(self._rect())

    def _rect(self):
        r = self.edit.rect()
        return QRect(r.left(), r.top(), r.width(), r.height())

    def _edited(self, text):
        self._typed = text                 # ההשלמה עצמה בזמן הקלדה – של QLineEdit

    def splitPath(self, path):
        return [path.strip()]

    # ----- בחירה, מחיקה -----
    def _activated(self, index):
        kind = index.data(ROLE_KIND)
        if kind == "clear":
            self.history.clear()
            QTimer.singleShot(0, lambda: self.edit.setText(self._typed))
            return
        q = index.data(Qt.DisplayRole) or ""
        QTimer.singleShot(0, lambda: self._pick(q))

    def _pick(self, q):
        self.edit.setText(q)
        self._last_pick = (q, time.monotonic())
        self.picked.emit(q)

    def just_picked(self, q: str) -> bool:
        """Enter ברשימה מפעיל גם את returnPressed של השדה – כדי לא לחפש פעמיים."""
        last, t = self._last_pick
        return last == q and time.monotonic() - t < 0.5

    def _remove(self, q):
        self.history.remove(q)
        if self.history.items and self.popup().isVisible():
            QTimer.singleShot(0, lambda: self.complete(self._rect()))

    def eventFilter(self, obj, ev):
        if obj is self.popup() and ev.type() == QEvent.KeyPress and ev.key() == Qt.Key_Delete:
            idx = self.popup().currentIndex()
            if idx.isValid() and idx.data(ROLE_KIND) == "item":
                self._remove(idx.data(Qt.DisplayRole))
                return True
        return super().eventFilter(obj, ev)


def history_icon() -> QIcon:
    return ui_icon("clock", C.muted, C.accent)
