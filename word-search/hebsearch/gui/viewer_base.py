"""בסיס משותף למציגי המסמכים: סרגל עם מיקום, מעבר בין תוצאות ופעולות."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from .results import doc_name


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
        self.layout_ = QVBoxLayout(central)
        self.layout_.setContentsMargins(8, 8, 8, 8)
        bar = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("title")
        self.where = QLabel()
        self.where.setObjectName("muted")
        bar.addWidget(self.title)
        bar.addSpacing(12)
        bar.addWidget(self.where)
        bar.addStretch(1)
        self.prev_btn = QPushButton("הקודמת ▶")
        self.prev_btn.setToolTip("התוצאה הקודמת במסמך (Shift+F3)")
        self.prev_btn.clicked.connect(lambda: self.go(self.index - 1))
        self.next_btn = QPushButton("◀ הבאה")
        self.next_btn.setToolTip("התוצאה הבאה במסמך (F3)")
        self.next_btn.clicked.connect(lambda: self.go(self.index + 1))
        bar.addWidget(self.prev_btn)
        bar.addWidget(self.next_btn)
        self.actions_bar = QHBoxLayout()
        bar.addSpacing(12)
        bar.addLayout(self.actions_bar)
        self.layout_.addLayout(bar)
        self.setCentralWidget(central)
        QShortcut(QKeySequence("F3"), self, lambda: self.go(self.index + 1))
        QShortcut(QKeySequence("Shift+F3"), self, lambda: self.go(self.index - 1))
        QShortcut(QKeySequence("Esc"), self, self.close)

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
        self.title.setText(doc_name(self.path))
        self.where.setText(f"{hit.location}   ·   תוצאה {i + 1:,} מתוך {len(self.hits):,} במסמך")
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
