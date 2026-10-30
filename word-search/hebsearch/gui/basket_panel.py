"""סרגל הסלים: כל הסלים ברשימה אחת (כמו תיקיות סביבת עבודה ב-VS Code או אוספים ב-Logos).

    הסלים                              [+ סל חדש]
    [ סינון לפי שם… ]
    ☑ ▾ שיעורים                        1,240     ← הסימון = מחפשים בסל הזה
          ▸ 📁 שיעורי הרב               820
          ＋ הוספה לסל…            ← פותח את עץ המחשב בחלון
    ☐ ▸ תורה                            312
    ───────────────────────────────────────
    ✓ בחיפוש: 1,552 מסמכים · עדכון        (או: מעדכן… 45%  [עצור])

אין בחירה כפולה (סל לעריכה + סלים לחיפוש): כל סל ערוך במקומו, והסימון שלו קובע אם מחפשים בו.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox,
    QProgressBar, QPushButton, QStackedWidget, QTreeView, QVBoxLayout, QWidget,
)

from ..index import is_supported
from ..opener import open_default, reveal_in_folder
from .basket_model import BasketModel
from .file_browser import BrowserDialog
from .icons import doc_kind, ui_icon
from .results import doc_name, ltr
from .theme import C, T
from .widgets import ElidedLabel, WrapLabel, text_icon_button


class BasketTree(QTreeView):
    """עץ הסלים; מקבל גרירת קבצים ותיקיות מהסייר אל הסל שמתחת לעכבר."""
    dropped = Signal(list, object)       # נתיבים, מזהה הסל (או None)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def _basket_at(self, pos):
        node = self.model().node_at(self.indexAt(pos))
        return node.bid if node is not None else None

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            e.acceptProposedAction()
            self.dropped.emit(paths, self._basket_at(e.position().toPoint()))


class BasketPanel(QFrame):
    contentsChanged = Signal()      # תוכן סל השתנה – צריך לסרוק/לעדכן מפה
    basketsChanged = Signal()       # סל נוסף / נמחק / שונה שמו
    scopeChanged = Signal()         # השתנו הסלים שמחפשים בהם
    updateRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, db, settings: QSettings):
        super().__init__()
        self.setObjectName("panel")
        self.db, self.settings = db, settings
        self.scan = None
        self._dialog = None
        self._expanded = None
        self._signature = None
        saved = settings.value("search_baskets", None)
        if saved is None:
            self.search_ids = None                       # בפעם הראשונה – כל הסלים
        else:
            vals = saved if isinstance(saved, list) else [saved]
            self.search_ids = {int(x) for x in vals if str(x).strip().lstrip("-").isdigit()}
        self.model = BasketModel(db, self._status_of)
        self.model.toggled.connect(self._tree_toggled)
        self.model.searchToggled.connect(self._search_toggled)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.pad, T.pad, T.pad, T.pad)
        lay.setSpacing(T.gap)

        # ---- כותרת ----
        head = QHBoxLayout()
        head.setSpacing(4)
        title = QLabel("הסלים")
        title.setObjectName("title")
        self.new_btn = text_icon_button("plus", " סל חדש", "יצירת סל חדש (למשל: שיעורים, תורה, מכתבים)")
        self.new_btn.setObjectName("bordered")
        self.new_btn.clicked.connect(self.new_basket)
        head.addWidget(title, 1)
        head.addWidget(self.new_btn)
        lay.addLayout(head)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("סינון לפי שם תיקייה או מסמך…")
        self.filter_edit.addAction(ui_icon("search", C.muted, C.muted), QLineEdit.LeadingPosition)
        self.filter_edit.setClearButtonEnabled(True)
        T.sized(self.filter_edit, h="h_ctl")
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_filter)
        self.filter_edit.textChanged.connect(lambda _: self._filter_timer.start(180))
        lay.addWidget(self.filter_edit)

        # ---- העץ / מצב ריק ----
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
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.clicked.connect(self._clicked)
        self.tree.doubleClicked.connect(self._double_clicked)
        self.tree.dropped.connect(lambda paths, bid: self.add_paths(paths, bid))
        hdr = self.tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, hdr.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, hdr.ResizeMode.Fixed)
        hdr.resizeSection(1, T.pad * 9)
        self.stack.addWidget(self.tree)
        self.stack.addWidget(self._empty_page())
        lay.addWidget(self.stack, 1)

        # ---- שורת מצב קטנה בתחתית ----
        sep = QFrame()
        sep.setObjectName("separator")
        lay.addWidget(sep)
        self.bottom = QStackedWidget()
        self.status = WrapLabel("")
        self.status.setObjectName("caption")
        self.status.setTextFormat(Qt.RichText)
        self.status.linkActivated.connect(self._status_link)
        self.bottom.addWidget(self.status)
        prog = QWidget()
        pl = QVBoxLayout(prog)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(3)
        top = QHBoxLayout()
        self.progress_title = ElidedLabel("", Qt.ElideRight)
        self.progress_title.setObjectName("caption")
        self.cancel_btn = QPushButton("עצור")
        self.cancel_btn.setObjectName("flat")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        T.sized(self.cancel_btn, h="h_chip")
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

    def _empty_page(self):
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
        d = WrapLabel("הוסיפו תיקיות או מסמכי Word ו-PDF. אפשר גם לגרור אותם לכאן מהסייר.")
        d.setObjectName("muted")
        d.setAlignment(Qt.AlignCenter)
        el.addWidget(d)
        b1 = QPushButton("בחירה מהמחשב…")
        b1.setObjectName("primary")
        b1.setCursor(Qt.PointingHandCursor)
        b1.clicked.connect(lambda: self.open_browser(self._first_basket()))
        b2 = QPushButton("הוספת תיקייה…")
        b2.setCursor(Qt.PointingHandCursor)
        b2.clicked.connect(lambda: self.add_folder(self._first_basket()))
        el.addWidget(b1, 0, Qt.AlignHCenter)
        el.addWidget(b2, 0, Qt.AlignHCenter)
        el.addStretch(2)
        self.empty_page = empty
        return empty

    # ================================================================ מצב
    def _status_of(self, path):
        return self.scan.status.get(path) if self.scan else None

    def _first_basket(self):
        baskets = self.db.baskets()
        return baskets[0][0] if baskets else None

    def retheme(self):
        self.tree.setIndentation(T.icon + 2)
        self.tree.setIconSize(QSize(T.icon, T.icon))
        self.tree.header().resizeSection(1, T.pad * 9)

    def scope(self):
        """[(מזהה, שם, מספר מסמכים)] של הסלים שמחפשים בהם."""
        out = []
        for bid, name, count in self.db.baskets():
            if bid in self.search_ids:
                files = self.scan.files.get(bid) if self.scan else None
                out.append((bid, name, len(files) if files is not None else count))
        return out

    # ================================================================ סלים
    def reload_baskets(self):
        baskets = self.db.baskets()
        if not baskets:
            self.db.create_basket("הסל שלי")
            baskets = self.db.baskets()
        ids = {b[0] for b in baskets}
        if self.search_ids is None:
            self.search_ids = set(ids)
        self.search_ids &= ids
        self.model.search_ids = set(self.search_ids)
        self._refresh(force=True)

    def _save_scope(self):
        self.settings.setValue("search_baskets", sorted(self.search_ids))
        self.model.set_search_ids(self.search_ids)
        self._update_status()
        self.scopeChanged.emit()

    def set_search_ids(self, ids):
        self.search_ids = set(ids)
        self._save_scope()

    def _search_toggled(self, bid, on):
        (self.search_ids.add if on else self.search_ids.discard)(bid)
        self._save_scope()

    def create_basket(self, name):
        """יוצר סל (שנכלל בחיפוש מיד). מחזיר את המזהה, או None אם השם תפוס."""
        try:
            bid = self.db.create_basket(name)
        except Exception:
            return None
        self.search_ids.add(bid)
        self.settings.setValue("search_baskets", sorted(self.search_ids))
        self.model.search_ids = set(self.search_ids)
        self._refresh(force=True)
        self.basketsChanged.emit()
        self.scopeChanged.emit()
        return bid

    def new_basket(self):
        name, ok = QInputDialog.getText(self, "סל חדש", "שם הסל (למשל: שיעורים, תורה, מכתבים):")
        if not (ok and name.strip()):
            return
        bid = self.create_basket(name.strip())
        if bid is None:
            QMessageBox.warning(self, "סל חדש", "כבר קיים סל בשם הזה.")
            return
        self.open_browser(bid)

    def rename_basket(self, bid):
        old = self._name(bid)
        name, ok = QInputDialog.getText(self, "שינוי שם", "שם חדש לסל:", text=old)
        if ok and name.strip() and name.strip() != old:
            try:
                self.db.rename_basket(bid, name.strip())
            except Exception:
                QMessageBox.warning(self, "שינוי שם", "כבר קיים סל בשם הזה.")
                return
            self._refresh(force=True)
            self.basketsChanged.emit()

    def delete_basket(self, bid):
        if QMessageBox.question(self, "מחיקת סל", f"למחוק את הסל '{self._name(bid)}'?\n"
                                "(המסמכים עצמם לא יימחקו)") != QMessageBox.Yes:
            return
        self.db.delete_basket(bid)
        self.search_ids.discard(bid)
        self.reload_baskets()
        self.basketsChanged.emit()
        self.scopeChanged.emit()

    def _name(self, bid):
        return next((n for b, n, _c in self.db.baskets() if b == bid), "")

    # ================================================================ הוספה והסרה
    def add_folder(self, bid):
        if bid is None:
            return
        d = QFileDialog.getExistingDirectory(self, f"הוספת תיקייה לסל '{self._name(bid)}'",
                                             self.settings.value("last_dir", ""))
        if d:
            self.add_paths([d], bid)

    def add_files(self, bid):
        if bid is None:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, f"הוספת מסמכים לסל '{self._name(bid)}'", self.settings.value("last_dir", ""),
            "מסמכים (*.docx *.docm *.dotx *.doc *.rtf *.pdf);;מסמכי וורד (*.docx *.doc);;PDF (*.pdf)")
        if files:
            self.add_paths(files, bid)

    def _remember_dir(self, d):
        recent = [x for x in (self.settings.value("recent_dirs", [], list) or []) if x != d]
        self.settings.setValue("recent_dirs", [d] + recent[:9])
        self.settings.setValue("last_dir", d)

    def add_paths(self, paths, bid=None):
        if bid is None:
            bid = self._target_basket()
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
        self.db.add_basket_items(bid, items)
        self._changed(structure=True)
        idx = self.model.basket_index(bid)
        if idx.isValid():
            self.tree.expand(idx)

    def _target_basket(self):
        """הסל שמסומן בעץ, ואם אין – הראשון שמחפשים בו, ואם אין – הראשון."""
        node = self.model.node_at(self.tree.currentIndex())
        if node is not None:
            return node.bid
        for bid, _n, _c in self.db.baskets():
            if bid in self.search_ids:
                return bid
        return self._first_basket()

    def remove_selected(self):
        """פריטי סל מוסרים; מסמך או תת-תיקייה שבתוך תיקייה – מוחרגים."""
        nodes = [self.model.node_at(i) for i in self.tree.selectionModel().selectedRows(0)]
        nodes = [n for n in nodes if n is not None]
        tops = {}
        for n in nodes:
            if n.kind in ("top", "single"):
                tops.setdefault(n.bid, []).append(n.path)
        for bid, paths in tops.items():
            self.db.remove_basket_items(bid, paths)
        inner = [n for n in nodes if n.kind in ("dir", "file")]
        for n in inner:
            editor = self.model.editors[n.bid]
            editor.reload()
            editor.set_checked(n.path, n.kind == "dir", False)
        if tops or inner:
            self._changed(structure=bool(tops))

    def _tree_toggled(self, bid, path, is_dir, checked):
        editor = self.model.editors[bid]
        editor.reload()
        editor.set_checked(path, is_dir, checked)
        self._changed()

    def _browser_toggled(self, bid, path, is_dir, checked):
        if checked and is_dir and os.path.dirname(path.rstrip("\\/")) == path.rstrip("\\/"):
            if QMessageBox.question(self, "כונן שלם", "זה יוסיף לסל את כל הכונן, ועלול לקחת זמן רב וליצור מפה גדולה מאוד.\n"
                                    "להמשיך?") != QMessageBox.Yes:
                if self._dialog is not None:
                    self._dialog.browser.refresh()
                return
        editor = self.model.editors[bid]
        editor.reload()
        editor.set_checked(path, is_dir, checked)
        if checked and is_dir:
            self._remember_dir(path)
        self._changed(structure=True)
        idx = self.model.basket_index(bid)
        if idx.isValid():
            self.tree.expand(idx)

    def _changed(self, structure=False):
        """שינוי בתוכן סל. structure=True: נוספו/הוסרו פריטים (צריך לבנות את העץ מחדש)."""
        self._refresh(force=structure)
        if self._dialog is not None:
            self._dialog.browser.refresh()
        self.contentsChanged.emit()

    def open_browser(self, bid, modal=True):
        """עץ המחשב בחלון (כמו "שינוי" במיקומי האינדוקס של חלונות): ✓ מוסיף לסל, ביטול מוציא."""
        if bid is None:
            return None
        editor = self.model.editors.get(bid)
        if editor is None:
            self._refresh(force=True)
            editor = self.model.editors[bid]
        dlg = BrowserDialog(lambda p, d: editor.state(p, d), self.settings, self.window())
        dlg.setWindowTitle(f"בחירת תיקיות ומסמכים לסל '{self._name(bid)}'")
        dlg.browser.toggled.connect(lambda p, d, c: self._browser_toggled(bid, p, d, c))
        self._dialog = dlg
        if modal:
            dlg.exec()
            self._dialog = None
        else:
            dlg.show()
        return dlg

    # ================================================================ תצוגה
    def set_scan(self, scan):
        self.scan = scan
        self._refresh()

    def _apply_filter(self):
        text = self.filter_edit.text()
        self.model.apply_filter(text)
        if text.strip():
            self.tree.expandToDepth(4 if sum(len(b.vkids) for b in self.model.root.kids) < 60 else 1)
        else:
            self.model.restore_expanded(self.tree, self._expanded)

    def _refresh(self, force=False):
        baskets = self.db.baskets()
        items_of = {bid: self.db.basket_items(bid) for bid, _n, _c in baskets}
        entries_of = {bid: self.scan.entries.get(bid, []) for bid, _n, _c in baskets} if self.scan else {}
        files_of = {bid: self.scan.files.get(bid) for bid, _n, _c in baskets} if self.scan else {}
        signature = (tuple((b, n) for b, n, _c in baskets), tuple((b, tuple(v)) for b, v in items_of.items()),
                     tuple((b, tuple((p, len(f)) for p, _k, f in e)) for b, e in entries_of.items()))
        if force or signature != self._signature:
            if self._signature is not None:
                self._expanded = self.model.expanded_keys(self.tree)
            self._signature = signature
            self.model.search_ids = set(self.search_ids)
            self.model.load(baskets, items_of, entries_of, files_of)
            if self.filter_edit.text().strip():
                self._apply_filter()
            else:
                self.model.restore_expanded(self.tree, self._expanded)
        else:
            self.model.files_of = files_of
            self.model.refresh()
        has_items = self.model.has_items()
        self.stack.setCurrentWidget(self.tree if has_items or len(baskets) > 1 else self.empty_page)
        self.filter_edit.setVisible(has_items)
        self._update_status()

    def _update_status(self):
        if self.bottom.currentIndex() == 1:
            return
        if not self.model.has_items():
            self.status.setText("")
            return
        if self.scan is None:
            self.status.setText("סורק את הסלים…")
            return
        scope = self.scope()
        if not scope:
            self.status.setText(f'<span style="color:{C.warn}">לא סומן אף סל לחיפוש</span>')
            return
        files = list(dict.fromkeys(f for bid, _n, _c in scope for f in (self.scan.files.get(bid) or [])))
        kinds = {"word": 0, "pdf": 0, "doc": 0}
        pending = bad = 0
        for f in files:
            kinds[doc_kind(f)] += 1
            st = self.scan.status.get(f)
            if st is None:
                pending += 1
            elif st[0] != "ok":
                bad += 1
        names = {"word": "וורד", "pdf": "PDF", "doc": "doc ישן"}
        parts = [f'<span style="color:{C.ok}">✓</span> בחיפוש: <b>{len(files):,}</b> מסמכים']
        parts += [f"{n:,} {ltr(names[k])}‏" for k, n in kinds.items() if n]
        if pending:
            parts.append(f"{pending:,} ממתינים")
        if bad:
            parts.append(f'<a href="problems" style="color:{C.warn}">{bad:,} לא נקראו</a>')
        parts.append(f'<a href="update" style="color:{C.accent}">עדכון</a>')
        self.status.setText(" · ".join(parts))

    def _status_link(self, link):
        if link == "problems":
            self._show_problems()
        elif link == "update":
            self.updateRequested.emit()

    def _show_problems(self, bid=None):
        if not self.scan:
            return
        files = []
        for b, _n, _c in self.db.baskets():
            if (bid is None and b in self.search_ids) or b == bid:
                files += self.scan.files.get(b) or []
        bad = [(f, self.scan.status[f][1]) for f in dict.fromkeys(files)
               if f in self.scan.status and self.scan.status[f][0] != "ok"]
        lines = [f"• {doc_name(p)} – {m}" for p, m in bad[:40]]
        if len(bad) > 40:
            lines.append(f"… ועוד {len(bad) - 40}")
        QMessageBox.information(self, "מסמכים שלא נקראו", "\n".join(lines) or "אין")

    # ================================================================ התקדמות
    def show_progress(self, frac, text=""):
        title, _, detail = text.partition("\n")
        pct = f"{int(frac * 100)}% · " if frac is not None and frac >= 0 else ""
        self.progress_title.setFullText(pct + (title or "מעדכן…"))
        self.progress_detail.setFullText(detail)
        if frac is None or frac < 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(min(1.0, frac) * 1000))
        self.bottom.setCurrentIndex(1)

    def hide_progress(self):
        self.bottom.setCurrentIndex(0)
        self._update_status()

    # ================================================================ אינטראקציה
    def _clicked(self, index):
        node = self.model.node_at(index)
        if node is not None and node.kind == "add":
            self.open_browser(node.bid)

    def _double_clicked(self, index):
        node = self.model.node_at(index)
        if node is None:
            return
        if node.kind == "basket":
            self.set_search_ids({node.bid})          # חיפוש רק בסל הזה
        elif node.kind in ("file", "single"):
            open_default(node.path)
        elif node.kind != "add":
            self.tree.setExpanded(index, not self.tree.isExpanded(index))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:
            self.remove_selected()
            return
        super().keyPressEvent(e)

    def _context_menu(self, pos):
        index = self.tree.indexAt(pos)
        node = self.model.node_at(index)
        menu = QMenu(self)
        if node is None:
            menu.addAction(ui_icon("plus"), "סל חדש…", self.new_basket)
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return
        bid = node.bid
        if node.kind in ("basket", "add"):
            menu.addAction(ui_icon("search"), "בחירה מהמחשב…", lambda: self.open_browser(bid))
            menu.addAction(ui_icon("folder-plus"), "הוספת תיקייה…", lambda: self.add_folder(bid))
            menu.addAction(ui_icon("file-plus"), "הוספת מסמכים…", lambda: self.add_files(bid))
            menu.addSeparator()
            menu.addAction(ui_icon("check"), "חיפוש רק בסל הזה", lambda: self.set_search_ids({bid}))
            all_ids = {b for b, _n, _c in self.db.baskets()}
            if self.search_ids != all_ids:
                menu.addAction("חיפוש בכל הסלים", lambda: self.set_search_ids(all_ids))
            if node.kind == "basket" and self.model.problems(node):
                menu.addAction(ui_icon("warning"), "מסמכים שלא נקראו…", lambda: self._show_problems(bid))
            menu.addAction(ui_icon("refresh"), "עדכון מפת החיפוש", self.updateRequested)
            menu.addSeparator()
            menu.addAction(ui_icon("pencil"), "שינוי שם…", lambda: self.rename_basket(bid))
            menu.addAction(ui_icon("trash"), "מחיקת הסל…", lambda: self.delete_basket(bid))
        else:
            if node.kind in ("file", "single"):
                menu.addAction(ui_icon("external"), "פתח את המסמך", lambda: open_default(node.path))
            menu.addAction(ui_icon("folder"), "הצג בתיקייה", lambda: reveal_in_folder(node.path))
            menu.addSeparator()
            if node.kind in ("dir", "file"):
                on = self.model.included_count(node) > 0
                what = "התיקייה" if node.kind == "dir" else "המסמך"
                menu.addAction(ui_icon("x") if on else ui_icon("check"),
                               f"החרג את {what} מהחיפוש" if on else f"החזר את {what} לחיפוש",
                               lambda: self._tree_toggled(bid, node.path, node.kind == "dir", not on))
            else:
                if not self.tree.selectionModel().isSelected(index):
                    self.tree.setCurrentIndex(index)
                menu.addAction(ui_icon("trash"), "הסר מהסל (Delete)", self.remove_selected)
        menu.exec(self.tree.viewport().mapToGlobal(pos))
