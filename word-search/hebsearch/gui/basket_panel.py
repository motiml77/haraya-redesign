"""לוח הסלים: רשימת הסלים השמורים, ותוכן מלא של הסל הנבחר."""

import os

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QProgressBar, QPushButton,
    QSplitter, QStyle, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..index import _key, is_supported
from ..opener import open_default, reveal_in_folder
from .icons import doc_kind, file_icon
from .results import doc_name, ltr, short_path

ROLE_PATH = Qt.UserRole
ROLE_KIND = Qt.UserRole + 1     # folder / file / child

C_OK, C_PENDING, C_BAD, C_OFF = "#15803d", "#64748b", "#b45309", "#94a3b8"


def _title(text):
    lab = QLabel(text)
    lab.setObjectName("title")
    return lab


class DropTree(QTreeWidget):
    dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.dropped.emit(paths)


class BasketPanel(QFrame):
    contentsChanged = Signal()     # תוכן סל השתנה – צריך לסרוק/לעדכן מפה
    basketsChanged = Signal()      # סל נוסף / נמחק / שונה שמו
    currentChanged = Signal(int)

    def __init__(self, db, settings: QSettings):
        super().__init__()
        self.setObjectName("panel")
        self.db, self.settings = db, settings
        self.data = {}        # מזהה_סל → (רשומות, קבצים) מהסריקה האחרונה
        self.status = {}      # נתיב → (מצב, הודעה, מזהה)
        self._filling = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 10)
        lay.setSpacing(6)
        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        lay.addWidget(split, 1)

        # ---- הסלים ----
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(_title("🧺 הסלים שלי"))
        row.addStretch(1)
        for text, tip, slot in (("＋ סל חדש", "יצירת סל חדש", self.new_basket),
                                ("✎", "שינוי שם הסל", self.rename_basket),
                                ("🗑", "מחיקת הסל (המסמכים עצמם לא נמחקים)", self.delete_basket)):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            row.addWidget(b)
        tl.addLayout(row)
        self.basket_list = QListWidget()
        self.basket_list.setObjectName("baskets")
        self.basket_list.currentRowChanged.connect(self._current_changed)
        self.basket_list.itemDoubleClicked.connect(lambda _: self.rename_basket())
        tl.addWidget(self.basket_list)
        split.addWidget(top)

        # ---- תוכן הסל ----
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 6, 0, 0)
        bl.setSpacing(6)
        self.contents_title = _title("תוכן הסל")
        bl.addWidget(self.contents_title)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("🔍 סינון לפי שם מסמך…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)
        bl.addWidget(self.filter_edit)

        self.tree = DropTree()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["מסמך", "מצב"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setStretchLastSection(False)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemChanged.connect(self._item_changed)
        self.tree.itemDoubleClicked.connect(self._item_open)
        self.tree.dropped.connect(self.add_paths)
        bl.addWidget(self.tree, 1)

        row = QHBoxLayout()
        self.add_folder_btn = QToolButton()
        self.add_folder_btn.setText("📁 הוסף תיקייה")
        self.add_folder_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.add_folder_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.add_folder_btn.setObjectName("button")
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.recent_menu = QMenu(self)
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        self.add_folder_btn.setMenu(self.recent_menu)
        add_files = QPushButton("📄 הוסף מסמכים")
        add_files.clicked.connect(self.add_files)
        remove = QPushButton("הסר")
        remove.setToolTip("הסרת הפריטים המסומנים מהסל")
        remove.clicked.connect(self.remove_selected)
        row.addWidget(self.add_folder_btn, 1)
        row.addWidget(add_files, 1)
        row.addWidget(remove)
        bl.addLayout(row)

        self.summary = QLabel()
        self.summary.setObjectName("muted")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        self.summary.linkActivated.connect(lambda _: self._show_problems())
        bl.addWidget(self.summary)
        split.addWidget(bottom)
        split.setSizes([170, 520])

        # ---- התקדמות ----
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        lay.addWidget(self.progress)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("muted")
        self.progress_label.setWordWrap(True)
        lay.addWidget(self.progress_label)
        row = QHBoxLayout()
        self.update_btn = QPushButton("🔄 עדכן מפת חיפוש")
        self.update_btn.setToolTip("קורא מחדש מסמכים שנוספו או השתנו מאז הפעם הקודמת")
        self.cancel_btn = QPushButton("עצור")
        self.cancel_btn.hide()
        row.addWidget(self.update_btn, 1)
        row.addWidget(self.cancel_btn)
        lay.addLayout(row)

        self.reload_baskets()

    # ================= הסלים =================
    @property
    def current_id(self):
        it = self.basket_list.currentItem()
        return it.data(ROLE_PATH) if it else None

    def reload_baskets(self, select_id=None):
        baskets = self.db.baskets()
        if not baskets:
            self.db.create_basket("הסל שלי")
            baskets = self.db.baskets()
        if select_id is None:
            select_id = self.current_id or int(self.settings.value("basket", baskets[0][0]))
        self.basket_list.blockSignals(True)
        self.basket_list.clear()
        row = 0
        for i, (bid, name, count) in enumerate(baskets):
            it = QListWidgetItem(f"{name}\n{count:,} מסמכים" if count != 1 else f"{name}\nמסמך אחד")
            it.setData(ROLE_PATH, bid)
            it.setData(ROLE_KIND, name)
            self.basket_list.addItem(it)
            if bid == select_id:
                row = i
        self.basket_list.setCurrentRow(row)
        self.basket_list.blockSignals(False)
        self._refresh_contents()

    def basket_names(self):
        return [(bid, name, count) for bid, name, count in self.db.baskets()]

    def _current_changed(self, _row):
        if self.current_id is not None:
            self.settings.setValue("basket", self.current_id)
            self._refresh_contents()
            self.currentChanged.emit(self.current_id)

    def new_basket(self):
        name, ok = QInputDialog.getText(self, "סל חדש", "שם הסל (למשל: שיעורים, תורה, מכתבים):")
        if ok and name.strip():
            try:
                bid = self.db.create_basket(name.strip())
            except Exception:
                QMessageBox.warning(self, "סל חדש", "כבר קיים סל בשם הזה.")
                return
            self.reload_baskets(bid)
            self.basketsChanged.emit()
            self.add_folder()

    def rename_basket(self):
        it = self.basket_list.currentItem()
        if not it:
            return
        name, ok = QInputDialog.getText(self, "שינוי שם", "שם חדש לסל:", text=it.data(ROLE_KIND))
        if ok and name.strip():
            try:
                self.db.rename_basket(self.current_id, name.strip())
            except Exception:
                QMessageBox.warning(self, "שינוי שם", "כבר קיים סל בשם הזה.")
                return
            self.reload_baskets(self.current_id)
            self.basketsChanged.emit()

    def delete_basket(self):
        it = self.basket_list.currentItem()
        if not it:
            return
        if QMessageBox.question(self, "מחיקת סל", f"למחוק את הסל '{it.data(ROLE_KIND)}'?\n"
                                "(המסמכים עצמם לא יימחקו)") == QMessageBox.Yes:
            self.db.delete_basket(self.current_id)
            self.data.pop(self.current_id, None)
            self.basket_list.setCurrentRow(-1)
            self.reload_baskets()
            self.basketsChanged.emit()

    # ================= הוספה והסרה =================
    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "בחירת תיקייה לסל", self.settings.value("last_dir", ""))
        if d:
            self.add_paths([d])

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "בחירת מסמכים לסל", self.settings.value("last_dir", ""),
            "מסמכים (*.docx *.docm *.dotx *.doc *.rtf *.pdf);;מסמכי וורד (*.docx *.doc);;PDF (*.pdf)")
        if files:
            self.add_paths(files)

    def _fill_recent(self):
        self.recent_menu.clear()
        recent = [d for d in (self.settings.value("recent_dirs", [], list) or []) if os.path.isdir(d)]
        if not recent:
            a = self.recent_menu.addAction("אין תיקיות אחרונות")
            a.setEnabled(False)
        for d in recent:
            a = self.recent_menu.addAction(self.style().standardIcon(QStyle.SP_DirIcon), short_path(d, 60))
            a.setToolTip(d)
            a.triggered.connect(lambda _=False, d=d: self.add_paths([d]))

    def _remember_dir(self, d):
        recent = [x for x in (self.settings.value("recent_dirs", [], list) or []) if x != d]
        self.settings.setValue("recent_dirs", [d] + recent[:9])
        self.settings.setValue("last_dir", d)

    def add_paths(self, paths):
        items = []
        for p in paths:
            if os.path.isdir(p):
                items.append((p, "folder"))
                self._remember_dir(p)
            elif os.path.isfile(p) and is_supported(p):
                items.append((p, "file"))
                self.settings.setValue("last_dir", os.path.dirname(p))
        if not items:
            QMessageBox.information(self, "הוספה לסל", "לא נמצאו מסמכי וורד או PDF להוספה.")
            return
        self.db.add_basket_items(self.current_id, items)
        self._refresh_contents()
        self.contentsChanged.emit()

    def remove_selected(self):
        tops = []
        for it in self.tree.selectedItems():
            if it.parent() is None:
                tops.append(it.data(0, ROLE_PATH))
            else:
                self.db.set_excluded(self.current_id, it.data(0, ROLE_PATH), True)
        if tops:
            self.db.remove_basket_items(self.current_id, tops)
        self._refresh_contents()
        self.contentsChanged.emit()

    # ================= תצוגת התוכן =================
    def set_scan(self, baskets, status):
        """מקבל את תוצאות הסריקה האחרונה (מהעבודה ברקע)."""
        self.data.update(baskets)
        self.status.update(status)
        self.reload_baskets(self.current_id)

    def _status_cell(self, item, path, excluded):
        if excluded:
            item.setText(1, "מוחרג")
            item.setForeground(1, QBrush(QColor(C_OFF)))
            item.setForeground(0, QBrush(QColor(C_OFF)))
            return "off"
        st = self.status.get(path)
        if st is None:
            item.setText(1, "ממתין")
            item.setForeground(1, QBrush(QColor(C_PENDING)))
            return "pending"
        if st[0] == "ok":
            item.setText(1, "✓")
            item.setForeground(1, QBrush(QColor(C_OK)))
            item.setToolTip(1, "נקרא ונכלל במפת החיפוש")
            return "ok"
        item.setText(1, "⚠ לא נקרא")
        item.setForeground(1, QBrush(QColor(C_BAD)))
        item.setToolTip(1, st[1] or "")
        return "bad"

    def _refresh_contents(self):
        bid = self.current_id
        if bid is None:
            return
        name = self.basket_list.currentItem().data(ROLE_KIND)
        self.contents_title.setText(f"תוכן הסל: {name}")
        items = self.db.basket_items(bid)
        excluded = {_key(p) for p, k in items if k == "exclude"}
        scanned = {e[0]: e[2] for e in self.data.get(bid, ([], []))[0]}
        expanded = {self.tree.topLevelItem(i).data(0, ROLE_PATH)
                    for i in range(self.tree.topLevelItemCount()) if self.tree.topLevelItem(i).isExpanded()}

        total_children = sum(len(v) for v in scanned.values())
        self._filling = True
        self.tree.clear()
        counts = {"ok": 0, "pending": 0, "bad": 0, "off": 0}
        kinds = {"word": 0, "pdf": 0, "doc": 0}
        seen = set()
        folder_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        for path, kind in items:
            if kind == "exclude":
                continue
            top = QTreeWidgetItem()
            top.setData(0, ROLE_PATH, path)
            top.setData(0, ROLE_KIND, kind)
            top.setToolTip(0, path)
            if kind == "folder":
                top.setIcon(0, folder_icon)
                children = scanned.get(path)
                top.setText(0, os.path.basename(path.rstrip("\\/")) or path)
                if children is None:
                    top.setText(1, "סורק…")
                else:
                    top.setText(1, f"{len(children):,}")
                    top.setToolTip(1, f"{len(children):,} מסמכים בתיקייה")
                    for f in children:
                        rel = os.path.relpath(os.path.dirname(f), path)
                        label = doc_name(f) if rel == "." else f"{doc_name(f)}  ‹{rel}›"
                        ch = QTreeWidgetItem([label])
                        ch.setIcon(0, file_icon(f))
                        ch.setToolTip(0, f)
                        ch.setData(0, ROLE_PATH, f)
                        ch.setData(0, ROLE_KIND, "child")
                        off = _key(f) in excluded
                        ch.setFlags(ch.flags() | Qt.ItemIsUserCheckable)
                        ch.setCheckState(0, Qt.Unchecked if off else Qt.Checked)
                        state = self._status_cell(ch, f, off)
                        if _key(f) not in seen:
                            seen.add(_key(f))
                            counts[state] += 1
                            if not off:
                                kinds[doc_kind(f)] += 1
                        top.addChild(ch)
            else:
                top.setText(0, doc_name(path))
                top.setIcon(0, file_icon(path))
                state = self._status_cell(top, path, False)
                if _key(path) not in seen:
                    seen.add(_key(path))
                    counts[state] += 1
                    kinds[doc_kind(path)] += 1
            self.tree.addTopLevelItem(top)
            if kind == "folder":
                # סלים קטנים-בינוניים נפתחים במלואם כדי לראות את כל הרשימה
                top.setExpanded(path in expanded or total_children <= 300)
        self._filling = False
        self._apply_filter(self.filter_edit.text())

        if not items:
            self.summary.setText("הסל ריק. הוסיפו תיקיות או מסמכים – או גררו אותם לכאן מהסייר.")
            return
        active = counts["ok"] + counts["pending"] + counts["bad"]
        parts = [f"<b>{active:,}</b> מסמכים"]
        names = {"word": "וורד", "pdf": "PDF", "doc": "doc ישן"}
        # סימן RLM שומר את הסדר הנכון כשמילה לועזית צמודה למפריד
        parts += [f"{n:,} {ltr(names[k])}\u200f" for k, n in kinds.items() if n]
        if counts["off"]:
            parts.append(f"{counts['off']:,} מוחרגים")
        if counts["pending"]:
            parts.append(f"{counts['pending']:,} ממתינים לקריאה")
        if counts["bad"]:
            parts.append(f'<a href="p" style="color:{C_BAD}">{counts["bad"]:,} לא נקראו</a>')
        self.summary.setText(" · ".join(parts))

    def _apply_filter(self, text):
        text = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            any_child = False
            for j in range(top.childCount()):
                ch = top.child(j)
                hide = bool(text) and text not in ch.text(0).lower()
                ch.setHidden(hide)
                any_child |= not hide
            own = not text or text in top.text(0).lower()
            top.setHidden(not (own or any_child))
            if text and any_child:
                top.setExpanded(True)

    def _item_changed(self, item, column):
        if self._filling or column != 0 or item.data(0, ROLE_KIND) != "child":
            return
        excluded = item.checkState(0) != Qt.Checked
        self.db.set_excluded(self.current_id, item.data(0, ROLE_PATH), excluded)
        self._filling = True
        self._status_cell(item, item.data(0, ROLE_PATH), excluded)
        if not excluded:
            item.setForeground(0, QBrush())
        self._filling = False
        self.contentsChanged.emit()

    def _item_open(self, item, _col):
        if item.data(0, ROLE_KIND) != "folder":
            open_default(item.data(0, ROLE_PATH))

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        path, kind = item.data(0, ROLE_PATH), item.data(0, ROLE_KIND)
        menu = QMenu(self)
        if kind != "folder":
            menu.addAction("פתח את המסמך", lambda: open_default(path))
        menu.addAction("הצג בתיקייה", lambda: reveal_in_folder(path))
        menu.addSeparator()
        if kind == "child":
            on = item.checkState(0) == Qt.Checked
            menu.addAction("החרג מהחיפוש" if on else "החזר לחיפוש",
                           lambda: item.setCheckState(0, Qt.Unchecked if on else Qt.Checked))
        else:
            act = QAction("הסר מהסל", menu)
            act.triggered.connect(lambda: (self.tree.clearSelection(), item.setSelected(True),
                                           self.remove_selected()))
            menu.addAction(act)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _show_problems(self):
        bid = self.current_id
        files = self.data.get(bid, ([], []))[1]
        bad = [(f, self.status[f][1]) for f in files if f in self.status and self.status[f][0] != "ok"]
        lines = [f"• {doc_name(p)} – {m}" for p, m in bad[:40]]
        if len(bad) > 40:
            lines.append(f"… ועוד {len(bad) - 40}")
        QMessageBox.information(self, "מסמכים שלא נקראו", "\n".join(lines) or "אין")
