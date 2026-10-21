"""עיון במחשב: עץ תיקיות ומסמכים עם תיבות סימון שמוסיפות לסל ומוציאות ממנו."""

import os

from PySide6.QtCore import QDir, QModelIndex, QStandardPaths, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFileSystemModel, QHBoxLayout, QLabel, QStyle, QToolButton, QTreeView,
    QVBoxLayout, QWidget,
)

from ..basket import CHECKED, PARTIAL
from ..index import SUPPORTED_EXTS
from ..opener import open_default
from .icons import file_icon
from .results import ltr, short_path

_STATE = {CHECKED: Qt.Checked, PARTIAL: Qt.PartiallyChecked}
NAME_FILTERS = [f"*{e}" for e in sorted(SUPPORTED_EXTS)] + [f"*{e.upper()}" for e in sorted(SUPPORTED_EXTS)]


class CheckableFsModel(QFileSystemModel):
    """מערכת הקבצים, רק תיקיות ומסמכים נתמכים, עם סימון לפי מצב הסל."""
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
                if not path or (not self.isDir(index) and os.path.basename(path).startswith("~$")):
                    return None
                return _STATE.get(self.state_fn(path, self.isDir(index)), Qt.Unchecked)
            if role == Qt.DecorationRole and not self.isDir(index):
                return file_icon(self.filePath(index))
            if role == Qt.DisplayRole and not self.isDir(index):
                # בלי הסיומת הלטינית, שמשבשת שמות בעברית (האייקון מראה אם זה Word או PDF)
                return os.path.splitext(self.fileName(index))[0]
            if role == Qt.ToolTipRole:
                return self.filePath(index)
        return super().data(index, role)

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.CheckStateRole and index.column() == 0:
            checked = value in (Qt.Checked, Qt.Checked.value, 2)
            self.toggled.emit(self.filePath(index), self.isDir(index), checked)
            return True
        return super().setData(index, value, role)


class FileBrowser(QWidget):
    toggled = Signal(str, bool, bool)

    def __init__(self, state_fn, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(6)

        row = QHBoxLayout()
        self.places = QComboBox()
        self.places.setToolTip("מקומות מהירים")
        self.places.activated.connect(self._place_chosen)
        up = QToolButton()
        up.setText("⬆")
        up.setToolTip("לתיקייה שמעל")
        up.clicked.connect(self._go_up)
        row.addWidget(self.places, 1)
        row.addWidget(up)
        lay.addLayout(row)
        self.path_label = QLabel()
        self.path_label.setObjectName("muted")
        lay.addWidget(self.path_label)

        self.model = CheckableFsModel(state_fn, self)
        self.model.toggled.connect(self.toggled)
        self.view = QTreeView()
        self.view.setModel(self.model)
        for c in range(1, self.model.columnCount()):
            self.view.hideColumn(c)
        self.view.setHeaderHidden(True)
        self.view.setAnimated(True)
        self.view.setUniformRowHeights(True)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.doubleClicked.connect(self._double_clicked)
        lay.addWidget(self.view, 1)

        hint = QLabel("סמנו ✓ תיקייה (כולל כל תתי־התיקיות שבה) או מסמך כדי להוסיף לסל.\n"
                      "ביטול הסימון מוציא מהסל.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        start = self.settings.value("browse_dir", "") or self.settings.value("last_dir", "")
        if not start or not os.path.isdir(start):
            start = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
        self.go(start)

    def _fill_places(self):
        self.places.blockSignals(True)
        self.places.clear()
        dir_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        drive_icon = self.style().standardIcon(QStyle.SP_DriveHDIcon)
        for label, loc in (("שולחן העבודה", QStandardPaths.DesktopLocation),
                           ("המסמכים שלי", QStandardPaths.DocumentsLocation),
                           ("הורדות", QStandardPaths.DownloadLocation),
                           ("תיקיית הבית", QStandardPaths.HomeLocation)):
            p = QStandardPaths.writableLocation(loc)
            if p and os.path.isdir(p):
                self.places.addItem(dir_icon, label, p)
        for d in QDir.drives():
            p = d.absoluteFilePath()
            self.places.addItem(drive_icon, f"כונן {ltr(p)}", p)
        recent = [d for d in (self.settings.value("recent_dirs", [], list) or []) if os.path.isdir(d)]
        if recent:
            self.places.insertSeparator(self.places.count())
            for d in recent[:8]:
                self.places.addItem(dir_icon, ltr(short_path(d, 45)), d)
        self.places.insertSeparator(self.places.count())
        self.places.addItem("בחירת תיקייה אחרת…", "")
        self.places.setCurrentIndex(-1)
        self.places.setPlaceholderText("📂 עבור אל…")
        self.places.blockSignals(False)

    def go(self, path):
        path = os.path.abspath(path)
        self.model.setRootPath(path)
        self.view.setRootIndex(self.model.index(path))
        self.path_label.setText(f"📂 {ltr(short_path(path, 50))}")
        self.path_label.setToolTip(path)
        self.current = path
        self.settings.setValue("browse_dir", path)
        self._fill_places()

    def _place_chosen(self, i):
        p = self.places.itemData(i)
        if p == "":
            p = QFileDialog.getExistingDirectory(self, "בחירת תיקייה", self.current)
        if p:
            self.go(p)

    def _go_up(self):
        parent = os.path.dirname(self.current.rstrip("\\/"))
        if parent and parent != self.current:
            self.go(parent)

    def _double_clicked(self, index: QModelIndex):
        if not self.model.isDir(index):
            open_default(self.model.filePath(index))

    def refresh(self):
        self.view.viewport().update()
