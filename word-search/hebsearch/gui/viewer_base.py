"""בסיס משותף למציגי המסמכים: סרגל כלים (שם, מיקום, מעבר בין תוצאות, פעולות) ודף המסמך."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from .icons import file_icon, ui_icon
from .results import doc_name
from .theme import C, T, fit_geometry
from .widgets import ElidedLabel, icon_button


class HitViewer(QMainWindow):
    """חלון שמציג מסמך אחד ועובר בין התוצאות שבו.

        ┌ [סמל] שם המסמך                      ‹ 2 מתוך 8 ›  │  [הצג בתיקייה] [פתח את המסמך המקורי] ┐
        │       עמוד 1 · פסקה 2                                                                  │
        ├──────────────────────────────────────────────────────────────────────────────────┤
        │                       ┌──── דף המסמך (לבן, על רקע אפור) ────┐                      │
    """

    def __init__(self, searcher, highlight, hits, index, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.searcher, self.highlight = searcher, highlight
        self.hits, self.index = hits, index
        self.path = hits[index].path
        self.setWindowTitle(doc_name(self.path))

        central = QWidget()
        central.setObjectName("viewer")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("header")
        head = QHBoxLayout(bar)
        head.setContentsMargins(T.pad + 2, T.gap, T.pad + 2, T.gap)
        head.setSpacing(T.gap)
        icon = QLabel()
        icon.setPixmap(file_icon(self.path).pixmap(QSize(T.icon + 8, T.icon + 8)))
        head.addWidget(icon, 0, Qt.AlignTop)
        names = QVBoxLayout()
        names.setSpacing(0)
        self.title = ElidedLabel("", Qt.ElideMiddle)
        self.title.setObjectName("title")
        self.where = ElidedLabel("", Qt.ElideRight)
        self.where.setObjectName("caption")
        names.addWidget(self.title)
        names.addWidget(self.where)
        head.addLayout(names, 1)

        # מעבר בין התוצאות: ‹ 2 מתוך 8 ›. בממשק מימין לשמאל "הקודמת" היא לכיוון ימין
        nav = QFrame()
        nav.setObjectName("navgroup")
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(0, 0, 0, 0)
        nl.setSpacing(0)
        self.prev_btn = icon_button("chevron-right", "התוצאה הקודמת במסמך (Shift+F3)")
        self.prev_btn.clicked.connect(lambda: self.go(self.index - 1))
        self.next_btn = icon_button("chevron-left", "התוצאה הבאה במסמך (F3)")
        self.next_btn.clicked.connect(lambda: self.go(self.index + 1))
        self.counter = QLabel("")
        self.counter.setObjectName("counter")
        self.counter.setAlignment(Qt.AlignCenter)
        nl.addWidget(self.prev_btn)
        nl.addWidget(self.counter)
        nl.addWidget(self.next_btn)
        head.addWidget(nav, 0, Qt.AlignVCenter)
        sep = QFrame()
        sep.setObjectName("vsep")
        T.sized(sep, h="h_ctl")
        head.addWidget(sep, 0, Qt.AlignVCenter)
        self.actions_bar = QHBoxLayout()
        self.actions_bar.setSpacing(6)
        head.addLayout(self.actions_bar)
        outer.addWidget(bar)

        # הדף: על רקע אפור, כמו תצוגת הדפסה
        page_area = QWidget()
        page_area.setObjectName("pagearea")
        self.layout_ = QVBoxLayout(page_area)
        self.layout_.setContentsMargins(T.pad * 2, T.pad + 4, T.pad * 2, 0)
        self.layout_.setSpacing(0)
        outer.addWidget(page_area, 1)
        self.setCentralWidget(central)
        QShortcut(QKeySequence("F3"), self, lambda: self.go(self.index + 1))
        QShortcut(QKeySequence("Shift+F3"), self, lambda: self.go(self.index - 1))
        QShortcut(QKeySequence("Esc"), self, self.close)

    def fit(self, want_w, want_h):
        """גודל התחלתי בתוך המסך (לא גדול ממנו), ממורכז."""
        parent = self.parent()
        screen = (parent.screen() if parent is not None else None) or QGuiApplication.primaryScreen()
        self.setGeometry(fit_geometry(screen.availableGeometry(), want_w, want_h, 0.92))
        self.setMinimumSize(min(560, self.width()), min(380, self.height()))

    def add_action(self, text, slot, tip="", kind="", icon=""):
        """kind: "primary" לפעולה הראשית, "ghost" לכפתור שקוף, ריק – כפתור משני."""
        if kind == "ghost" and icon and not text:
            b = icon_button(icon, tip)
        else:
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            if kind:
                b.setObjectName(kind)
            if icon:
                color = "#ffffff" if kind == "primary" else C.text2
                b.setIcon(ui_icon(icon, color, color))
                b.setIconSize(QSize(T.icon, T.icon))
            b.setToolTip(tip)
        b.clicked.connect(slot)
        self.actions_bar.addWidget(b)
        return b

    @property
    def hit(self):
        return self.hits[self.index]

    def go(self, i):
        if not 0 <= i < len(self.hits):
            return
        self.index = i
        hit = self.searcher.materialize(self.hits[i], self.highlight)
        self.title.setFullText(doc_name(self.path))
        self.where.setFullText(hit.location)
        self.counter.setText(f"{i + 1:,} מתוך {len(self.hits):,}")
        self.counter.setToolTip("התוצאה הנוכחית מתוך התוצאות במסמך הזה")
        self.prev_btn.setEnabled(i > 0)
        self.next_btn.setEnabled(i < len(self.hits) - 1)
        self.show_hit(hit)

    def show_hit(self, hit):  # pragma: no cover - ממומש במחלקות היורשות
        raise NotImplementedError

    def navigate(self, hits, hit):
        """מעבר לתוצאה (מחלון התוצאות) בחלון שכבר פתוח."""
        self.hits = hits
        self.go(next(i for i, h in enumerate(hits) if h is hit))
        self.showNormal()
        self.raise_()
        self.activateWindow()
