"""בסיס משותף למציגי המסמכים: סרגל עם מיקום, מעבר בין תוצאות ופעולות."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QPushButton, QVBoxLayout, QWidget

from .results import doc_name
from .theme import T, fit_geometry
from .widgets import ElidedLabel


class HitViewer(QMainWindow):
    """חלון שמציג מסמך אחד ועובר בין התוצאות שבו."""

    def __init__(self, searcher, highlight, hits, index, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.searcher, self.highlight = searcher, highlight
        self.hits, self.index = hits, index
        self.path = hits[index].path
        self.setWindowTitle(doc_name(self.path))

        central = QWidget()
        central.setObjectName("central")
        self.layout_ = QVBoxLayout(central)
        self.layout_.setContentsMargins(T.gap, T.gap, T.gap, T.gap)
        self.layout_.setSpacing(T.gap)
        head = QHBoxLayout()
        head.setSpacing(T.gap)
        self.title = ElidedLabel("", Qt.ElideMiddle)
        self.title.setObjectName("title")
        self.actions_bar = QHBoxLayout()
        self.actions_bar.setSpacing(T.gap)
        head.addWidget(self.title, 1)
        head.addLayout(self.actions_bar)
        self.layout_.addLayout(head)

        nav = QHBoxLayout()
        nav.setSpacing(T.gap)
        self.where = ElidedLabel("", Qt.ElideRight)
        self.where.setObjectName("muted")
        self.prev_btn = QPushButton("הקודמת ▶")
        self.prev_btn.setToolTip("התוצאה הקודמת במסמך (Shift+F3)")
        self.prev_btn.clicked.connect(lambda: self.go(self.index - 1))
        self.next_btn = QPushButton("◀ הבאה")
        self.next_btn.setToolTip("התוצאה הבאה במסמך (F3)")
        self.next_btn.clicked.connect(lambda: self.go(self.index + 1))
        nav.addWidget(self.where, 1)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        self.layout_.addLayout(nav)
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

    def add_action(self, text, slot, tip=""):
        b = QPushButton(text)
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
        self.where.setFullText(f"{hit.location}   ·   תוצאה {i + 1:,} מתוך {len(self.hits):,} במסמך")
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
