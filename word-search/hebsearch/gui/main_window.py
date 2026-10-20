import os

from PySide6.QtCore import QSettings, QStringListModel, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QCompleter, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter,
    QVBoxLayout, QWidget,
)

from .. import __version__
from ..index import IndexDB
from ..opener import open_at, open_default, reveal_in_folder, word_automation_available
from ..search import Searcher, SearchOptions
from . import pdf_viewer
from .basket_panel import BasketPanel
from .icons import file_icon
from .results import SYNTAX_TABLE, ResultsView, doc_name, form_of, ltr
from .workers import Job

AHEVI_CHOICES = [("none", "מדויק"), ("vy", "ו׳ י׳ – כתיב מלא וחסר"), ("all", "כל אותיות אהו״י")]
SORT_CHOICES = [("relevance", "הכי מדויק קודם"), ("document", "לפי מסמך ומיקום")]


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
        self.pending = None          # שאילתה שממתינה לסיום עבודה קודמת ("" = רק סריקה)
        self.result = None
        self.form_filter = None
        self.viewers = []
        self.history = self.settings.value("history", [], list) or []
        saved = self.settings.value("search_baskets", None)
        self.search_ids = None if saved is None else {int(x) for x in (saved if isinstance(saved, list) else [saved])}

        self.setWindowTitle("חיפוש במסמכי Word ו-PDF")
        self.resize(1360, 860)
        self._build()
        self._restore_options()
        self._open_error.connect(lambda m: self.statusBar().showMessage(f"לא הצלחתי לפתוח בוורד: {m}", 8000))
        self._refresh_chips()
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
        self.baskets = BasketPanel(self.db, self.settings)
        self.baskets.contentsChanged.connect(lambda: self.start_job(None))
        self.baskets.basketsChanged.connect(self._baskets_changed)
        self.baskets.update_btn.clicked.connect(lambda: self.start_job(None))
        self.baskets.cancel_btn.clicked.connect(self._cancel_job)
        splitter.addWidget(self.baskets)
        splitter.addWidget(self._build_search_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([390, 970])

        act = QAction(self)
        act.setShortcut(QKeySequence("Ctrl+F"))
        act.triggered.connect(lambda: (self.search_edit.setFocus(), self.search_edit.selectAll()))
        self.addAction(act)

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

        # בחירת סלים בלחיצה אחת
        self.chips_row = QHBoxLayout()
        self.chips_row.setSpacing(6)
        tl.addLayout(self.chips_row)
        self.chips = {}

        opts = QHBoxLayout()
        opts.setSpacing(18)
        self.cb_prefixes = QCheckBox("אותיות שימוש (ו, ה, ש, ב, כ, ל, מ)")
        self.cb_prefixes.setToolTip("למשל: חיפוש 'דרך' ימצא גם 'בדרך', 'והדרך', 'כשבדרך'")
        self.cb_inflect = QCheckBox("הטיות (הלך ← הלכה, הליכה, הולכים)")
        self.cb_inflect.setToolTip(
            "מוצא צורות נוספות של המילה: סיומות, תחיליות ותנועות בתוך המילה (הלכה, הולכים, וילך, ללכת).\n"
            "זהו קירוב – צורות חריגות כמו בית/בתים לא נמצאות.")
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
        head = QHBoxLayout()
        self.summary = _label("", "summary")
        self.summary.setTextFormat(Qt.RichText)
        self.summary.setWordWrap(True)
        self.summary.linkActivated.connect(self._summary_link)
        head.addWidget(self.summary, 1)
        head.addWidget(_label("מיון:", "muted"), 0, Qt.AlignTop)
        self.sort_combo = QComboBox()
        for _, label in SORT_CHOICES:
            self.sort_combo.addItem(label)
        self.sort_combo.setToolTip("הכי מדויק קודם: צורה זהה למילה שהוקלדה ומילים צמודות – בראש הרשימה")
        self.sort_combo.currentIndexChanged.connect(self._sort_changed)
        head.addWidget(self.sort_combo, 0, Qt.AlignTop)
        rl.addLayout(head)

        split = QSplitter(Qt.Horizontal)
        self.file_list = QListWidget()
        self.file_list.setMinimumWidth(180)
        self.file_list.currentRowChanged.connect(lambda _: self._apply_filters())
        self.file_list.itemDoubleClicked.connect(self._file_item_open)
        self.results = ResultsView(self.searcher.materialize)
        self.results.hitClicked.connect(self.open_hit)
        self.results.fileClicked.connect(open_default)
        self.results.folderClicked.connect(reveal_in_folder)
        split.addWidget(self.file_list)
        split.addWidget(self.results)
        split.setStretchFactor(1, 1)
        split.setSizes([220, 750])
        self.file_list.hide()
        rl.addWidget(split, 1)
        lay.addWidget(res_panel, 1)

        self.statusBar().showMessage(f"גרסה {__version__}")
        return w

    # ================= בחירת סלים לחיפוש =================
    def _refresh_chips(self):
        while self.chips_row.count():
            it = self.chips_row.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()
        self.chips = {}
        baskets = self.db.baskets()
        ids = {b[0] for b in baskets}
        if self.search_ids is None:
            self.search_ids = set(ids)
        self.search_ids &= ids
        self.chips_row.addWidget(_label("חיפוש בסלים:", "muted"))
        for bid, name, count in baskets:
            chip = QPushButton(f"{name}  {count:,}")
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setChecked(bid in self.search_ids)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setToolTip("לחיצה: הכללה/הוצאה של הסל מהחיפוש\nלחיצה כפולה: חיפוש רק בסל הזה")
            chip.toggled.connect(lambda on, bid=bid: self._chip_toggled(bid, on))
            chip.mouseDoubleClickEvent = lambda e, bid=bid: self._only_basket(bid)
            self.chips[bid] = chip
            self.chips_row.addWidget(chip)
        if len(baskets) > 1:
            all_link = _label('<a href="all" style="color:#1d4ed8; text-decoration:none">כל הסלים</a>')
            all_link.setTextFormat(Qt.RichText)
            all_link.linkActivated.connect(lambda _: self._set_search_ids(ids))
            self.chips_row.addWidget(all_link)
        self.chips_row.addStretch(1)

    def _set_search_ids(self, ids):
        self.search_ids = set(ids)
        for bid, chip in self.chips.items():
            chip.blockSignals(True)
            chip.setChecked(bid in self.search_ids)
            chip.blockSignals(False)
        self._search_ids_changed()

    def _chip_toggled(self, bid, on):
        (self.search_ids.add if on else self.search_ids.discard)(bid)
        self._search_ids_changed()

    def _only_basket(self, bid):
        self._set_search_ids({bid})

    def _search_ids_changed(self):
        self.settings.setValue("search_baskets", sorted(self.search_ids))
        if self.result is not None and self.search_edit.text().strip():
            self.run_search()

    def _baskets_changed(self):
        known = set(self.chips)
        new = {b[0] for b in self.db.baskets()} - known
        if self.search_ids is not None:
            self.search_ids |= new          # סל חדש נכלל בחיפוש מיד
            self.settings.setValue("search_baskets", sorted(self.search_ids))
        self._refresh_chips()
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
            sort=SORT_CHOICES[self.sort_combo.currentIndex()][0],
        )

    def _restore_options(self):
        s = self.settings
        widgets = [self.cb_prefixes, self.cb_inflect, self.ahevi_combo, self.gap_spin,
                   self.cb_paragraph, self.cb_ordered, self.sort_combo]
        for wd in widgets:
            wd.blockSignals(True)
        self.cb_prefixes.setChecked(s.value("prefixes", True, bool))
        self.cb_inflect.setChecked(s.value("inflect", False, bool))
        self.ahevi_combo.setCurrentIndex(int(s.value("ahevi", 0)))
        self.gap_spin.setValue(int(s.value("gap", 0)))
        self.cb_paragraph.setChecked(s.value("paragraph", False, bool))
        self.gap_spin.setEnabled(not self.cb_paragraph.isChecked())
        self.cb_ordered.setChecked(s.value("ordered", True, bool))
        self.sort_combo.setCurrentIndex(int(s.value("sort", 0)))
        for wd in widgets:
            wd.blockSignals(False)

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

    def _sort_changed(self):
        self.settings.setValue("sort", self.sort_combo.currentIndex())
        if self.result is not None and self.search_edit.text().strip():
            self.run_search()

    # ================= עבודות רקע =================
    def run_search(self):
        q = self.search_edit.text().strip()
        if not q:
            return
        if not self.search_ids:
            self.summary.setText('<span style="color:#b45309">בחרו לפחות סל אחד לחיפוש (מעל התוצאות).</span>')
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
        baskets = {bid: self.db.basket_items(bid) for bid, _, _ in self.db.baskets()}
        self.job = Job(self.db_path, baskets, sorted(self.search_ids or ()), query,
                       self.options() if query else None)
        self.thread = QThread()
        self.job.moveToThread(self.thread)
        self.thread.started.connect(self.job.run)
        self.job.progress.connect(self._on_progress)
        self.job.done.connect(self._on_done)
        self.baskets.update_btn.setEnabled(False)
        self.baskets.cancel_btn.show()
        if query:
            self.search_btn.setEnabled(False)
            self.summary.setText("מחפש…")
        self.thread.start()

    def _cancel_job(self):
        if self.job:
            self.job.cancel()
            self.pending = None

    def _on_progress(self, text, done, total):
        bar, label = self.baskets.progress, self.baskets.progress_label
        bar.show()
        if total:
            bar.setRange(0, total)
            bar.setValue(done)
            label.setText(f"{text}\n{done:,} מתוך {total:,}")
        else:
            bar.setRange(0, 0)
            label.setText(text)

    def _on_done(self, out):
        self.thread.quit()
        self.thread.wait()
        self.job.deleteLater()
        self.thread.deleteLater()
        self.job = self.thread = None
        self.baskets.progress.hide()
        self.baskets.progress_label.setText("העדכון נעצר." if out.cancelled else "")
        self.baskets.update_btn.setEnabled(True)
        self.baskets.cancel_btn.hide()
        self.search_btn.setEnabled(True)

        if out.error:
            QMessageBox.critical(self, "שגיאה", out.error[-1500:])
        else:
            self.baskets.set_scan(out.baskets, out.status)
            self._update_chip_counts()
            if out.result is not None:
                self._show_result(out.result)
            elif out.indexed:
                self.statusBar().showMessage(f"המפה עודכנה: נקראו {out.indexed:,} מסמכים", 6000)
        self._refresh_stats()

        pending, self.pending = self.pending, None
        if pending is not None:
            self.start_job(pending or None)

    def _update_chip_counts(self):
        for bid, name, count in self.db.baskets():
            chip = self.chips.get(bid)
            if chip:
                chip.setText(f"{name}  {count:,}")

    def _refresh_stats(self):
        st = self.db.stats()
        size = ltr(f"{st['size_mb']:.1f} MB")
        jump = " · קפיצה למקום בוורד: פעילה" if word_automation_available() else ""
        self.statusBar().showMessage(
            f"מפת חיפוש: {st['files']:,} מסמכים · {st['words']:,} מילים שונות · {size}{jump}")

    # ================= תוצאות =================
    def _show_result(self, res):
        self.result = res
        self.form_filter = None
        self.file_list.blockSignals(True)
        self.file_list.clear()
        if res.files:
            self.file_list.addItem(QListWidgetItem(f"כל המסמכים  ({res.total:,})"))
            for fid, path, count in res.files:
                it = QListWidgetItem(file_icon(path), f"{doc_name(path)}  ({count:,})")
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
        found = ('נמצאה <b style="color:#1d4ed8">תוצאה אחת</b>' if res.total == 1 else
                 f'נמצאו <b style="color:#1d4ed8">{res.total:,}</b> תוצאות')
        s = f'{found} ב{files_word}<span style="color:#94a3b8">  ·  {res.elapsed:.2f} שניות</span>'
        exact = sum(1 for h in res.hits if h.exact)
        if exact and exact != res.total:
            s += f'<span style="color:#166534">  ·  {exact:,} מדויקות</span>'
        if shown != res.total:
            s += f'<span style="color:#64748b">  ·  מוצגות {shown:,}</span>'
        if res.truncated:
            s += '<span style="color:#b45309">  ·  הוצגו רק הראשונות – צמצמו את החיפוש</span>'
        if len(res.forms) > 1 or self.form_filter:
            chips = []
            for form, c in res.forms.most_common(14):
                on = form == self.form_filter
                style = "background:#1d4ed8; color:white" if on else "color:#1d4ed8"
                chips.append(f'<a href="form:{form}" style="{style}; text-decoration:none">&nbsp;{form}&nbsp;</a>'
                             f'<span style="color:#94a3b8">({c:,})</span>')
            more = f" … ועוד {len(res.forms) - 14:,}" if len(res.forms) > 14 else ""
            reset = '  <a href="form:" style="color:#64748b">[הצג הכל]</a>' if self.form_filter else ""
            s += (f'<br><span style="color:#64748b; font-size:9.5pt">צורות שנמצאו: </span>'
                  f'<span style="font-size:10pt">{"  ".join(chips)}{more}{reset}</span>')
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
            grouped = SORT_CHOICES[self.sort_combo.currentIndex()][0] == "document" and fid is None
            self.results.show_hits(res, hits, grouped)
        else:
            self.results.show_message(
                '<p style="font-size:13pt; color:#64748b; margin:30px" align="center">'
                'לא נמצאו תוצאות.<br><span style="font-size:10pt">נסו להפעיל הטיות, אותיות שימוש '
                'או גמישות באותיות אהו״י, להגדיל את הרווח בין המילים, או לבחור סלים נוספים.</span></p>')

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
            "</ul><p><b>דירוג:</b> קודם הצורה הזהה למה שהוקלד, ואחריה צורות רחוקות יותר; "
            "מילים צמודות ובסדר הנכון לפני מילים מרוחקות.</p>"
            "<p style='color:#64748b'>ניקוד, טעמים, גרשיים ואותיות סופיות לא משנים את החיפוש.</p>")
        box.exec()

    def _file_item_open(self, item):
        path = item.data(Qt.UserRole + 1)
        if path:
            open_default(path)

    def open_hit(self, hit):
        self.searcher.materialize(hit, self.result.highlight if self.result else frozenset())
        if hit.path.lower().endswith(".pdf"):
            if pdf_viewer.AVAILABLE:
                word = max(hit.needle.split(), key=len) if hit.needle.split() else ""
                v = pdf_viewer.PdfViewer(hit.path, hit.page or 1, word, doc_name(hit.path), self)
                v.show()
                self.viewers = [x for x in self.viewers if x.isVisible()] + [v]
            else:
                open_default(hit.path)
                QApplication.clipboard().setText(hit.needle)
                self.statusBar().showMessage(
                    f"'{doc_name(hit.path)}' נפתח – {hit.location}. הטקסט שנמצא הועתק ללוח.", 12000)
            return
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
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow(db_path)
    win.show()
    return app.exec()
