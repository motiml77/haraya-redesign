"""ווידג'טים משותפים: ספינר, שכבת התקדמות, פריסה זורמת, בורר מספרי, גלילה חלקה ועוד."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen, QTextDocument
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit, QProgressBar, QPushButton, QSizePolicy,
    QStyle, QStyleOptionComboBox, QToolButton, QVBoxLayout, QWidget,
)

from .icons import ui_icon
from .theme import C, T


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


class Chip(QPushButton):
    """כפתור-תגית (בחירת סל). לחיצה כפולה = "רק זה"."""
    doubleClicked = Signal()

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("chip")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        T.sized(self, h="h_chip")

    def mouseDoubleClickEvent(self, e):
        self.doubleClicked.emit()


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
    """שדה חיפוש קומפקטי: סמל זכוכית מגדלת בהתחלה וכפתור ניקוי (✕) בסוף."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("search")
        self.addAction(ui_icon("search", C.muted, C.muted), QLineEdit.LeadingPosition)
        self._clear = self.addAction(ui_icon("x", C.muted, C.text), QLineEdit.TrailingPosition)
        self._clear.setVisible(False)
        self._clear.setToolTip("ניקוי")
        self._clear.triggered.connect(self.clear)
        self.textChanged.connect(lambda t: self._clear.setVisible(bool(t)))
        T.sized(self, h="h_search")


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

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("popup")
        self.setAttribute(Qt.WA_DeleteOnClose, False)

    def show_below(self, anchor: QWidget):
        self.adjustSize()
        screen = anchor.screen().availableGeometry() if anchor.screen() else QRect(0, 0, 1280, 800)
        below = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
        # יישור לקצה הימני של הכפתור (RTL), ובתוך המסך
        x = below.x() + anchor.width() - self.width()
        x = max(screen.left() + 4, min(x, screen.right() - self.width() - 4))
        y = below.y()
        if y + self.height() > screen.bottom() - 4:
            y = max(screen.top() + 4, anchor.mapToGlobal(QPoint(0, 0)).y() - self.height() - 4)
        self.move(x, y)
        self.show()
