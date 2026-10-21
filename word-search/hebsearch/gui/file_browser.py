"""עיון במחשב: עץ מלא של התיקיות והמסמכים עם תיבות סימון שמוסיפות לסל ומוציאות ממנו.

כמו בסייר (ובתוכנות מקצועיות כמו VS Code): העץ מתחיל מכל הכוננים וגבוה ככל שהסרגל מאפשר –
בלי "שורש" מוגבל שצריך לעלות ממנו. לניווט מהיר: מקלידים נתיב, בוחרים קיצור דרך (שולחן עבודה,
מסמכים, הורדות, כוננים, תיקיות אחרונות) או עולים תיקייה. כפתור ההרחבה פותח את אותו עץ בחלון גדול.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QDir, QSize, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCompleter, QDialog, QFileDialog, QFileSystemModel, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QPushButton, QToolButton, QTreeView, QVBoxLayout, QWidget,
)

from ..basket import CHECKED, PARTIAL
from ..index import SUPPORTED_EXTS
from ..opener import open_default
from .icons import file_icon, folder_icon, ui_icon
from .results import ltr, short_path
from .theme import T
from .widgets import icon_button

_STATE = {CHECKED: Qt.Checked, PARTIAL: Qt.PartiallyChecked}
NAME_FILTERS = [f"*{e}" for e in sorted(SUPPORTED_EXTS)] + [f"*{e.upper()}" for e in sorted(SUPPORTED_EXTS)]


class CheckableFsModel(QFileSystemModel):
    """מערכת הקבצים: תיקיות ומסמכים נתמכים בלבד, עם סימון לפי מצב הסל."""
    toggled = Signal(str, bool, bool)      # נתיב, תיקייה?, מסומן?

    def __init__(self, state_fn, parent=None):
        super().__init__(parent)
        self.state_fn = state_fn
        self.setReadOnly(True)
        self.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot | QDir.Drives)
        self.setNameFilters(NAME_FILTERS)
        self.setNameFilterDisables(False)

    def flags(self, index):
        f = super().flags(index)
        if index.column() == 0:
            f |= Qt.ItemIsUserCheckable
        return f

    def data(self, index, role=Qt.DisplayRole):
        if index.column() == 0:
            if role == Qt.CheckStateRole:
                path = self.filePath(index)
                is_dir = self.isDir(index)
                if not path or (not is_dir and os.path.basename(path).startswith("~$")):
                    return None
                return _STATE.get(self.state_fn(path, is_dir), Qt.Unchecked)
            if role == Qt.DecorationRole:
                if not self.isDir(index):
                    return file_icon(self.filePath(index))      # הסמל של מערכת ההפעלה לסוג הקובץ
                icon = super().data(index, role)                # תיקיות וכוננים: הסמלים של המערכת
                return icon if isinstance(icon, QIcon) and not icon.isNull() else folder_icon()
            if role == Qt.DisplayRole and not self.isDir(index):
                return os.path.splitext(self.fileName(index))[0]  # בלי הסיומת הלטינית (משבשת שמות בעברית)
            if role == Qt.ToolTipRole:
                return ltr(self.filePath(index))
        return super().data(index, role)

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.CheckStateRole and index.column() == 0:
            checked = value in (Qt.Checked, 2) or getattr(value, "value", None) == 2
            self.toggled.emit(self.filePath(index), self.isDir(index), bool(checked))
            return True
        return super().setData(index, value, role)


class FileBrowser(QWidget):
    toggled = Signal(str, bool, bool)
    expandRequested = Signal()

    def __init__(self, state_fn, settings, allow_expand=True, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.current = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, T.gap, 0, 0)
        lay.setSpacing(T.gap)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.places_btn = icon_button("home", "קיצורי דרך", bordered=True)
        self.places_menu = QMenu(self)
        self.places_menu.aboutToShow.connect(self._fill_places)
        self.places_btn.setMenu(self.places_menu)
        self.places_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.up_btn = icon_button("up-folder", "תיקייה אחת למעלה", bordered=True)
        self.up_btn.clicked.connect(self._go_up)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("הקלידו או הדביקו נתיב ולחצו Enter")
        self.path_edit.setLayoutDirection(Qt.LeftToRight)
        T.sized(self.path_edit, h="h_ctl")
        self.path_edit.returnPressed.connect(lambda: self.reveal(self.path_edit.text().strip().strip('"')))
        row.addWidget(self.places_btn)
        row.addWidget(self.up_btn)
        row.addWidget(self.path_edit, 1)
        self.expand_btn = icon_button("expand", "פתח בחלון גדול", bordered=True)
        self.expand_btn.clicked.connect(self.expandRequested)
        self.expand_btn.setVisible(allow_expand)
        row.addWidget(self.expand_btn)
        lay.addLayout(row)

        self._target = ""
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(40)
        self._scroll_timer.timeout.connect(self._scroll_to_target)
        self.model = CheckableFsModel(state_fn, self)
        self.model.toggled.connect(self.toggled)
        self.model.directoryLoaded.connect(self._dir_loaded)
        self.model.setRootPath("")                 # כל הכוננים (בחלונות) / שורש (במערכות אחרות)
        self.view = QTreeView()
        self.view.setModel(self.model)
        for c in range(1, self.model.columnCount()):
            self.view.hideColumn(c)
        self.view.setHeaderHidden(True)
        self.view.setUniformRowHeights(True)
        self.view.setIndentation(T.icon + 2)
        self.view.setIconSize(QSize(T.icon, T.icon))
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setTextElideMode(Qt.ElideMiddle)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.header().setStretchLastSection(False)
        self.view.header().setSectionResizeMode(0, self.view.header().ResizeMode.ResizeToContents)
        self.view.doubleClicked.connect(self._double_clicked)
        self.view.clicked.connect(self._clicked)
        self.view.verticalScrollBar().actionTriggered.connect(lambda _: setattr(self, "_target", ""))
        lay.addWidget(self.view, 1)

        hint = QLabel("סמנו ✓ ליד תיקייה (כולל כל תתי־התיקיות שבה) או ליד מסמך כדי להוסיף לסל. ביטול הסימון מוציא מהסל.")
        hint.setObjectName("caption")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        completer = QCompleter(self)
        cm = QFileSystemModel(completer)
        cm.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Drives)
        cm.setRootPath("")
        completer.setModel(cm)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.path_edit.setCompleter(completer)

        start = self.settings.value("browse_dir", "") or self.settings.value("last_dir", "")
        if not start or not os.path.isdir(str(start)):
            start = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
        QTimer.singleShot(0, lambda: self.reveal(str(start)))

    # ----- ניווט -----
    def reveal(self, path: str, select: bool = True) -> bool:
        """פותח את העץ עד הנתיב ומגלל אליו. הטעינה של תיקיות אסינכרונית, אז הגלילה מתעדכנת
        כל עוד המשתמש לא גלל בעצמו."""
        if not path:
            return False
        path = os.path.abspath(path)
        if not os.path.exists(path):
            self.path_edit.setStyleSheet("QLineEdit { border-color: #c0262d; }")
            QTimer.singleShot(1200, lambda: self.path_edit.setStyleSheet(""))
            return False
        idx = self.model.index(path)
        if not idx.isValid():
            return False
        self._target = path
        self._expand_chain(idx)
        if select:
            self.view.setCurrentIndex(idx)
        self._scroll_timer.start(0)
        for ms in (120, 400, 900, 1800):
            QTimer.singleShot(ms, self._scroll_timer.start)
        self.current = path if os.path.isdir(path) else os.path.dirname(path)
        self.path_edit.setText(path.replace("/", os.sep))
        self.settings.setValue("browse_dir", self.current)
        return True

    def _expand_chain(self, idx):
        chain = []
        p = idx
        while p.isValid():
            chain.append(p)
            p = p.parent()
        for i in reversed(chain[1:]):
            self.view.expand(i)
        if self.model.isDir(idx):
            self.view.expand(idx)

    def _dir_loaded(self, loaded: str):
        """תיקייה נטענה: אם היא בדרך אל הנתיב המבוקש – ממשיכים להרחיב ולגלול."""
        target = self._target
        if target and os.path.normcase(target).startswith(os.path.normcase(loaded.rstrip("\\/"))):
            self._scroll_timer.start()

    def _scroll_to_target(self):
        if not self._target:
            return
        idx = self.model.index(self._target)            # מחושב מחדש: המיון משנה אינדקסים
        if idx.isValid():
            self._expand_chain(idx)
            self.view.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)

    def _go_up(self):
        base = self.current or self.path_edit.text()
        parent = os.path.dirname(base.rstrip("\\/"))
        if parent and parent != base:
            self.reveal(parent)

    def _clicked(self, index):
        if index.isValid():
            p = self.model.filePath(index)
            self.current = p if self.model.isDir(index) else os.path.dirname(p)
            self.path_edit.setText(p.replace("/", os.sep))

    def _double_clicked(self, index):
        if index.isValid() and not self.model.isDir(index):
            open_default(self.model.filePath(index))

    def _fill_places(self):
        m = self.places_menu
        m.clear()
        for label, loc in (("שולחן העבודה", QStandardPaths.DesktopLocation), ("המסמכים שלי", QStandardPaths.DocumentsLocation),
                           ("הורדות", QStandardPaths.DownloadLocation), ("תיקיית הבית", QStandardPaths.HomeLocation)):
            p = QStandardPaths.writableLocation(loc)
            if p and os.path.isdir(p):
                m.addAction(ui_icon("folder"), label, lambda p=p: self.reveal(p))
        drives = [d.absoluteFilePath() for d in QDir.drives()]
        if drives:
            m.addSeparator()
            for d in drives:
                m.addAction(ui_icon("drive"), f"כונן {ltr(d)}", lambda d=d: self.reveal(d))
        recent = [d for d in (self.settings.value("recent_dirs", [], list) or []) if os.path.isdir(d)]
        if recent:
            m.addSeparator()
            for d in recent[:8]:
                m.addAction(ui_icon("folder"), ltr(short_path(d, 46)), lambda d=d: self.reveal(d))
        m.addSeparator()
        m.addAction(ui_icon("folder-plus"), "בחירת תיקייה אחרת…", self._choose)

    def _choose(self):
        d = QFileDialog.getExistingDirectory(self, "בחירת תיקייה", self.current or "")
        if d:
            self.reveal(d)

    def refresh(self):
        self.view.viewport().update()

    def retheme(self):
        self.view.setIndentation(T.icon + 2)
        self.view.setIconSize(QSize(T.icon, T.icon))


class BrowserDialog(QDialog):
    """אותו עץ בחלון גדול, לבחירה נוחה של הרבה תיקיות."""

    def __init__(self, state_fn, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("בחירת תיקיות ומסמכים לסל")
        screen = (parent.screen() if parent is not None else QApplication.primaryScreen()).availableGeometry()
        self.resize(min(760, int(screen.width() * 0.7)), min(720, int(screen.height() * 0.8)))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.pad, T.pad, T.pad, T.pad)
        self.browser = FileBrowser(state_fn, settings, allow_expand=False)
        lay.addWidget(self.browser, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        done = QPushButton("סיום")
        done.setObjectName("primary")
        done.clicked.connect(self.accept)
        row.addWidget(done)
        lay.addLayout(row)
