"""ווידג'טים משותפים: ספינר, שכבת התקדמות, פריסה זורמת, בורר מספרי, גלילה חלקה ועוד."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen, QTextDocument
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit, QProgressBar,
    QPushButton, QSizePolicy, QStyle, QStyleOptionComboBox, QToolButton, QVBoxLayout, QWidget,
)

from .icons import ui_icon
from .theme import C, T, ui_font


# ---------------------------------------------------------------- כפתורים וסמלים
def icon_button(name: str, tip: str = "", checkable: bool = False, bordered: bool = False,
                parent=None) -> QToolButton:
    """כפתור סמל קומפקטי (גובה לפי הזום)."""
    b = QToolButton(parent)
    b.setIcon(ui_icon(name))
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setCursor(Qt.PointingHandCursor)
    b.setToolButtonStyle(Qt.ToolButtonIconOnly)
    if bordered:
        b.setObjectName("bordered")
    T.sized(b, h="h_ctl", min_w="h_ctl", icon="icon")
    return b


def text_icon_button(name: str, text: str, tip: str = "", parent=None) -> QToolButton:
    b = QToolButton(parent)
    b.setIcon(ui_icon(name))
    b.setText(text)
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    T.sized(b, h="h_ctl", icon="icon")
    return b


def link_button(text: str, tip: str = "", icon: str = "", parent=None) -> QPushButton:
    """כפתור-קישור: טקסט בצבע ההדגשה, רקע רק במעבר עכבר."""
    b = QPushButton(text, parent)
    b.setObjectName("link")
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.TabFocus)
    if icon:
        b.setIcon(ui_icon(icon, C.accent, C.accent_hover))
        T.sized(b, icon="icon")
    T.sized(b, h="h_chip")
    return b


def _focus_ring(p: QPainter, rect: QRectF, radius: float):
    p.setPen(QPen(QColor(C.accent), 2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), radius + 1, radius + 1)


class OptionChip(QAbstractButton):
    """שבב של הגדרה: "שם: ערך ⌄". מציג את הבחירה הנוכחית במילים, ולחיצה פותחת חלונית.

    מצבים: on – שונה מברירת המחדל (צבוע), locked – ננעל (מסגרת מקווקוות ומנעול, בלי חץ),
    dim – לא רלוונטי כרגע (מעומעם, עדיין לחיץ), open – החלונית שלו פתוחה."""

    RING = 2

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self._key, self._value = key, ""
        self._on = self._locked = self._dim = self._open = self._warn = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    # ----- מצב -----
    def value(self) -> str:
        return self._value

    def setValue(self, text: str):
        if text != self._value:
            self._value = text
            self.setAccessibleName(f"{self._key} {text}")
            self.updateGeometry()
            self.update()

    def _flag(self, name, on):
        if getattr(self, name) != bool(on):
            setattr(self, name, bool(on))
            self.update()

    def setOn(self, on: bool):
        self._flag("_on", on)

    def setLocked(self, on: bool):
        self._flag("_locked", on)
        self.updateGeometry()

    def setDim(self, on: bool):
        self._flag("_dim", on)

    def setOpen(self, on: bool):
        self._flag("_open", on)

    def setWarn(self, on: bool):
        self._flag("_warn", on)

    def isOn(self) -> bool:
        return self._on

    def isLocked(self) -> bool:
        return self._locked

    def isDim(self) -> bool:
        return self._dim

    # ----- מידות -----
    def _fonts(self):
        return ui_font(T.body), ui_font(T.body, 600)

    def sizeHint(self):
        fk, fv = self._fonts()
        w = 2 * self.RING + 2 * T.gap + 2
        w += QFontMetrics(fk).horizontalAdvance(self._key) + 4 + QFontMetrics(fv).horizontalAdvance(self._value)
        w += (T.icon - 2) + 4      # חץ או מנעול
        return QSize(w, T.h_ctl + 2 * self.RING - 2)

    def minimumSizeHint(self):
        return self.sizeHint()

    # ----- ציור -----
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._dim and not self._open:
            p.setOpacity(0.5)
        box = QRectF(self.rect()).adjusted(self.RING + 0.5, self.RING + 0.5, -self.RING - 0.5, -self.RING - 0.5)
        r = T.radius + 1
        hover = self.underMouse() and self.isEnabled()
        if self._locked:
            bg, border, val = C.surface_alt, C.border_strong, C.text2
        elif self._warn:
            bg, border, val = C.warn_bg, "#efc98a", C.warn
        elif self._on:
            bg, border, val = C.accent_soft, "#b7cdfb", C.accent
        else:
            bg, border, val = C.surface, C.border_strong, C.text
        if hover and not self._locked:
            bg = C.accent_sel if self._on else C.hover
            border = C.accent if self._on else "#aeb8c9"
        if self._open:
            border = C.accent
        if self.isDown():
            bg = C.accent_sel
        pen = QPen(QColor(border), 1)
        if self._locked:
            pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(QColor(bg))
        p.drawRoundedRect(box, r, r)
        if self._open:                      # טבעת עדינה סביב השבב שהחלונית שלו פתוחה
            p.setPen(QPen(QColor(C.accent_sel), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box.adjusted(-1.5, -1.5, 1.5, 1.5), r + 1.5, r + 1.5)
        elif self.hasFocus():
            _focus_ring(p, box, r)

        fk, fv = self._fonts()
        x = box.right() - T.gap
        isz = T.icon - 2
        if self._locked:
            pm = ui_icon("lock", C.text2).pixmap(QSize(isz, isz))
            p.drawPixmap(int(x - isz), int(box.center().y() - isz / 2), pm)
            x -= isz + 4
        p.setFont(fk)
        kw = QFontMetrics(fk).horizontalAdvance(self._key)
        p.setPen(QColor(C.muted))
        p.drawText(QRectF(x - kw, box.top(), kw + 1, box.height()), Qt.AlignRight | Qt.AlignVCenter, self._key)
        x -= kw + 4
        p.setFont(fv)
        vw = QFontMetrics(fv).horizontalAdvance(self._value)
        p.setPen(QColor(val))
        p.drawText(QRectF(x - vw, box.top(), vw + 1, box.height()), Qt.AlignRight | Qt.AlignVCenter, self._value)
        x -= vw + 4
        if not self._locked:
            name = "chevron-up" if self._open else "chevron-down"
            color = C.accent if (self._open or self._on) else C.muted
            pm = ui_icon(name, color).pixmap(QSize(isz, isz))
            p.drawPixmap(int(x - isz), int(box.center().y() - isz / 2), pm)

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class Segmented(QWidget):
    """בורר מקטעים: כמה אפשרויות צמודות, אחת נבחרת. "גלולה" לבנה מחליקה אל הבחירה.

    במקום קבוצת כפתורי רדיו לבחירות קצרות שהן סולם (מדויק ← רחב). חצים במקלדת מזיזים את הבחירה."""
    changed = Signal(int)

    def __init__(self, items, index=0, parent=None):
        super().__init__(parent)
        self._items = list(items)
        self._index = index
        self._pos = float(index)            # מיקום הגלולה (לאנימציה)
        self._hover = -1
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._moved)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        T.sized(self, h="h_ctl")

    def index(self) -> int:
        return self._index

    def items(self):
        return list(self._items)

    def setIndex(self, i: int, emit: bool = False, animate: bool = False):
        i = max(0, min(len(self._items) - 1, int(i)))
        if i == self._index:
            return
        start = self._pos
        self._index = i
        self.setAccessibleDescription(self._items[i])
        if animate and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(float(start))
            self._anim.setEndValue(float(i))
            self._anim.start()
        else:
            self._pos = float(i)
            self.update()
        if emit:
            self.changed.emit(i)

    def _moved(self, v):
        self._pos = float(v)
        self.update()

    def _font(self, selected=False):
        return ui_font(T.body, 600 if selected else None)

    def sizeHint(self):
        fm = QFontMetrics(self._font(True))
        w = sum(fm.horizontalAdvance(t) + 2 * T.pad + 4 for t in self._items) + 4
        return QSize(w, T.h_ctl)

    def minimumSizeHint(self):
        return self.sizeHint()

    def _rects(self):
        """מלבני המקטעים, מימין לשמאל; רוחב יחסי לטקסט והעודף מתחלק שווה."""
        fm = QFontMetrics(self._font(True))
        widths = [fm.horizontalAdvance(t) + 2 * T.pad for t in self._items]
        inner = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        extra = max(0.0, inner.width() - sum(widths)) / max(1, len(widths))
        x = inner.right()
        out = []
        for w in widths:
            w = w + extra
            out.append(QRectF(x - w, inner.top(), w, inner.height()))
            x -= w
        return out

    def _at(self, pos) -> int:
        for i, r in enumerate(self._rects()):
            if r.contains(pos):
                return i
        return -1

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.5)
        track = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        r = T.radius + 1
        p.setPen(QPen(QColor(C.border), 1))
        p.setBrush(QColor(C.track))
        p.drawRoundedRect(track, r, r)
        rects = self._rects()
        if not rects:
            return
        # הגלולה: בין שני מקטעים כשהיא בתנועה
        lo = int(self._pos)
        hi = min(len(rects) - 1, lo + 1)
        f = self._pos - lo
        a, b = rects[lo], rects[hi]
        pill = QRectF(a.left() + (b.left() - a.left()) * f, a.top(), a.width() + (b.width() - a.width()) * f, a.height())
        if 0 <= self._hover < len(rects) and self._hover != self._index:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C.track_hover))
            p.drawRoundedRect(rects[self._hover], r - 1, r - 1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 22))                 # צל רך מתחת לגלולה
        p.drawRoundedRect(pill.translated(0, 1), r - 1, r - 1)
        p.setPen(QPen(QColor(C.border_strong), 1))
        p.setBrush(QColor(C.surface))
        p.drawRoundedRect(pill.adjusted(0.5, 0.5, -0.5, -0.5), r - 1, r - 1)
        for i, rect in enumerate(rects):
            sel = i == self._index
            p.setFont(self._font(sel))
            p.setPen(QColor(C.accent if sel else (C.text if i == self._hover else C.text2)))
            p.drawText(rect, Qt.AlignCenter, self._items[i])
        if self.hasFocus() and self._kbd_focus:
            _focus_ring(p, track, r)

    _kbd_focus = False

    def focusInEvent(self, e):
        # טבעת מיקוד רק בניווט במקלדת (Tab), לא אחרי לחיצת עכבר
        self._kbd_focus = e.reason() in (Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)
        super().focusInEvent(e)

    def focusOutEvent(self, e):
        self._kbd_focus = False
        super().focusOutEvent(e)

    def mousePressEvent(self, e):
        i = self._at(e.position())
        if i >= 0:
            self.setIndex(i, emit=True, animate=True)

    def mouseMoveEvent(self, e):
        i = self._at(e.position())
        if i != self._hover:
            self._hover = i
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()
        super().leaveEvent(e)

    def keyPressEvent(self, e):
        # בממשק מימין לשמאל: חץ ימינה = האפשרות הקודמת (שמימין)
        if e.key() == Qt.Key_Right:
            self.setIndex(self._index - 1, emit=True, animate=True)
        elif e.key() == Qt.Key_Left:
            self.setIndex(self._index + 1, emit=True, animate=True)
        else:
            super().keyPressEvent(e)


class Combo(QComboBox):
    """תיבה נפתחת עם חץ מצויר: ה-QSS מסיר את החץ המקורי של הסגנון, אז מציירים אותו כאן."""

    def paintEvent(self, e):
        super().paintEvent(e)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        arrow = self.style().subControlRect(QStyle.CC_ComboBox, opt, QStyle.SC_ComboBoxArrow, self)
        size = max(10, T.icon - 4)
        box = QRect(0, 0, size, size)
        box.moveCenter(arrow.center())
        mode = QIcon.Disabled if not self.isEnabled() else QIcon.Active if self.underMouse() else QIcon.Normal
        p = QPainter(self)
        ui_icon("chevron-down", C.muted, C.text).paint(p, box, Qt.AlignCenter, mode)


# ---------------------------------------------------------------- שדה חיפוש
class SearchField(QLineEdit):
    """שדה חיפוש קומפקטי: זכוכית מגדלת בהתחלה; בסוף – שעון (היסטוריה) וכפתור ניקוי (✕).
    לחיצה על השדה כשהוא ריק, או חץ למטה, מבקשות את היסטוריית החיפוש."""
    historyRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("search")
        self.addAction(ui_icon("search", C.muted, C.muted), QLineEdit.LeadingPosition)
        self._clear = self.addAction(ui_icon("x", C.muted, C.text), QLineEdit.TrailingPosition)
        self._clear.setVisible(False)
        self._clear.setToolTip("ניקוי")
        self._clear.triggered.connect(self.clear)
        self.history_action = self.addAction(ui_icon("clock", C.muted, C.accent), QLineEdit.TrailingPosition)
        self.history_action.setToolTip("חיפושים אחרונים (חץ למטה)")
        self.history_action.triggered.connect(self.historyRequested)
        self.textChanged.connect(lambda t: self._clear.setVisible(bool(t)))
        T.sized(self, h="h_search")
        self.shortcut_hint = "Ctrl+F"

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        if not self.text() and e.button() == Qt.LeftButton:
            self.historyRequested.emit()

    def keyPressEvent(self, e):
        popup = self.completer().popup() if self.completer() else None
        if e.key() == Qt.Key_Down and not (popup and popup.isVisible()):
            self.historyRequested.emit()
            return
        super().keyPressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        # רמז מקלדת בקצה השדה כשהוא ריק ולא בפוקוס (כמו בתוכנות עבודה מודרניות)
        if self.text() or self.hasFocus() or not self.shortcut_hint or self.width() < T.pad * 40:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = ui_font(T.caption - 1, 600)
        p.setFont(f)
        fm = QFontMetrics(f)
        w, h = fm.horizontalAdvance(self.shortcut_hint) + 10, fm.height() + 4
        start = T.gap + 2 + (T.icon + 10 if self.history_action.isVisible() else 0)   # אחרי סמל השעון
        r = QRectF(start, (self.height() - h) / 2, w, h)            # בקצה השמאלי (סוף השדה בעברית)
        p.setPen(QPen(QColor(C.border_strong), 1))
        p.setBrush(QColor(C.surface))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        p.setPen(QColor(C.muted))
        p.drawText(r, Qt.AlignCenter, self.shortcut_hint)


class FormChips(QWidget):
    """הצורות שנמצאו, כשבבים קטנים עם מספר. לחיצה מסננת לפי הצורה, לחיצה נוספת מבטלת.
    שורה אחת בלבד; מה שלא נכנס מתקפל ל"ועוד N", שפותח את כל הצורות."""
    clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.flow = FlowLayout(self, 4, 4)
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self._chips, self._extra, self._expanded = [], 0, False
        self._label = self._more = self._clear = None

    def set_forms(self, forms, active=None, extra=0):
        """forms: [(צורה, מספר)]; extra: כמה צורות נוספות לא הועברו בכלל."""
        while self.flow.count():
            item = self.flow.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._chips, self._extra = [], extra
        self._label = QLabel("צורות שנמצאו:")
        self._label.setObjectName("caption")
        T.sized(self._label, h="h_chip")
        self.flow.addWidget(self._label)
        for form, count in forms:
            b = QPushButton(f"{form}  {count:,}")
            b.setObjectName("formchip")
            b.setCheckable(True)
            b.setChecked(form == active)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.TabFocus)
            b.setToolTip(f"הצגת התוצאות עם הצורה '{form}' בלבד" if form != active else "ביטול הסינון")
            T.sized(b, h="h_chip")
            b.clicked.connect(lambda _=False, f=form: self.clicked.emit(f))
            self.flow.addWidget(b)
            self._chips.append(b)
        self._more = link_button("")
        self._more.clicked.connect(self._toggle)
        self.flow.addWidget(self._more)
        self._clear = None
        if active:
            self._clear = link_button("הצגת הכל")
            self._clear.clicked.connect(lambda: self.clicked.emit(""))
            self.flow.addWidget(self._clear)
        self._relayout()

    def _toggle(self):
        self._expanded = not self._expanded
        self._relayout()

    def _relayout(self):
        if self._more is None:
            return
        if self._expanded:
            for b in self._chips:
                b.show()
            self._more.setText("פחות ⌃")
            self._more.setEnabled(True)
            self._more.setVisible(self._has_overflow())
        else:
            room = self.width() - self._label.sizeHint().width() - 8
            if self._clear is not None:
                room -= self._clear.sizeHint().width() + 4
            more_w = QFontMetrics(self._more.font()).horizontalAdvance("ועוד 999 ⌄") + 2 * T.gap + 4
            used = hidden = 0
            for i, b in enumerate(self._chips):
                w = b.sizeHint().width() + 4
                reserve = 0 if (i == len(self._chips) - 1 and not self._extra) else more_w
                if hidden == 0 and used + w + reserve <= room:
                    b.show()
                    used += w
                else:
                    b.hide()
                    hidden += 1
            rest = hidden + self._extra
            self._more.setText(f"ועוד {rest:,} ⌄" if hidden else f"ועוד {rest:,}")
            self._more.setEnabled(hidden > 0)          # רק צורות שלא הועברו – תווית בלבד
            self._more.setVisible(rest > 0)
        self.flow.invalidate()
        self.updateGeometry()

    def _has_overflow(self) -> bool:
        """האם בתצוגה מקופלת היו צורות מוסתרות (כדי לדעת אם להציג "פחות")."""
        room = self.width() - self._label.sizeHint().width() - 8
        return sum(b.sizeHint().width() + 4 for b in self._chips) > room

    def relayout(self):
        """אחרי שינוי זום: הגדלים השתנו, צריך לחשב מחדש מה נכנס בשורה."""
        QTimer.singleShot(0, self._relayout)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if e.oldSize().width() != e.size().width():
            self._relayout()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self.flow.heightForWidth(w)


# ---------------------------------------------------------------- בורר מספרי
class Stepper(QFrame):
    """בורר מספרי קומפקטי  [−] 3 [+]  (במקום QSpinBox שנראה לא טוב בעיצוב המותאם)."""
    valueChanged = Signal(int)

    def __init__(self, minimum=0, maximum=99, value=0, parent=None):
        super().__init__(parent)
        self.setObjectName("stepper")
        self._min, self._max, self._value = minimum, maximum, value
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.minus = QToolButton()
        self.minus.setObjectName("step")
        self.minus.setIcon(ui_icon("minus"))
        self.minus.setAutoRepeat(True)
        self.plus = QToolButton()
        self.plus.setObjectName("step")
        self.plus.setIcon(ui_icon("plus"))
        self.plus.setAutoRepeat(True)
        self.label = QLabel(str(value))
        self.label.setAlignment(Qt.AlignCenter)
        T.sized(self.label, min_w=36)
        for b in (self.minus, self.plus):
            b.setCursor(Qt.PointingHandCursor)
            T.sized(b, h="h_ctl", w="h_ctl", icon="icon")
        lay.addWidget(self.plus)
        lay.addWidget(self.label)
        lay.addWidget(self.minus)
        self.minus.clicked.connect(lambda: self.setValue(self._value - 1))
        self.plus.clicked.connect(lambda: self.setValue(self._value + 1))
        T.sized(self, h="h_ctl")
        self._refresh()

    def value(self) -> int:
        return self._value

    def setValue(self, v: int, emit: bool = True):
        v = max(self._min, min(self._max, int(v)))
        if v != self._value:
            self._value = v
            self._refresh()
            if emit:
                self.valueChanged.emit(v)

    def _refresh(self):
        self.label.setText(str(self._value))
        self.minus.setEnabled(self._value > self._min and self.isEnabled())
        self.plus.setEnabled(self._value < self._max and self.isEnabled())

    def changeEvent(self, e):
        if e.type() == QEvent.EnabledChange:
            self._refresh()
        super().changeEvent(e)


# ---------------------------------------------------------------- תווית עם קיצור
class ElidedLabel(QLabel):
    """תווית שמקצרת טקסט ארוך ב-… (ושומרת את הטקסט המלא ב-tooltip)."""

    def __init__(self, text="", mode=Qt.ElideRight, parent=None):
        super().__init__(parent)
        self._full = text
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._update()

    def setFullText(self, text: str):
        self._full = text
        self._update()

    def fullText(self) -> str:
        return self._full

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update()

    def _update(self):
        fm = QFontMetrics(self.font())
        width = max(10, self.width() - 2)
        shown = fm.elidedText(self._full, self._mode, width)
        if shown != self.text():
            super().setText(shown)
        self.setToolTip(self._full if shown != self._full else "")

    def minimumSizeHint(self):
        return QSize(24, super().minimumSizeHint().height())


class WrapLabel(QLabel):
    """תווית עם גלישת שורות שגובהה נגזר מהרוחב בפועל. בתוך לשוניות QLabel רגיל שומר מקום
    ליותר שורות משצריך (גובה-לפי-רוחב לא עובר דרך QTabWidget), ונוצר רווח ריק."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._fit()

    def setText(self, text):
        super().setText(text)
        self._fit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def showEvent(self, e):
        super().showEvent(e)
        self._fit()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() in (QEvent.FontChange, QEvent.StyleChange):     # ה-QSS משנה את הגופן אחרי הבנייה
            self._fit()

    def _fit(self):
        width = max(60, self.width())
        if self.textFormat() == Qt.RichText or (self.textFormat() == Qt.AutoText and "<" in self.text()):
            doc = QTextDocument()
            doc.setDefaultFont(self.font())
            doc.setTextWidth(width)
            doc.setHtml(self.text())
            h = int(doc.size().height())
        else:
            h = QFontMetrics(self.font()).boundingRect(0, 0, width, 100_000, Qt.TextWordWrap, self.text()).height()
        h += 2
        if h != self.minimumHeight():
            self.setMinimumHeight(h)
            self.setMaximumHeight(h)


# ---------------------------------------------------------------- פריסה זורמת (עוברת שורה)
class FlowLayout(QLayout):
    """פריסה שמעבירה פריטים לשורה חדשה כשנגמר המקום; מכבדת כיוון RTL."""

    def __init__(self, parent=None, hspacing=8, vspacing=6):
        super().__init__(parent)
        self._items = []
        self._h, self._v = hspacing, vspacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _layout(self, rect, test_only):
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        rtl = QApplication.layoutDirection() == Qt.RightToLeft
        x = area.right() + 1 if rtl else area.x()
        y = area.y()
        line_h = 0
        for item in self._items:
            if item.isEmpty():
                continue
            sz = item.sizeHint()
            w, h = sz.width(), sz.height()
            if rtl:
                left = x - w
                if left < area.x() and line_h > 0:
                    x = area.right() + 1
                    y += line_h + self._v
                    line_h = 0
                    left = x - w
                if not test_only:
                    item.setGeometry(QRect(QPoint(left, y), sz))
                x = left - self._h
            else:
                if x + w > area.right() + 1 and line_h > 0:
                    x = area.x()
                    y += line_h + self._v
                    line_h = 0
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), sz))
                x += w + self._h
            line_h = max(line_h, h)
        return y + line_h - rect.y() + m.bottom()


# ---------------------------------------------------------------- ספינר
class Spinner(QWidget):
    """ספינר מסתובב (קשת על טבעת)."""

    def __init__(self, size=28, thickness=3, parent=None):
        super().__init__(parent)
        self._size, self._th, self._angle = size, thickness, 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _tick(self):
        self._angle = (self._angle + 14) % 360
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self._th / 2, self._th / 2, self._size - self._th, self._size - self._th)
        pen = QPen(QColor(C.border), self._th)
        p.setPen(pen)
        p.drawEllipse(r)
        pen = QPen(QColor(C.accent), self._th)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(r, int(-self._angle * 16), 110 * 16)


# ---------------------------------------------------------------- שכבת התקדמות
class BusyOverlay(QWidget):
    """שכבה מעומעמת מעל אזור שמציגה ספינר, אחוזים, סרגל התקדמות וכפתור ביטול.
    מופיעה רק אם הפעולה נמשכת יותר מ-delay (כדי שחיפוש מהיר לא יהבהב)."""

    cancelRequested = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._parent = parent
        parent.installEventFilter(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.card = QFrame()
        self.card.setObjectName("popup")
        self.card.setMinimumWidth(300)
        self.card.setMaximumWidth(380)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(T.pad * 2, T.pad * 2, T.pad * 2, T.pad * 2)
        lay.setSpacing(T.gap)
        self.spinner = Spinner(32, 3)
        lay.addWidget(self.spinner, 0, Qt.AlignHCenter)
        self.title = QLabel("מחפש…")
        self.title.setObjectName("title")
        self.title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.title)
        self.percent = QLabel("")
        self.percent.setObjectName("percent")
        self.percent.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.percent)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)
        self.detail = QLabel("")
        self.detail.setObjectName("caption")
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setWordWrap(True)
        lay.addWidget(self.detail)
        self.cancel = QPushButton("ביטול")
        self.cancel.setCursor(Qt.PointingHandCursor)
        self.cancel.clicked.connect(self.cancelRequested)
        lay.addWidget(self.cancel, 0, Qt.AlignHCenter)
        row.addWidget(self.card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reveal)
        self.hide()

    # ----- API -----
    def begin(self, title: str = "מחפש…", delay_ms: int = 220, cancellable: bool = True):
        self.title.setText(title)
        self.cancel.setVisible(cancellable)
        self.set_progress(-1, None, "")
        self._timer.start(delay_ms)

    def set_progress(self, frac: float, title: str | None = None, detail: str | None = None):
        if title:
            self.title.setText(title)
        if detail is not None:
            self.detail.setText(detail)
            self.detail.setVisible(bool(detail))
        if frac is None or frac < 0:
            self.percent.setText("")
            self.bar.setVisible(False)
        else:
            frac = min(1.0, frac)
            self.percent.setText(f"{int(frac * 100)}%")
            self.bar.setVisible(True)
            self.bar.setValue(int(frac * 1000))

    def end(self):
        self._timer.stop()
        self.hide()

    def is_active(self) -> bool:
        return self._timer.isActive() or self.isVisible()

    # ----- פנימי -----
    def _reveal(self):
        self.setGeometry(self._parent.rect())
        self.raise_()
        self.show()

    def eventFilter(self, obj, ev):
        if obj is self._parent and ev.type() == QEvent.Resize and self.isVisible():
            self.setGeometry(self._parent.rect())
        return False

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(243, 244, 247, 238))


# ---------------------------------------------------------------- גלילה חלקה
class SmoothScroller(QObject):
    """גלילת גלגלת עכבר חלקה (אנימציה), במרווחים נוחים; מגע/משטח מגע – בגלילה ישירה."""

    def __init__(self, area, step: int = 84, duration: int = 170):
        super().__init__(area)
        self.area = area
        self.bar = area.verticalScrollBar()
        self.step = step
        self.target = None
        self.anim = QPropertyAnimation(self.bar, b"value", self)
        self.anim.setDuration(duration)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        area.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() != QEvent.Wheel or ev.modifiers() & Qt.ControlModifier:
            return False
        pixel = ev.pixelDelta()
        if not pixel.isNull():                    # משטח מגע: גלילה ישירה ומדויקת
            self.anim.stop()
            self.bar.setValue(self.bar.value() - pixel.y())
            return True
        dy = ev.angleDelta().y()
        if dy == 0:
            return False
        base = self.target if self.anim.state() == QPropertyAnimation.Running and self.target is not None \
            else self.bar.value()
        self.target = max(self.bar.minimum(), min(self.bar.maximum(), int(base - dy / 120 * self.step)))
        self.anim.stop()
        self.anim.setStartValue(self.bar.value())
        self.anim.setEndValue(self.target)
        self.anim.start()
        return True


# ---------------------------------------------------------------- חלון קופץ
class Popup(QFrame):
    """חלון קופץ (נסגר בלחיצה בחוץ) המעוגן לכפתור."""
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("popup")
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.closed_at = 0.0

    def hideEvent(self, e):
        import time
        self.closed_at = time.monotonic()
        super().hideEvent(e)
        self.closed.emit()

    def show_below(self, anchor: QWidget):
        self.adjustSize()
        screen = anchor.screen().availableGeometry() if anchor.screen() else QRect(0, 0, 1280, 800)
        below = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
        # יישור לקצה הימני של הכפתור (RTL); בתוך חלון התוכנה אם יש מקום, ותמיד בתוך המסך
        x = below.x() + anchor.width() - self.width()
        win = anchor.window().geometry() if anchor.window() is not None else screen
        if win.width() >= self.width() + 8:
            x = max(win.left() + 4, min(x, win.right() - self.width() - 4))
        x = max(screen.left() + 4, min(x, screen.right() - self.width() - 4))
        y = below.y()
        if y + self.height() > screen.bottom() - 4:
            y = max(screen.top() + 4, anchor.mapToGlobal(QPoint(0, 0)).y() - self.height() - 4)
        self.move(x, y)
        self.show()
