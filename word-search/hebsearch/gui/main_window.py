import os

from PySide6.QtCore import QSettings, QStringListModel, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QCompleter, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSpinBox, QSplitter, QStyle,
    QToolButton, QVBoxLayout, QWidget,
)

from .. import __version__
from ..index import IndexDB, is_supported
from ..opener import open_at, reveal_in_folder, word_automation_available
from ..search import Searcher, SearchOptions
from .results import SYNTAX_TABLE, ResultsView, doc_name, form_of, ltr, short_path
from .workers import Job

AHEVI_CHOICES = [("none", "מדויק"), ("vy", "ו׳ י׳ – כתיב מלא וחסר"), ("all", "כל אותיות אהו״י")]


class BasketList(QListWidget):
    """רשימת פריטי הסל – מקבלת גם גרירת קבצים ותיקיות מהסייר."""
    dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setWordWrap(True)

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


def _panel():
    f = QFrame()
    f.setObjectName("panel")
    return f


def _label(text, name=None):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    return lab


class MainWindow(QMainWindow):
    _open_error = Signal(str)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.db = IndexDB(db_path)
        self.searcher = Searcher(self.db)
        self.settings = QSettings("HebWordSearch", "app")
        self.thread = None
        self.job = None
        self.pending = None          # (query, opts) שממתין לסיום עבודה קודמת
        self.result = None
        self.problems = []
        self.history = self.settings.value("history", [], list) or []

        self.setWindowTitle("חיפוש במסמכי וורד")
        self.resize(1280, 820)
        self._build()
        self._load_baskets()
        self._restore_options()
        self._open_error.connect(lambda m: self.statusBar().showMessage(f"לא הצלחתי לפתוח בוורד: {m}", 8000))
        self._refresh_stats()
        QTimer.singleShot(300, lambda: self.start_job(None))

    # ================= בניית הממשק =================
    def _build(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(10)
        root.addWidget(splitter)
        splitter.addWidget(self._build_basket_panel())
        splitter.addWidget(self._build_search_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([310, 970])

        act = QAction(self)
        act.setShortcut(QKeySequence("Ctrl+F"))
        act.triggered.connect(lambda: (self.search_edit.setFocus(), self.search_edit.selectAll()))
        self.addAction(act)

    def _build_basket_panel(self):
        panel = _panel()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(_label("🧺 סל החיפוש", "title"))

        row = QHBoxLayout()
        self.basket_combo = QComboBox()
        self.basket_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.basket_combo.currentIndexChanged.connect(self._basket_changed)
        row.addWidget(self.basket_combo)
        for icon, tip, slot in (("＋", "סל חדש", self._new_basket),
                                ("✎", "שינוי שם", self._rename_basket),
                                ("🗑", "מחיקת הסל", self._delete_basket)):
            b = QToolButton()
            b.setText(icon)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            row.addWidget(b)
        lay.addLayout(row)

        self.basket_list = BasketList()
        self.basket_list.dropped.connect(self._add_paths)
        lay.addWidget(self.basket_list, 1)

        row = QHBoxLayout()
        b_folder = QPushButton("📁 הוסף תיקייה")
        b_folder.clicked.connect(self._add_folder)
        b_files = QPushButton("📄 הוסף קבצים")
        b_files.clicked.connect(self._add_files)
        row.addWidget(b_folder)
        row.addWidget(b_files)
        lay.addLayout(row)
        b_remove = QPushButton("הסר את הנבחרים")
        b_remove.clicked.connect(self._remove_selected)
        lay.addWidget(b_remove)

        self.basket_info = _label("", "muted")
        self.basket_info.setWordWrap(True)
        self.basket_info.setTextFormat(Qt.RichText)
        self.basket_info.linkActivated.connect(lambda _: self._show_problems())
        lay.addWidget(self.basket_info)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        lay.addWidget(self.progress)
        self.progress_label = _label("", "muted")
        self.progress_label.setWordWrap(True)
        lay.addWidget(self.progress_label)

        row = QHBoxLayout()
        self.update_btn = QPushButton("🔄 עדכן מפת חיפוש")
        self.update_btn.setToolTip("קורא מחדש מסמכים שנוספו או השתנו מאז הפעם הקודמת")
        self.update_btn.clicked.connect(lambda: self.start_job(None))
        self.cancel_btn = QPushButton("עצור")
        self.cancel_btn.clicked.connect(self._cancel_job)
        self.cancel_btn.hide()
        row.addWidget(self.update_btn, 1)
        row.addWidget(self.cancel_btn)
        lay.addLayout(row)
        return panel

    def _build_search_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        top = _panel()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(14, 14, 14, 12)
        tl.setSpacing(10)

        row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("search")
        self.search_edit.setPlaceholderText("הקלידו מילים לחיפוש…   למשל: הלך בדרך")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(self.run_search)
        self.history_model = QStringListModel(self.history)
        completer = QCompleter(self.history_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.search_edit.setCompleter(completer)
        self.search_btn = QPushButton("חיפוש")
        self.search_btn.setObjectName("primary")
        self.search_btn.clicked.connect(self.run_search)
        row.addWidget(self.search_edit, 1)
        row.addWidget(self.search_btn)
        tl.addLayout(row)

        opts = QHBoxLayout()
        opts.setSpacing(18)
        self.cb_prefixes = QCheckBox("אותיות שימוש (ו, ה, ש, ב, כ, ל, מ)")
        self.cb_prefixes.setToolTip("למשל: חיפוש 'דרך' ימצא גם 'בדרך', 'והדרך', 'כשבדרך'")
        self.cb_inflect = QCheckBox("הטיות (הלך ← הלכה, הליכה, הולכים)")
        self.cb_inflect.setToolTip(
            "מוצא צורות נוספות של המילה: סיומות, תחיליות ותנועות בתוך המילה.\n"
            "זהו קירוב – לא נמצאות צורות שבהן נשמטת אות שורש (ילך, ללכת).")
        opts.addWidget(self.cb_prefixes)
        opts.addWidget(self.cb_inflect)
        opts.addWidget(_label("אותיות אהו״י:"))
        self.ahevi_combo = QComboBox()
        for _, label in AHEVI_CHOICES:
            self.ahevi_combo.addItem(label)
        self.ahevi_combo.setToolTip("כמה לסבול הבדלים באותיות אהו״י: 'שמרה' ימצא גם 'שמירה', 'שומרה'")
        opts.addWidget(self.ahevi_combo)
        opts.addStretch(1)
        tl.addLayout(opts)

        opts2 = QHBoxLayout()
        opts2.setSpacing(10)
        opts2.addWidget(_label("רווח בין המילים: עד"))
        self.gap_spin = QSpinBox()
        self.gap_spin.setRange(0, 99)
        self.gap_spin.setSuffix(" מילים")
        self.gap_spin.setToolTip("0 = המילים צמודות זו לזו (צירוף מדויק)")
        opts2.addWidget(self.gap_spin)
        self.cb_paragraph = QCheckBox("בכל מקום באותה פסקה")
        self.cb_paragraph.toggled.connect(lambda on: self.gap_spin.setEnabled(not on))
        self.cb_ordered = QCheckBox("שמירה על סדר המילים")
        opts2.addSpacing(10)
        opts2.addWidget(self.cb_paragraph)
        opts2.addSpacing(10)
        opts2.addWidget(self.cb_ordered)
        opts2.addStretch(1)
        hint = _label('<a href="help" style="color:#1d4ed8; text-decoration:none">❔ חיפוש מתקדם</a>')
        hint.setTextFormat(Qt.RichText)
        hint.linkActivated.connect(self._show_syntax)
        opts2.addWidget(hint)
        tl.addLayout(opts2)
        for cb in (self.cb_prefixes, self.cb_inflect, self.cb_paragraph, self.cb_ordered):
            cb.toggled.connect(self._options_changed)
        self.ahevi_combo.currentIndexChanged.connect(self._options_changed)
        self.gap_spin.valueChanged.connect(self._options_changed)
        lay.addWidget(top)

        res_panel = _panel()
        rl = QVBoxLayout(res_panel)
        rl.setContentsMargins(12, 10, 12, 10)
        self.summary = _label("", "summary")
        self.summary.setTextFormat(Qt.RichText)
        self.summary.setWordWrap(True)
        self.summary.linkActivated.connect(self._summary_link)
        rl.addWidget(self.summary)

        split = QSplitter(Qt.Horizontal)
        self.file_list = QListWidget()
        self.file_list.setMinimumWidth(180)
        self.file_list.currentRowChanged.connect(lambda _: self._apply_filters())
        self.file_list.itemDoubleClicked.connect(self._file_item_open)
        self.results = ResultsView(self.searcher.materialize)
        self.results.hitClicked.connect(self.open_hit)
        self.results.fileClicked.connect(lambda p: open_at(p))
        self.results.folderClicked.connect(reveal_in_folder)
        split.addWidget(self.file_list)
        split.addWidget(self.results)
        split.setStretchFactor(1, 1)
        split.setSizes([230, 740])
        self.file_list.hide()
        rl.addWidget(split, 1)
        lay.addWidget(res_panel, 1)

        self.form_filter = None
        self.statusBar().showMessage(f"גרסה {__version__}")
        return w

    # ================= סלים =================
    def _load_baskets(self, select_id=None):
        baskets = self.db.baskets()
        if not baskets:
            self.db.create_basket("הסל שלי")
            baskets = self.db.baskets()
        if select_id is None:
            select_id = int(self.settings.value("basket", baskets[0][0]))
        self.basket_combo.blockSignals(True)
        self.basket_combo.clear()
        idx = 0
        for i, (bid, name) in enumerate(baskets):
            self.basket_combo.addItem(name, bid)
            if bid == select_id:
                idx = i
        self.basket_combo.setCurrentIndex(idx)
        self.basket_combo.blockSignals(False)
        self._fill_basket_list()

    @property
    def basket_id(self):
        return self.basket_combo.currentData()

    def _basket_changed(self):
        self.settings.setValue("basket", self.basket_id)
        self._fill_basket_list()
        self.start_job(None)

    def _fill_basket_list(self):
        self.basket_list.clear()
        style = self.style()
        for path, kind in self.db.basket_items(self.basket_id):
            name = os.path.basename(path.rstrip("\\/")) or path
            if kind != "folder":
                name = doc_name(path)
            item = QListWidgetItem(f"{name}\n{ltr(short_path(os.path.dirname(path)))}")
            item.setIcon(style.standardIcon(QStyle.SP_DirIcon if kind == "folder" else QStyle.SP_FileIcon))
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            self.basket_list.addItem(item)
        if not self.basket_list.count():
            self.basket_info.setText("הסל ריק. הוסיפו תיקיות או קבצים, או גררו אותם לכאן.")

    def _new_basket(self):
        name, ok = QInputDialog.getText(self, "סל חדש", "שם הסל:")
        if ok and name.strip():
            try:
                bid = self.db.create_basket(name.strip())
            except Exception:
                QMessageBox.warning(self, "סל חדש", "כבר קיים סל בשם הזה.")
                return
            self._load_baskets(bid)
            self._basket_changed()

    def _rename_basket(self):
        name, ok = QInputDialog.getText(self, "שינוי שם", "שם חדש:", text=self.basket_combo.currentText())
        if ok and name.strip():
            try:
                self.db.rename_basket(self.basket_id, name.strip())
            except Exception:
                QMessageBox.warning(self, "שינוי שם", "כבר קיים סל בשם הזה.")
                return
            self._load_baskets(self.basket_id)

    def _delete_basket(self):
        if QMessageBox.question(self, "מחיקת סל",
                                f"למחוק את הסל '{self.basket_combo.currentText()}'?\n"
                                "(המסמכים עצמם לא יימחקו)") == QMessageBox.Yes:
            self.db.delete_basket(self.basket_id)
            self._load_baskets()
            self._basket_changed()

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "בחירת תיקייה", self.settings.value("last_dir", ""))
        if d:
            self.settings.setValue("last_dir", d)
            self._add_paths([d])

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "בחירת מסמכים", self.settings.value("last_dir", ""),
            "מסמכי וורד (*.docx *.docm *.dotx *.doc *.rtf);;כל הקבצים (*)")
        if files:
            self.settings.setValue("last_dir", os.path.dirname(files[0]))
            self._add_paths(files)

    def _add_paths(self, paths):
        items = []
        for p in paths:
            if os.path.isdir(p):
                items.append((p, "folder"))
            elif os.path.isfile(p) and is_supported(p):
                items.append((p, "file"))
        if items:
            self.db.add_basket_items(self.basket_id, items)
            self._fill_basket_list()
            self.start_job(None)

    def _remove_selected(self):
        paths = [it.data(Qt.UserRole) for it in self.basket_list.selectedItems()]
        if paths:
            self.db.remove_basket_items(self.basket_id, paths)
            self._fill_basket_list()
            self.start_job(None)

    # ================= אפשרויות =================
    def options(self) -> SearchOptions:
        return SearchOptions(
            prefixes=self.cb_prefixes.isChecked(),
            inflections=self.cb_inflect.isChecked(),
            ahevi=AHEVI_CHOICES[self.ahevi_combo.currentIndex()][0],
            max_gap=self.gap_spin.value(),
            whole_paragraph=self.cb_paragraph.isChecked(),
            ordered=self.cb_ordered.isChecked(),
        )

    def _restore_options(self):
        s = self.settings
        self.cb_prefixes.setChecked(s.value("prefixes", True, bool))
        self.cb_inflect.setChecked(s.value("inflect", False, bool))
        self.ahevi_combo.setCurrentIndex(int(s.value("ahevi", 0)))
        self.gap_spin.setValue(int(s.value("gap", 0)))
        self.cb_paragraph.setChecked(s.value("paragraph", False, bool))
        self.cb_ordered.setChecked(s.value("ordered", True, bool))

    def _options_changed(self):
        s = self.settings
        s.setValue("prefixes", self.cb_prefixes.isChecked())
        s.setValue("inflect", self.cb_inflect.isChecked())
        s.setValue("ahevi", self.ahevi_combo.currentIndex())
        s.setValue("gap", self.gap_spin.value())
        s.setValue("paragraph", self.cb_paragraph.isChecked())
        s.setValue("ordered", self.cb_ordered.isChecked())
        if self.result is not None and self.search_edit.text().strip():
            self.run_search()

    # ================= עבודות רקע =================
    def run_search(self):
        q = self.search_edit.text().strip()
        if not q:
            return
        if q in self.history:
            self.history.remove(q)
        self.history.insert(0, q)
        del self.history[50:]
        self.history_model.setStringList(self.history)
        self.settings.setValue("history", self.history)
        self.start_job(q)

    def start_job(self, query):
        if self.job is not None:
            if query is not None:
                self.pending = query
            elif self.pending is None:
                self.pending = ""
            return
        items = self.db.basket_items(self.basket_id)
        self.job = Job(self.db_path, items, query, self.options() if query else None)
        self.thread = QThread()
        self.job.moveToThread(self.thread)
        self.thread.started.connect(self.job.run)
        self.job.progress.connect(self._on_progress)
        self.job.done.connect(self._on_done)
        self.update_btn.setEnabled(False)
        self.cancel_btn.show()
        if query:
            self.search_btn.setEnabled(False)
            self.summary.setText("מחפש…")
        self.thread.start()

    def _cancel_job(self):
        if self.job:
            self.job.cancel()
            self.pending = None

    def _on_progress(self, text, done, total):
        self.progress.show()
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.progress_label.setText(f"{text}\n{done:,} מתוך {total:,}")
        else:
            self.progress.setRange(0, 0)
            self.progress_label.setText(text)

    def _on_done(self, out):
        self.thread.quit()
        self.thread.wait()
        self.job.deleteLater()
        self.thread.deleteLater()
        self.job = self.thread = None
        self.progress.hide()
        self.progress_label.setText("")
        self.update_btn.setEnabled(True)
        self.cancel_btn.hide()
        self.search_btn.setEnabled(True)

        if out.error:
            QMessageBox.critical(self, "שגיאה", out.error[-1500:])
        else:
            self.problems = out.problems
            self._update_basket_info(out)
            if out.result is not None:
                self._show_result(out.result)
            elif out.indexed:
                self.statusBar().showMessage(f"המפה עודכנה: נקראו {out.indexed:,} מסמכים", 6000)
        self._refresh_stats()

        pending, self.pending = self.pending, None
        if pending is not None:
            self.start_job(pending or None)

    def _update_basket_info(self, out):
        if not self.basket_list.count():
            return
        txt = f"{out.files:,} מסמכים בסל"
        if out.problems:
            txt += f' · <a href="p" style="color:#b45309">{len(out.problems):,} לא נקראו</a>'
        if out.cancelled:
            txt += " · העדכון נעצר"
        self.basket_info.setText(txt)

    def _show_problems(self):
        lines = [f"• {doc_name(p)} – {m}" for p, m in self.problems[:40]]
        if len(self.problems) > 40:
            lines.append(f"… ועוד {len(self.problems) - 40}")
        QMessageBox.information(self, "מסמכים שלא נקראו", "\n".join(lines))

    def _refresh_stats(self):
        st = self.db.stats()
        size = ltr(f"{st['size_mb']:.1f} MB")
        jump = " · קפיצה למקום בוורד: פעילה" if word_automation_available() else ""
        self.statusBar().showMessage(
            f"מפת חיפוש: {st['files']:,} מסמכים · {st['words']:,} מילים שונות · "
            f"{size}{jump}")

    # ================= תוצאות =================
    def _show_result(self, res):
        self.result = res
        self.form_filter = None
        self.file_list.blockSignals(True)
        self.file_list.clear()
        if res.files:
            self.file_list.addItem(QListWidgetItem(f"כל המסמכים  ({res.total:,})"))
            for fid, path, count in res.files:
                it = QListWidgetItem(f"{doc_name(path)}  ({count:,})")
                it.setToolTip(path)
                it.setData(Qt.UserRole, fid)
                it.setData(Qt.UserRole + 1, path)
                self.file_list.addItem(it)
            self.file_list.setCurrentRow(0)
        self.file_list.setVisible(len(res.files) > 1)
        self.file_list.blockSignals(False)
        self._apply_filters()

    def _summary_html(self, res, shown):
        if res.message and not res.total:
            return f'<span style="color:#b45309">{res.message}</span>'
        if not res.total:
            return f"לא נמצאו תוצאות ב-{res.searched_files:,} מסמכים."
        files_word = "מסמך אחד" if len(res.files) == 1 else f"-{len(res.files):,} מסמכים"
        found = ("נמצאה <b style=\"color:#1d4ed8\">תוצאה אחת</b>" if res.total == 1 else
                 f'נמצאו <b style="color:#1d4ed8">{res.total:,}</b> תוצאות')
        s = (f'{found} ב{files_word}'
             f'<span style="color:#94a3b8">  ·  {res.elapsed:.2f} שניות</span>')
        if shown != res.total:
            s += f'<span style="color:#64748b">  ·  מוצגות {shown:,}</span>'
        if res.truncated:
            s += '<span style="color:#b45309">  ·  הוצגו רק הראשונות – צמצמו את החיפוש</span>'
        if len(res.forms) > 1 or self.form_filter:
            chips = []
            for form, c in res.forms.most_common(14):
                on = form == self.form_filter
                style = ("background:#1d4ed8; color:white" if on else "color:#1d4ed8")
                chips.append(f'<a href="form:{form}" style="{style}; text-decoration:none">&nbsp;{form}&nbsp;</a>'
                             f'<span style="color:#94a3b8">({c:,})</span>')
            more = f" … ועוד {len(res.forms) - 14:,}" if len(res.forms) > 14 else ""
            reset = ('  <a href="form:" style="color:#64748b">[הצג הכל]</a>' if self.form_filter else "")
            s += f'<br><span style="color:#64748b; font-size:9.5pt">צורות שנמצאו: </span>' \
                 f'<span style="font-size:10pt">{"  ".join(chips)}{more}{reset}</span>'
        return s

    def _apply_filters(self):
        res = self.result
        if res is None:
            return
        hits = res.hits
        item = self.file_list.currentItem()
        fid = item.data(Qt.UserRole) if item is not None else None
        if fid is not None:
            hits = [h for h in hits if h.file_id == fid]
        if self.form_filter:
            hits = [h for h in hits if any(form_of(w) == self.form_filter for w in h.words)]
        self.summary.setText(self._summary_html(res, len(hits)))
        if hits:
            self.results.show_hits(res, hits)
        else:
            self.results.show_message(
                '<p style="font-size:13pt; color:#64748b; margin:30px" align="center">'
                'לא נמצאו תוצאות.<br><span style="font-size:10pt">נסו להפעיל הטיות, אותיות שימוש '
                'או גמישות באותיות אהו״י, או להגדיל את הרווח בין המילים.</span></p>')

    def _summary_link(self, link):
        if link.startswith("form:"):
            form = link[5:] or None
            self.form_filter = None if form == self.form_filter else form
            self._apply_filters()

    def _show_syntax(self):
        box = QMessageBox(self)
        box.setWindowTitle("חיפוש מתקדם")
        box.setTextFormat(Qt.RichText)
        box.setText(
            "<p><b>אפשר לשלב בשאילתה:</b></p>" + SYNTAX_TABLE +
            "<p><b>אפשרויות:</b></p><ul>"
            "<li><b>אותיות שימוש</b> – 'דרך' ימצא גם 'בדרך', 'והדרך', 'כשבדרך'.</li>"
            "<li><b>הטיות</b> – 'הלך' ימצא גם 'הלכה', 'הליכה', 'הולכים', 'וילך', 'ללכת'.</li>"
            "<li><b>אותיות אהו״י</b> – 'שמרה' ימצא גם 'שמירה', 'שומרה'.</li>"
            "<li><b>רווח בין המילים</b> – כמה מילים מותר שיפרידו בין מילות החיפוש (0 = צמודות).</li>"
            "</ul><p style='color:#64748b'>ניקוד, טעמים, גרשיים ואותיות סופיות לא משנים את החיפוש.</p>")
        box.exec()

    def _file_item_open(self, item):
        path = item.data(Qt.UserRole + 1)
        if path:
            open_at(path)

    def open_hit(self, hit):
        cands = self.searcher.locate(hit)
        used_word = open_at(hit.path, cands, hit.kind, hit.note, on_error=self._open_error.emit)
        if used_word:
            self.statusBar().showMessage(f"פותח את '{doc_name(hit.path)}' בוורד ומסמן את המקום…", 6000)
        else:
            QApplication.clipboard().setText(hit.needle)
            self.statusBar().showMessage(
                f"'{doc_name(hit.path)}' נפתח ({hit.location}). הטקסט שנמצא הועתק – "
                "Ctrl+F ואז Ctrl+V כדי להגיע אליו.", 12000)

    def closeEvent(self, e):
        if self.job:
            self.job.cancel()
            self.thread.quit()
            self.thread.wait(5000)
        self.db.close()
        super().closeEvent(e)


def run(db_path):
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("HebWordSearch")
    app.setLayoutDirection(Qt.RightToLeft)
    from .style import QSS
    app.setStyleSheet(QSS)
    f = QFont("Segoe UI", 10)
    app.setFont(f)
    win = MainWindow(db_path)
    win.show()
    return app.exec()
