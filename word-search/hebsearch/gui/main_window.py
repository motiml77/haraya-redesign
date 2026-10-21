"""החלון הראשי.

פריסה (מימין לשמאל, כמו בעברית):
    סרגל הסלים │ שורת חיפוש קומפקטית (שדה · חיפוש · אפשרויות) + תגיות הסלים
               │ התוצאות – תופסות את כל שאר המקום
כל העבודה הכבדה (סריקה, אינדוקס, חיפוש, הכנת קטעים) רצה ברקע, והחלון נשאר חי ומציג אחוזים.
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QEvent, QRect, QSettings, QSize, QStringListModel, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCompleter, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from .. import __version__
from ..index import IndexDB
from ..opener import open_at, open_default, open_pdf_external, reveal_in_folder, word_automation_available
from ..search import Searcher, parse_query
from . import pdf_viewer, theme
from .basket_panel import BasketPanel
from .doc_viewer import DocViewer
from .icons import file_icon, ui_icon
from .options import OptionsPopup
from .results import ResultsView, doc_name, form_of, ltr, message_html, syntax_table
from .theme import C, T
from .widgets import Chip, Combo, FlowLayout, SearchField, icon_button, text_icon_button
from .workers import ScanJob, SearchJob

SORT_CHOICES = [("relevance", "הכי מדויק קודם"), ("document", "לפי מסמך ומיקום")]


def _alive(widget):
    try:
        return widget.isVisible()
    except RuntimeError:     # החלון נסגר ונמחק
        return False


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("panel")
    return f


class MainWindow(QMainWindow):
    statusMessage = Signal(str)          # מתהליכון רקע (פתיחה בוורד) אל שורת המצב

    def __init__(self, db_path, settings=None):
        super().__init__()
        self.db_path = db_path
        self.db = IndexDB(db_path)
        self.searcher = Searcher(self.db)             # לשימוש בחוט הראשי בלבד: איתור מיקום, מציגים
        self.settings = settings or QSettings("HebWordSearch", "app")
        self._closing = False
        self._last_scan_done = 0.0
        self.scan = None
        self.scan_cache = {}
        self._scan_job = None
        self._scan_pending = False
        self._scan_ui_timer = QTimer(self)
        self._scan_ui_timer.setSingleShot(True)
        self._scan_ui_timer.timeout.connect(self._show_scan_progress)
        self._scan_last = (-1.0, "")
        self._search_job = None
        self._search_seq = 0
        self._search_waiting_scan = False
        self.result = None
        self.pending_docs = 0
        self.form_filter = None
        self.viewers = []
        self.history = self.settings.value("history", [], list) or []
        saved = self.settings.value("search_baskets", None)
        self.search_ids = None if saved is None else {int(x) for x in (saved if isinstance(saved, list) else [saved])}

        from .. import APP_NAME
        self.statusMessage.connect(self._show_status)
        self.setWindowTitle(f"{APP_NAME} – Word ו-PDF")
        self._place_window()
        self._build()
        self.options.restore(self.settings)
        self.options_btn_text()
        self.sort_combo.setCurrentIndex(int(self.settings.value("sort", 0)))
        self.results.configure(self.db_path, 20)
        self._refresh_chips()
        self._refresh_stats()
        self._restore_layout_state()
        QTimer.singleShot(150, lambda: self.start_scan())

    # ================================================================ גודל החלון
    def _screen_rect(self) -> QRect:
        screen = self.screen() or QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def _place_window(self):
        avail = self._screen_rect()
        geo = theme.fit_geometry(avail)
        self.setGeometry(geo)
        self.setMinimumSize(min(860, avail.width()), min(520, avail.height()))
        saved = self.settings.value("geometry")
        if saved:
            self.restoreGeometry(saved)
            frame = self.frameGeometry()
            if not avail.intersects(frame) or frame.width() > avail.width() + 4 or frame.height() > avail.height() + 4:
                self.setGeometry(geo)

    # ================================================================ בנייה
    def _build(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(T.gap, T.gap, T.gap, T.gap)
        root.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(T.gap)
        self.splitter.setChildrenCollapsible(True)
        root.addWidget(self.splitter)

        self.baskets = BasketPanel(self.db, self.settings)
        self.baskets.setMinimumWidth(T.pad * 24)
        self.baskets.contentsChanged.connect(lambda: self.start_scan())
        self.baskets.basketsChanged.connect(self._baskets_changed)
        self.baskets.currentChanged.connect(self._basket_selected)
        self.baskets.updateRequested.connect(lambda: self.start_scan(force=True))
        self.baskets.cancelRequested.connect(self._cancel_scan)
        self.splitter.addWidget(self.baskets)
        self.splitter.addWidget(self._build_main())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(1, False)
        total = max(600, self.width() - 2 * T.gap)
        side = max(T.pad * 28, min(T.pad * 34, int(total * 0.28)))
        self.splitter.setSizes([side, total - side])

        self._build_status_bar()

        for seq, slot in (("Ctrl+F", self._focus_search), ("Ctrl+B", self._toggle_sidebar),
                          ("Ctrl+=", lambda: self.set_zoom(T.zoom + 0.1)), ("Ctrl++", lambda: self.set_zoom(T.zoom + 0.1)),
                          ("Ctrl+-", lambda: self.set_zoom(T.zoom - 0.1)), ("Ctrl+0", lambda: self.set_zoom(1.0)),
                          ("Esc", self._escape)):
            act = QAction(self)
            act.setShortcut(QKeySequence(seq))
            act.triggered.connect(slot)
            self.addAction(act)

    def _build_main(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(T.gap)

        # ---- כרטיס החיפוש (קומפקטי) ----
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(T.pad, T.gap, T.pad, T.gap)
        cl.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.sidebar_btn = icon_button("sidebar", "הצגה / הסתרה של סרגל הסלים (Ctrl+B)", checkable=True, bordered=True)
        self.sidebar_btn.setChecked(True)
        self.sidebar_btn.toggled.connect(self._sidebar_toggled)
        self.search_edit = SearchField()
        self.search_edit.setPlaceholderText("חיפוש במסמכים…  למשל: הלך בדרך")
        self.search_edit.returnPressed.connect(self.run_search)
        self.search_edit.textChanged.connect(self._query_changed)
        self.history_model = QStringListModel(self.history)
        completer = QCompleter(self.history_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.search_edit.setCompleter(completer)
        self.search_btn = QPushButton("חיפוש")
        self.search_btn.setObjectName("primary")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.clicked.connect(self.run_search)
        self.options_btn = text_icon_button("sliders", "אפשרויות", "אפשרויות החיפוש: אותיות שימוש, הטיות, רווח בין מילים ועוד")
        self.options_btn.setObjectName("bordered")
        T.sized(self.options_btn, h="h_search")
        self.options_btn.clicked.connect(self._show_options)
        self.options = OptionsPopup(self)
        self.options.changed.connect(self._options_changed)
        self.options.helpRequested.connect(self._show_syntax)
        row.addWidget(self.sidebar_btn)
        row.addWidget(self.search_edit, 1)
        row.addWidget(self.search_btn)
        row.addWidget(self.options_btn)
        T.sized(self.sidebar_btn, h="h_search", min_w="h_search")
        cl.addLayout(row)

        # תגיות הסלים לחיפוש (שורה אחת קומפקטית; מוסתרת כשיש סל אחד)
        self.chips_host = QWidget()
        self.chips_flow = FlowLayout(self.chips_host, hspacing=6, vspacing=4)
        cl.addWidget(self.chips_host)
        self.chips = {}
        lay.addWidget(card)

        # ---- כרטיס התוצאות ----
        res = _card()
        rl = QVBoxLayout(res)
        rl.setContentsMargins(T.pad, T.gap, T.pad, T.gap)
        rl.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(T.gap)
        self.summary = QLabel("")
        self.summary.setObjectName("summary")
        self.summary.setTextFormat(Qt.RichText)
        self.summary.setWordWrap(True)
        self.summary.linkActivated.connect(self._summary_link)
        head.addWidget(self.summary, 1)
        self.sort_combo = Combo()
        for _, label in SORT_CHOICES:
            self.sort_combo.addItem(label)
        self.sort_combo.setToolTip("הכי מדויק קודם: צורה זהה למילה שהוקלדה ומילים צמודות – בראש הרשימה")
        self.sort_combo.currentIndexChanged.connect(self._sort_changed)
        self.sort_combo.hide()
        head.addWidget(self.sort_combo, 0, Qt.AlignTop)
        rl.addLayout(head)
        self.forms_label = QLabel("")
        self.forms_label.setObjectName("caption")
        self.forms_label.setTextFormat(Qt.RichText)
        self.forms_label.setWordWrap(True)
        self.forms_label.linkActivated.connect(self._summary_link)
        self.forms_label.hide()
        rl.addWidget(self.forms_label)

        self.docs_split = QSplitter(Qt.Horizontal)
        self.docs_split.setHandleWidth(T.gap)
        self.file_list = QListWidget()
        T.sized(self.file_list, min_w=lambda: T.pad * 14, max_w=lambda: T.pad * 34)
        self.file_list.setIconSize(QSize(T.icon, T.icon))
        self.file_list.setTextElideMode(Qt.ElideMiddle)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_list.currentRowChanged.connect(lambda _: self._apply_filters())
        self.file_list.itemDoubleClicked.connect(lambda it: it.data(Qt.UserRole + 1) and open_default(it.data(Qt.UserRole + 1)))
        self.results = ResultsView()
        self.results.hitClicked.connect(self.open_hit)
        self.results.hitPreview.connect(self.preview_hit)
        self.results.fileClicked.connect(open_default)
        self.results.folderClicked.connect(reveal_in_folder)
        self.results.linkActivated.connect(self._summary_link)
        self.results.cancelRequested.connect(self._cancel_search)
        self.docs_split.addWidget(self.file_list)
        self.docs_split.addWidget(self.results)
        self.docs_split.setStretchFactor(0, 0)
        self.docs_split.setStretchFactor(1, 1)
        self.docs_split.setCollapsible(1, False)
        self.docs_split.setSizes([T.pad * 22, 800])
        self.file_list.hide()
        rl.addWidget(self.docs_split, 1)
        lay.addWidget(res, 1)
        return w

    def _build_status_bar(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.zoom_label = QLabel("")
        self.zoom_label.setObjectName("caption")
        minus = QToolButton()
        minus.setText("A−")
        minus.setToolTip("הקטנת התצוגה (Ctrl+מינוס)")
        minus.clicked.connect(lambda: self.set_zoom(T.zoom - 0.1))
        plus = QToolButton()
        plus.setText("A+")
        plus.setToolTip("הגדלת התצוגה (Ctrl+פלוס)")
        plus.clicked.connect(lambda: self.set_zoom(T.zoom + 0.1))
        about = QToolButton()
        about.setText("אודות")
        about.setIcon(ui_icon("info"))
        about.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        about.clicked.connect(self._about)
        for b in (about, plus, self.zoom_label, minus):
            sb.addPermanentWidget(b)
        self._update_zoom_label()

    # ================================================================ תצוגה: זום, סרגל צד, מצב
    def set_zoom(self, zoom: float):
        zoom = max(0.7, min(1.6, round(zoom, 2)))
        if abs(zoom - T.zoom) < 0.01:
            return
        theme.apply(QApplication.instance(), zoom)
        self.settings.setValue("zoom", zoom)
        self.results.retheme()
        self.baskets.retheme()
        self._update_zoom_label()

    def _update_zoom_label(self):
        self.zoom_label.setText(f"{int(round(T.zoom * 100))}%")

    def _toggle_sidebar(self):
        self.sidebar_btn.setChecked(not self.sidebar_btn.isChecked())

    def _sidebar_toggled(self, on):
        self.baskets.setVisible(on)

    def _focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _escape(self):
        if self._search_job is not None:
            self._cancel_search()

    def _restore_layout_state(self):
        state = self.settings.value("splitter")
        if state:
            self.splitter.restoreState(state)

    # ================================================================ תגיות הסלים
    def _refresh_chips(self):
        flow = self.chips_flow
        while flow.count():
            item = flow.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.chips = {}
        baskets = self.db.baskets()
        ids = {b[0] for b in baskets}
        if self.search_ids is None:
            self.search_ids = set(ids)
        self.search_ids &= ids
        label = QLabel("חיפוש בסלים:")
        label.setObjectName("caption")
        flow.addWidget(label)
        for bid, name, count in baskets:
            chip = Chip(f"{name}  {count:,}" if count else name)
            chip.setChecked(bid in self.search_ids)
            chip.setToolTip("לחיצה: הכללה/הוצאה של הסל מהחיפוש\nלחיצה כפולה: חיפוש רק בסל הזה")
            chip.toggled.connect(lambda on, bid=bid: self._chip_toggled(bid, on))
            chip.doubleClicked.connect(lambda bid=bid: self._set_search_ids({bid}))
            self.chips[bid] = chip
            flow.addWidget(chip)
        if len(baskets) > 1:
            all_btn = QPushButton("כל הסלים")
            all_btn.setObjectName("flat")
            all_btn.setCursor(Qt.PointingHandCursor)
            T.sized(all_btn, h="h_chip")
            all_btn.clicked.connect(lambda: self._set_search_ids(set(ids)))
            flow.addWidget(all_btn)
        self.chips_host.setVisible(len(baskets) > 1)
        self.chips_host.updateGeometry()

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
        self.start_scan()

    def _basket_selected(self, bid):
        if self.scan is None or bid not in self.scan.entries:
            self.start_scan()

    def _update_chip_counts(self):
        for bid, name, count in self.db.baskets():
            chip = self.chips.get(bid)
            if chip:
                chip.setText(f"{name}  {count:,}" if count else name)

    # ================================================================ אפשרויות
    def _show_options(self):
        self.options.show_below(self.options_btn)

    def options_btn_text(self):
        n = self.options.non_default()
        self.options_btn.setText(f" אפשרויות ({n})" if n else " אפשרויות")

    def _options_changed(self):
        self.options.save(self.settings)
        self.options_btn_text()
        if self.result is not None and self.search_edit.text().strip():
            self.run_search()

    def _query_changed(self, text):
        n = sum(1 for t in parse_query(text) if not t.negate)
        self.options.set_term_count(n)
        self.options_btn_text()

    def _sort_changed(self):
        self.settings.setValue("sort", self.sort_combo.currentIndex())
        if self.result is not None and self.search_edit.text().strip():
            self.run_search()

    # ================================================================ סריקה ועדכון המפה
    def start_scan(self, force=False):
        if self._closing:
            return
        if force:
            self.scan_cache.clear()
        if self._scan_job is not None:
            self._scan_pending = True
            return
        baskets = {bid: self.db.basket_items(bid) for bid, _n, _c in self.db.baskets()}
        job = ScanJob(self.db_path, baskets, self.scan_cache)
        job.signals.progress.connect(self._on_scan_progress)
        job.signals.finished.connect(self._on_scan_done)
        self._scan_job = job
        self._scan_last = (-1.0, "סורק את התיקיות…")
        self._scan_ui_timer.start(450)               # התקדמות מוצגת רק אם הסריקה לא מהירה
        job.start()

    def _show_scan_progress(self):
        if self._scan_job is not None:
            self.baskets.show_progress(*self._scan_last)

    @Slot(float, str)
    def _on_scan_progress(self, frac, text):
        self._scan_last = (frac, text)
        if not self._scan_ui_timer.isActive():
            self.baskets.show_progress(frac, text)
        if self._search_waiting_scan:
            self.results.busy_progress(frac, text or "מעדכן את מפת החיפוש")

    @Slot(object)
    def _on_scan_done(self, outcome):
        if self._closing:
            return
        self._scan_job = None
        self._scan_ui_timer.stop()
        self.baskets.hide_progress()
        self._last_scan_done = time.monotonic()
        note = ""
        if outcome.error:
            note = "שגיאה בסריקה: " + outcome.error.strip().splitlines()[-1]
        elif outcome.result is not None:
            self.scan = outcome.result
            self.baskets.set_scan(self.scan)
            self._update_chip_counts()
            if outcome.result.indexed:
                note = f"המפה עודכנה: נקראו {outcome.result.indexed:,} מסמכים"
        self._refresh_stats()
        if note:
            self.statusBar().showMessage(note, 8000)
        if self._scan_pending:
            self._scan_pending = False
            self.start_scan()
            return
        if self._search_waiting_scan:
            self._search_waiting_scan = False
            self.results.busy_end()
            if self.scan is None:           # הסריקה נכשלה או בוטלה – לא מנסים שוב ושוב
                self.results.show_message(message_html(
                    "לא ניתן היה לעדכן את הסלים לחיפוש", note or "הסריקה בוטלה. אפשר ללחוץ על 'עדכון מפת החיפוש'.", C.warn))
            else:
                self.run_search()

    @Slot(str)
    def _show_status(self, msg):
        if not self._closing:
            self.statusBar().showMessage(msg, 10000)

    def _maybe_rescan(self):
        """חזרה לחלון אחרי זמן: בודקים ברקע אם נוספו מסמכים לתיקיות הסלים (בלי לחסום)."""
        if self.scan is not None and self._scan_job is None and time.monotonic() - self._last_scan_done > 45:
            self.start_scan(force=True)

    def event(self, e):
        if e.type() == QEvent.WindowActivate and not self._closing:
            QTimer.singleShot(250, self._maybe_rescan)
        return super().event(e)

    def _cancel_scan(self):
        if self._scan_job is not None:
            self._scan_job.cancel()
        self._scan_pending = False

    def _refresh_stats(self):
        st = self.db.stats()
        size = ltr(f"{st['size_mb']:.1f} MB")
        jump = " · קפיצה למקום בוורד: פעילה" if word_automation_available() else ""
        self.statusBar().showMessage(
            f"מפת חיפוש: {st['files']:,} מסמכים · {st['words']:,} מילים שונות · {size}{jump}")

    # ================================================================ חיפוש
    def run_search(self):
        q = self.search_edit.text().strip()
        if not q:
            return
        if not self.search_ids:
            self.results.show_message(message_html("בחרו לפחות סל אחד לחיפוש", "מעל התוצאות – תגיות הסלים", C.warn))
            return
        if q in self.history:
            self.history.remove(q)
        self.history.insert(0, q)
        del self.history[50:]
        self.history_model.setStringList(self.history)
        self.settings.setValue("history", self.history)
        self._cancel_search(quiet=True)
        if self.scan is None or self._scan_job is not None:
            # הסריקה רצה (ראשונית, או אחרי שינוי בסל) – מחכים לה, עם התקדמות, ואז מחפשים
            self._search_waiting_scan = True
            self.results.busy_begin("מכין את הסלים לחיפוש…")
            if self._scan_job is None:
                self.start_scan()
            return
        opts = self.options.options()
        from dataclasses import replace
        opts = replace(opts, sort=SORT_CHOICES[self.sort_combo.currentIndex()][0])
        paths, seen = [], set()
        for bid in sorted(self.search_ids):
            for f in self.scan.files.get(bid, []):
                if f not in seen:
                    seen.add(f)
                    paths.append(f)
        self._search_seq += 1
        job = SearchJob(self.db_path, q, opts, paths, dict(self.scan.status), tag=self._search_seq)
        job.signals.progress.connect(self._on_search_progress)
        job.signals.finished.connect(self._on_search_done)
        self._search_job = job
        self.results.busy_begin("מחפש…")
        job.start()

    def _cancel_search(self, quiet=False):
        if self._search_job is not None:
            self._search_job.cancel()
            self._search_job = None
            self._search_seq += 1            # תוצאות העבודה הישנה יתעלמו
        self._search_waiting_scan = False
        self.results.busy_end()
        if not quiet and self.result is None:
            self.results.show_welcome()

    @Slot(float, str)
    def _on_search_progress(self, frac, text):
        if self._search_job is not None and self.sender() is self._search_job.signals:
            self.results.busy_progress(frac, text)

    @Slot(object)
    def _on_search_done(self, outcome):
        if self._closing or outcome.tag != self._search_seq:
            return
        self._search_job = None
        self.results.busy_end()
        if outcome.error:
            self.results.show_message(message_html("אירעה שגיאה בחיפוש", outcome.error.strip().splitlines()[-1], C.danger))
            return
        payload = outcome.result
        if payload.result.cancelled:
            return
        self.pending_docs = payload.pending
        self._show_result(payload.result)

    # ================================================================ תוצאות
    def _show_result(self, res):
        self.result = res
        self.form_filter = None
        self.file_list.blockSignals(True)
        self.file_list.clear()
        if res.files:
            self.file_list.addItem(QListWidgetItem(f"כל המסמכים  ({res.total:,})"))
            for fid, path, count in res.files[:400]:
                it = QListWidgetItem(file_icon(path), f"{doc_name(path)}  ({count:,})")
                it.setToolTip(ltr(path))
                it.setData(Qt.UserRole, fid)
                it.setData(Qt.UserRole + 1, path)
                self.file_list.addItem(it)
            self.file_list.setCurrentRow(0)
        self.file_list.blockSignals(False)
        self._sync_file_list()
        self._apply_filters()

    def _sync_file_list(self):
        """רשימת המסמכים מוצגת רק כשיש מה לסנן ויש מקום (בחלון צר היא מקטינה את הכרטיסים)."""
        res = self.result
        show = bool(res and len(res.files) > 1 and self.docs_split.width() >= T.pad * 56)
        if not show and self.file_list.isVisible() and self.file_list.currentRow() > 0:
            self.file_list.blockSignals(True)
            self.file_list.setCurrentRow(0)
            self.file_list.blockSignals(False)
            self._apply_filters()
        self.file_list.setVisible(show)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._sync_file_list)

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
        self._update_header(res, len(hits), fid)
        self.sort_combo.setVisible(bool(res.total))
        if hits:
            grouped = SORT_CHOICES[self.sort_combo.currentIndex()][0] == "document" and fid is None
            self.results.show_hits(res, hits, grouped)
        else:
            self.results.show_message(self._no_results_html(res))

    def _no_results_html(self, res):
        near = ""
        if res.near_miss:
            m, count = res.near_miss
            near = (f'<p align="center"><a href="near:{m}">נסו בלי אחת המילים: {m} מתוך {res.n_terms} – '
                    f'{count:,} תוצאות ›</a></p>')
        if res.message and not res.total:
            return message_html(res.message, "", C.warn).replace("</body>", near + "</body>")
        if res.n_terms > 1:
            text = f"לא נמצאו כל {res.n_terms} המילים יחד"
            hint = "עם הרווח והסדר שנבחרו. נסו להגדיל את הרווח, לבטל את שמירת הסדר, או לחפש בכל מקום באותה פסקה."
        else:
            text = "לא נמצאו תוצאות"
            hint = "נסו להפעיל הטיות, אותיות שימוש או גמישות באותיות אהו״י, או לבחור סלים נוספים."
        return message_html(text, hint).replace("</body>", near + "</body>")

    def _update_header(self, res, shown, fid):
        parts = []
        if res.message and not res.total:
            self.summary.setText(f'<span style="color:{C.warn}">{res.message}</span>')
            self.forms_label.hide()
            return
        if not res.total:
            self.summary.setText(f"לא נמצאו תוצאות ב-{res.searched_files:,} מסמכים")
            self.forms_label.hide()
            return
        files_word = "מסמך אחד" if len(res.files) == 1 else f"{len(res.files):,} מסמכים"
        found = (f'נמצאה <b style="color:{C.accent}">תוצאה אחת</b>' if res.total == 1 else
                 f'נמצאו <b style="color:{C.accent}">{res.total:,}</b> תוצאות')
        parts.append(f"{found} ב-{files_word}")
        parts.append(f'<span style="color:{C.muted}">{res.elapsed:.2f} שניות</span>')
        exact = sum(1 for h in res.hits if h.exact)
        if exact and exact != res.total:
            parts.append(f'<span style="color:{C.ok}">{exact:,} מדויקות</span>')
        if res.required and res.required < res.n_terms:
            full = sum(1 for h in res.hits if h.covered == res.n_terms)
            if full:
                parts.append(f'<span style="color:{C.muted}">{full:,} עם כל המילים</span>')
        if shown != res.total:
            parts.append(f'<span style="color:{C.muted}">מוצגות {shown:,}</span>')
        if res.truncated:
            parts.append(f'<span style="color:{C.warn}">הוצגו רק הראשונות – צמצמו את החיפוש</span>')
        if self.pending_docs:
            parts.append(f'<span style="color:{C.warn}">{self.pending_docs:,} מסמכים עדיין לא נקראו</span>')
        desc = self.options.describe()
        if desc:
            parts.append(f'<span style="color:{C.muted}">{desc}</span>')
        self.summary.setText("  ·  ".join(parts))
        # צורות שנמצאו (ניתן ללחוץ לסינון)
        if len(res.forms) > 1 or self.form_filter:
            chips = []
            for form, c in res.forms.most_common(10):
                on = form == self.form_filter
                style = f"background:{C.accent}; color:white" if on else f"color:{C.accent}"
                chips.append(f'<a href="form:{form}" style="{style}; text-decoration:none">&nbsp;{form}&nbsp;</a>'
                             f'<span style="color:{C.muted}">({c:,})</span>')
            more = f" … ועוד {len(res.forms) - 10:,}" if len(res.forms) > 10 else ""
            reset = '  <a href="form:" style="color:#64748b">[הצג הכל]</a>' if self.form_filter else ""
            self.forms_label.setText("צורות שנמצאו: " + "  ".join(chips) + more + reset)
            self.forms_label.show()
        else:
            self.forms_label.hide()

    def _summary_link(self, link):
        if link.startswith("near:"):
            m = int(link[5:])
            idx = self.options.required.findData(m)
            if idx >= 0:
                self.options.required.setCurrentIndex(idx)      # מפעיל חיפוש מחדש
            return
        if link.startswith("form:"):
            form = link[5:] or None
            self.form_filter = None if form == self.form_filter else form
            self._apply_filters()

    def _show_syntax(self):
        box = QMessageBox(self)
        box.setWindowTitle("חיפוש מתקדם")
        box.setTextFormat(Qt.RichText)
        box.setText(
            "<p><b>אפשר לשלב בשאילתה:</b></p>" + syntax_table() +
            "<p><b>אפשרויות:</b></p><ul>"
            "<li><b>אותיות שימוש</b> – 'דרך' ימצא גם 'בדרך', 'והדרך', 'כשבדרך'.</li>"
            "<li><b>הטיות</b> – 'הלך' ימצא גם 'הלכה', 'הליכה', 'הולכים', 'וילך', 'ללכת'.</li>"
            "<li><b>אותיות אהו״י</b> – 'שמרה' ימצא גם 'שמירה', 'שומרה'.</li>"
            "<li><b>רווח בין המילים</b> – כמה מילים מותר שיפרידו בין מילות החיפוש (0 = צמודות).</li>"
            "</ul><p><b>דירוג:</b> קודם הצורה הזהה למה שהוקלד, ואחריה צורות רחוקות יותר; "
            "מילים צמודות ובסדר הנכון לפני מילים מרוחקות.</p>"
            "<p style='color:#64748b'>ניקוד, טעמים, גרשיים ואותיות סופיות לא משנים את החיפוש.</p>")
        box.exec()

    def _about(self):
        from PySide6.QtGui import QPixmap

        from .. import APP_NAME, asset
        from ..paths import data_dir
        box = QMessageBox(self)
        box.setWindowTitle(f"אודות {APP_NAME}")
        box.setIconPixmap(QPixmap(asset("icon.png")).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        box.setTextFormat(Qt.RichText)
        box.setText(f"<h3>{APP_NAME}</h3><p>גרסה {__version__}</p>"
                    "<p>חיפוש מהיר וגמיש בתוך מסמכי Word ו-PDF בעברית.</p>"
                    f"<p style='color:#64748b'>מפת החיפוש נשמרת ב:<br>{ltr(data_dir())}</p>")
        box.exec()

    # ================================================================ פתיחה במקום
    def open_hit(self, hit):
        """לחיצה על תוצאה: פותח את המסמך ומנווט בדיוק למקום שלה."""
        highlight = self.result.highlight if self.result else frozenset()
        self.searcher.materialize(hit, highlight)
        if hit.path.lower().endswith(".pdf"):
            self.preview_hit(hit)                      # צופה ה-PDF מגיע לעמוד ולשורה
        elif word_automation_available():
            self.open_in_word(hit)
        else:
            # בלי וורד לשליטה (מק/לינוקס, או וורד לא מותקן) – המציג המובנה מגיע בדיוק למקום
            self.preview_hit(hit)
            self.statusBar().showMessage(
                "המסמך מוצג במציג המובנה, במקום המדויק. 'פתח את המסמך המקורי' פותח את הקובץ עצמו.", 10000)

    def open_in_word(self, hit):
        cands, ratio = self.searcher.locate(hit)
        if open_at(hit.path, cands, hit.kind, hit.note, ratio, on_status=self.statusMessage.emit):
            self.statusBar().showMessage(f"פותח את '{doc_name(hit.path)}' בוורד – {hit.location}…", 6000)
        else:
            QApplication.clipboard().setText(hit.needle)
            self.statusBar().showMessage(
                f"'{doc_name(hit.path)}' נפתח ({hit.location}). הטקסט שנמצא הועתק – "
                "Ctrl+F ואז Ctrl+V כדי להגיע אליו.", 12000)

    def preview_hit(self, hit):
        """פותח (או מעדכן) מציג מובנה של המסמך, גלול למקום התוצאה."""
        if self.result is None:
            return
        self.searcher.materialize(hit, self.result.highlight)
        hits, index = self.searcher.file_hits(self.result, hit)
        self.viewers = [v for v in self.viewers if _alive(v)]
        for v in self.viewers:
            if v.path == hit.path:
                v.navigate(hits, hit)
                return
        highlight = self.result.highlight
        if hit.path.lower().endswith(".pdf"):
            if not pdf_viewer.AVAILABLE:
                open_pdf_external(hit.path, hit.page, hit.needle.split()[0] if hit.needle else "")
                return
            v = pdf_viewer.PdfViewer(self.searcher, highlight, hits, index, self)
        else:
            v = DocViewer(self.searcher, highlight, hits, index, self.open_in_word, self)
        v.show()
        self.viewers.append(v)

    # ================================================================ סגירה
    def closeEvent(self, e):
        self._closing = True
        self._scan_ui_timer.stop()
        for job in (self._scan_job, self._search_job):
            if job is not None:
                job.cancel()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
        self.settings.setValue("zoom", T.zoom)
        self.options.save(self.settings)
        from .workers import pool
        pool().waitForDone(3000)
        self.db.close()
        super().closeEvent(e)


def prepare_app(app, settings=None):
    """הגדרות כלליות לאפליקציה: שם, כיוון, עיצוב בהיר קבוע (Fusion), גופן, לוגו."""
    from .. import APP_ID, APP_NAME, asset
    app.setApplicationName("HebWordSearch")
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setLayoutDirection(Qt.RightToLeft)
    settings = settings or QSettings("HebWordSearch", "app")
    try:
        saved_zoom = float(settings.value("zoom", 0) or 0)
    except (TypeError, ValueError):
        saved_zoom = 0.0
    screen = app.primaryScreen()
    zoom = saved_zoom if saved_zoom else (theme.default_zoom(screen.availableGeometry()) if screen else 1.0)
    theme.apply(app, zoom)
    icon = QIcon()
    for name in ("icon-16.png", "icon-32.png", "icon.png", "icon-512.png"):
        icon.addFile(asset(name))
    app.setWindowIcon(icon)
    sys.setswitchinterval(0.002)       # תגובתיות הממשק בזמן שתהליכון רקע עושה חישוב כבד
    if sys.platform == "win32":
        # בלי זה חלונות מציגה בשורת המשימות את האייקון של פייתון ולא את הלוגו
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_ID}.app")
        except Exception:
            pass


def run(db_path):
    app = QApplication.instance() or QApplication(sys.argv)
    prepare_app(app)
    win = MainWindow(db_path)
    win.show()
    return app.exec()
