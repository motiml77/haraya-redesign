"""לוח הסלים (סרגל הצד).

מבנה (העץ תופס את כל הגובה הפנוי; כל השאר קומפקטי):
    [ בורר הסל ▾ ] [＋] [⋯]
    ┌ תוכן הסל │ בחירה מהמחשב ┐
    │  עץ מלא בגובה הסרגל      │
    └───────────────────────────┘
    שורת סיכום · כפתור עדכון / התקדמות

"""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings, QSize, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu,
    QMessageBox, QProgressBar, QPushButton, QSizePolicy, QStackedWidget, QTabWidget, QToolButton, QTreeView,
    QVBoxLayout, QWidget,
)

from ..basket import BasketEditor
from ..index import is_supported
from ..opener import open_default, reveal_in_folder
from .basket_model import BasketModel
from .file_browser import BrowserDialog, FileBrowser
from .icons import doc_kind, ui_icon
from .results import doc_name, ltr
from .theme import C, T
from .widgets import Combo, ElidedLabel, icon_button


class BasketTree(QTreeView):
    """עץ תוכן הסל; מקבל גרירת קבצים ותיקיות מהסייר."""
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
    contentsChanged = Signal()      # תוכן סל השתנה – צריך לסרוק/לעדכן מפה
    basketsChanged = Signal()       # סל נוסף / נמחק / שונה שמו
    currentChanged = Signal(int)
    updateRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, db, settings: QSettings):
        super().__init__()
        self.setObjectName("panel")
        self.db, self.settings = db, settings
        self.scan = None
        self.editor = BasketEditor(db, None)
        self.model = BasketModel(self.editor, self._status_of)
        self.model.toggled.connect(self._tree_toggled)
        self._signature = None
        self._expanded = {}
        self._dialog = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.pad, T.pad, T.pad, T.pad)
        lay.setSpacing(T.gap)

        # ---- בורר הסל ----
        row = QHBoxLayout()
        row.setSpacing(4)
        self.basket_combo = Combo()
        self.basket_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.basket_combo.setToolTip("הסל שעורכים כעת (לבחירת סלים לחיפוש – השתמשו בתגיות שליד שורת החיפוש)")
        self.basket_combo.currentIndexChanged.connect(self._basket_changed)
        self.new_btn = icon_button("plus", "סל חדש", bordered=True)
        self.new_btn.clicked.connect(self.new_basket)
        self.more_btn = icon_button("more", "שינוי שם / מחיקת הסל", bordered=True)
        menu = QMenu(self)
        menu.addAction(ui_icon("pencil"), "שינוי שם הסל…", self.rename_basket)
        menu.addAction(ui_icon("trash"), "מחיקת הסל…", self.delete_basket)
        self.more_btn.setMenu(menu)
        self.more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        row.addWidget(self.basket_combo, 1)
        row.addWidget(self.new_btn)
        row.addWidget(self.more_btn)
        lay.addLayout(row)

        # ---- לשוניות ----
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        lay.addWidget(self.tabs, 1)

        # תוכן הסל
        contents = QWidget()
        cl = QVBoxLayout(contents)
        cl.setContentsMargins(0, T.gap, 0, 0)
        cl.setSpacing(T.gap)
        tool = QHBoxLayout()
        tool.setSpacing(4)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("סינון לפי שם…")
        self.filter_edit.addAction(ui_icon("search", C.muted, C.muted), QLineEdit.LeadingPosition)
        self.filter_edit.setClearButtonEnabled(True)
        T.sized(self.filter_edit, h="h_ctl")
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_filter)
        self.filter_edit.textChanged.connect(lambda _: self._filter_timer.start(180))
        self.add_folder_btn = icon_button("folder-plus", "הוספת תיקייה לסל", bordered=True)
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.add_files_btn = icon_button("file-plus", "הוספת מסמכים לסל", bordered=True)
        self.add_files_btn.clicked.connect(self.add_files)
        self.remove_btn = icon_button("trash", "הסרת הפריטים המסומנים מהסל", bordered=True)
        self.remove_btn.clicked.connect(self.remove_selected)
        tool.addWidget(self.filter_edit, 1)
        tool.addWidget(self.add_folder_btn)
        tool.addWidget(self.add_files_btn)
        tool.addWidget(self.remove_btn)
        cl.addLayout(tool)

        self.stack = QStackedWidget()
        self.tree = BasketTree()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setIndentation(T.icon + 2)
        self.tree.setIconSize(QSize(T.icon, T.icon))
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.setTextElideMode(Qt.ElideMiddle)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.doubleClicked.connect(self._double_clicked)
        self.tree.dropped.connect(self.add_paths)
        hdr = self.tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, hdr.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, hdr.ResizeMode.Fixed)
        hdr.resizeSection(1, T.pad * 7)
        self.stack.addWidget(self.tree)

        empty = QWidget()
        el = QVBoxLayout(empty)
        el.setContentsMargins(T.pad, T.pad * 2, T.pad, T.pad)
        el.addStretch(1)
        ic = QLabel()
        ic.setPixmap(ui_icon("folder-plus", C.border_strong).pixmap(48, 48))
        ic.setAlignment(Qt.AlignCenter)
        el.addWidget(ic)
        t = QLabel("הסל ריק")
        t.setObjectName("title")
        t.setAlignment(Qt.AlignCenter)
        el.addWidget(t)
        d = QLabel("הוסיפו תיקיות או מסמכי Word ו-PDF. אפשר גם לגרור אותם לכאן מהסייר.")
        d.setObjectName("muted")
        d.setAlignment(Qt.AlignCenter)
        d.setWordWrap(True)
        el.addWidget(d)
        b1 = QPushButton("בחירה מהמחשב")
        b1.setObjectName("primary")
        b1.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        b2 = QPushButton("הוספת תיקייה…")
        b2.clicked.connect(self.add_folder)
        el.addWidget(b1, 0, Qt.AlignHCenter)
        el.addWidget(b2, 0, Qt.AlignHCenter)
        el.addStretch(2)
        self.empty_page = empty
        self.stack.addWidget(empty)
        cl.addWidget(self.stack, 1)
        self.tabs.addTab(contents, ui_icon("folder"), "תוכן הסל")

        # בחירה מהמחשב
        self.browser = FileBrowser(lambda p, d: self.editor.state(p, d), settings)
        self.browser.toggled.connect(self._browser_toggled)
        self.browser.expandRequested.connect(self._open_dialog)
        self.tabs.addTab(self.browser, ui_icon("search"), "בחירה מהמחשב")

        # ---- שוליים: סיכום + עדכון/התקדמות ----
        self.summary = QLabel()
        self.summary.setObjectName("caption")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        self.summary.linkActivated.connect(lambda _: self._show_problems())
        lay.addWidget(self.summary)
        self.bottom = QStackedWidget()
        self.update_btn = QPushButton(" עדכון מפת החיפוש")
        self.update_btn.setIcon(ui_icon("refresh"))
        self.update_btn.setToolTip("קורא מחדש מסמכים שנוספו או השתנו (בדרך כלל זה קורה לבד)")
        self.update_btn.clicked.connect(self.updateRequested)
        self.bottom.addWidget(self.update_btn)
        prog = QWidget()
        pl = QVBoxLayout(prog)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(3)
        top = QHBoxLayout()
        self.progress_title = QLabel("")
        self.progress_title.setObjectName("summary")
        self.cancel_btn = QPushButton("עצור")
        self.cancel_btn.setObjectName("flat")
        self.cancel_btn.clicked.connect(self.cancelRequested)
        top.addWidget(self.progress_title, 1)
        top.addWidget(self.cancel_btn)
        pl.addLayout(top)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        pl.addWidget(self.progress)
        self.progress_detail = ElidedLabel("", Qt.ElideMiddle)
        self.progress_detail.setObjectName("caption")
        pl.addWidget(self.progress_detail)
        self.bottom.addWidget(prog)
        lay.addWidget(self.bottom)

        self.reload_baskets()

    # ================================================================ מצב
    def _status_of(self, path):
        return self.scan.status.get(path) if self.scan else None

    @property
    def current_id(self):
        return self.basket_combo.currentData()

    def basket_items(self):
        return self.db.basket_items(self.current_id) if self.current_id is not None else []

    def retheme(self):
        self.tree.setIndentation(T.icon + 2)
        self.tree.setIconSize(QSize(T.icon, T.icon))
        self.tree.header().resizeSection(1, T.pad * 7)
        self.browser.retheme()

    # ================================================================ סלים
    def reload_baskets(self, select_id=None):
        baskets = self.db.baskets()
        if not baskets:
            self.db.create_basket("הסל שלי")
            baskets = self.db.baskets()
        if select_id is None:
            select_id = self.current_id or int(self.settings.value("basket", baskets[0][0]))
        self.basket_combo.blockSignals(True)
        self.basket_combo.clear()
        row = 0
        for i, (bid, name, count) in enumerate(baskets):
            label = f"{name}  ·  {count:,}" if count else name
            self.basket_combo.addItem(label, bid)
            self.basket_combo.setItemData(i, name, Qt.UserRole + 1)
            if bid == select_id:
                row = i
        self.basket_combo.setCurrentIndex(row)
        self.basket_combo.blockSignals(False)
        self.editor.basket_id = self.current_id
        self._refresh(force=True)

    def _basket_name(self):
        return self.basket_combo.currentData(Qt.UserRole + 1) or ""

    def _basket_changed(self):
        if self.current_id is None:
            return
        self.settings.setValue("basket", self.current_id)
        self.editor.basket_id = self.current_id
        self._refresh(force=True)
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
            self.tabs.setCurrentIndex(1)

    def rename_basket(self):
        if self.current_id is None:
            return
        name, ok = QInputDialog.getText(self, "שינוי שם", "שם חדש לסל:", text=self._basket_name())
        if ok and name.strip():
            try:
                self.db.rename_basket(self.current_id, name.strip())
            except Exception:
                QMessageBox.warning(self, "שינוי שם", "כבר קיים סל בשם הזה.")
                return
            self.reload_baskets(self.current_id)
            self.basketsChanged.emit()

    def delete_basket(self):
        if self.current_id is None:
            return
        if QMessageBox.question(self, "מחיקת סל", f"למחוק את הסל '{self._basket_name()}'?\n"
                                "(המסמכים עצמם לא יימחקו)") == QMessageBox.Yes:
            self.db.delete_basket(self.current_id)
            self.basket_combo.setCurrentIndex(-1)
            self.reload_baskets()
            self.basketsChanged.emit()

    # ================================================================ הוספה והסרה
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
        self._changed(structure=True)

    def remove_selected(self):
        """פריטי סל מוסרים; מסמך או תת-תיקייה שבתוך תיקייה – מוחרגים."""
        nodes = [self.model.node_at(i) for i in self.tree.selectionModel().selectedRows(0)]
        nodes = [n for n in nodes if n is not None]
        tops = [n.path for n in nodes if n.kind in ("top", "single")]
        if tops:
            self.db.remove_basket_items(self.current_id, tops)
        self.editor.reload()
        for n in nodes:
            if n.kind in ("dir", "file"):
                self.editor.set_checked(n.path, n.kind == "dir", False)
        self._changed(structure=bool(tops))

    def _tree_toggled(self, path, is_dir, checked):
        self.editor.set_checked(path, is_dir, checked)
        self._changed()

    def _browser_toggled(self, path, is_dir, checked):
        if checked and is_dir and os.path.dirname(path.rstrip("\\/")) == path.rstrip("\\/"):
            if QMessageBox.question(self, "כונן שלם", "זה יוסיף לסל את כל הכונן, ועלול לקחת זמן רב וליצור מפה גדולה מאוד.\n"
                                    "להמשיך?") != QMessageBox.Yes:
                self.browser.refresh()
                return
        self.editor.set_checked(path, is_dir, checked)
        if checked and is_dir:
            self._remember_dir(path)
        self._changed(structure=True)

    def _changed(self, structure=False):
        """שינוי בתוכן הסל. structure=True: נוספו/הוסרו פריטים בסל (צריך לבנות את העץ מחדש)."""
        self.editor.reload()
        self._refresh(force=structure)
        self.browser.refresh()
        if self._dialog is not None:
            self._dialog.browser.refresh()
        self.contentsChanged.emit()

    def _open_dialog(self):
        self._dialog = BrowserDialog(lambda p, d: self.editor.state(p, d), self.settings, self.window())
        self._dialog.browser.toggled.connect(self._browser_toggled)
        self._dialog.browser.reveal(self.browser.current or self.settings.value("browse_dir", ""))
        self._dialog.exec()
        self._dialog = None
        self.browser.refresh()

    # ================================================================ תצוגה
    def set_scan(self, scan):
        self.scan = scan
        self._refresh()

    def _apply_filter(self):
        text = self.filter_edit.text()
        self.model.apply_filter(text)
        if text.strip():
            self.tree.expandToDepth(3 if self.model.rowCount() < 40 else 1)
        else:
            self._restore_expanded()

    def _save_expanded(self):
        bid = self.current_id
        if bid is not None and self.model.root.kids:
            self._expanded[bid] = self.model.expanded_keys(self.tree)

    def _restore_expanded(self):
        keys = self._expanded.get(self.current_id)
        total = sum(k.total for k in self.model.root.kids)
        if keys is None and total <= 80:
            self.tree.expandAll()
            return
        self.model.restore_expanded(self.tree, keys or set(), default_open_tops=keys is None)

    def _refresh(self, force=False):
        bid = self.current_id
        if bid is None:
            return
        self.editor.basket_id = bid
        self.editor.reload()
        items = self.db.basket_items(bid)
        entries = self.scan.entries.get(bid, []) if self.scan else []
        signature = (bid, tuple(items), tuple((p, len(files)) for p, _k, files in entries))
        if force or signature != self._signature:
            if self._signature and self._signature[0] == bid:
                self._save_expanded()
            self._signature = signature
            self.model.load(items, entries)
            if not self.filter_edit.text().strip():
                self._restore_expanded()
            else:
                self.tree.expandToDepth(3 if self.model.rowCount() < 40 else 1)
        else:
            self.model.refresh()
        has_items = any(k != "exclude" for _p, k in items)
        self.stack.setCurrentWidget(self.tree if has_items else self.empty_page)
        self.filter_edit.setEnabled(has_items)
        self.remove_btn.setEnabled(has_items)
        self._update_summary(items, entries)
        # הסל בבורר: מספר המסמכים מתעדכן אחרי סריקה
        if self.scan is not None:
            for i, (b, name, count) in enumerate(self.db.baskets()):
                label = f"{name}  ·  {count:,}" if count else name
                if self.basket_combo.itemText(i) != label:
                    self.basket_combo.setItemText(i, label)

    def _update_summary(self, items, entries):
        if not any(k != "exclude" for _p, k in items):
            self.summary.setText("")
            return
        files = self.scan.files.get(self.current_id) if self.scan else None
        if files is None:
            self.summary.setText("סורק את הסל…")
            return
        status = self.scan.status
        counts = {"ok": 0, "pending": 0, "bad": 0}
        kinds = {"word": 0, "pdf": 0, "doc": 0}
        for f in files:
            st = status.get(f)
            counts["pending" if st is None else ("ok" if st[0] == "ok" else "bad")] += 1
            kinds[doc_kind(f)] += 1
        total_found = sum(len(found) for _p, _k, found in entries)
        excluded = max(0, total_found - len(files))
        parts = [f"<b>{len(files):,}</b> מסמכים"]
        names = {"word": "וורד", "pdf": "PDF", "doc": "doc ישן"}
        parts += [f"{n:,} {ltr(names[k])}‏" for k, n in kinds.items() if n]
        if excluded:
            parts.append(f"{excluded:,} מוחרגים")
        if counts["pending"]:
            parts.append(f"{counts['pending']:,} ממתינים")
        if counts["bad"]:
            parts.append(f'<a href="p" style="color:{C.warn}">{counts["bad"]:,} לא נקראו</a>')
        self.summary.setText(" · ".join(parts))

    def _show_problems(self):
        files = self.scan.files.get(self.current_id, []) if self.scan else []
        bad = [(f, self.scan.status[f][1]) for f in files if f in self.scan.status and self.scan.status[f][0] != "ok"]
        lines = [f"• {doc_name(p)} – {m}" for p, m in bad[:40]]
        if len(bad) > 40:
            lines.append(f"… ועוד {len(bad) - 40}")
        QMessageBox.information(self, "מסמכים שלא נקראו", "\n".join(lines) or "אין")

    # ================================================================ התקדמות
    def show_progress(self, frac, text=""):
        title, _, detail = text.partition("\n")
        pct = f"{int(frac * 100)}% · " if frac is not None and frac >= 0 else ""
        self.progress_title.setText(pct + (title or "מעדכן…"))
        self.progress_detail.setFullText(detail)
        if frac is None or frac < 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(min(1.0, frac) * 1000))
        self.bottom.setCurrentIndex(1)

    def hide_progress(self):
        self.bottom.setCurrentIndex(0)

    # ================================================================ אינטראקציה
    def _double_clicked(self, index):
        node = self.model.node_at(index)
        if node is not None and node.kind in ("file", "single"):
            open_default(node.path)

    def _context_menu(self, pos):
        index = self.tree.indexAt(pos)
        node = self.model.node_at(index)
        if node is None:
            return
        menu = QMenu(self)
        if node.kind in ("file", "single"):
            menu.addAction(ui_icon("external"), "פתח את המסמך", lambda: open_default(node.path))
        menu.addAction(ui_icon("folder"), "הצג בתיקייה", lambda: reveal_in_folder(node.path))
        menu.addSeparator()
        if node.kind in ("dir", "file"):
            on = self.editor.is_included(node.path) if node.kind == "file" else self.model.included_count(node) > 0
            what = "התיקייה" if node.kind == "dir" else "המסמך"
            menu.addAction(ui_icon("x") if on else ui_icon("check"),
                           f"החרג את {what} מהחיפוש" if on else f"החזר את {what} לחיפוש",
                           lambda: self._tree_toggled(node.path, node.kind == "dir", not on))
        else:
            menu.addAction(ui_icon("trash"), "הסר מהסל", self.remove_selected)
        menu.exec(self.tree.viewport().mapToGlobal(pos))
