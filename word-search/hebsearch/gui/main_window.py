"""החלון הראשי.

פריסה (מימין לשמאל), כמו בתוכנות עבודה מקצועיות – מסגרת אחת בלי "כרטיסים" צפים:
    סרגל האוספים │ כותרת: [סרגל] [שדה חיפוש ············] [חיפוש]
    (רקע מסגרת)│         [חיפוש ב: ⌄] [מילים: ⌄] [מרחק: ⌄]        ברירת מחדל · עזרה
               ├──────────────────────────────────────────────────
               │ סיכום התוצאות                                  [מיון ⌄]
               │ צורות שנמצאו (שבבים)
               │ התוצאות – בשקע אפור, כל השאר
    ──────────── שורת מצב: מפת החיפוש · זום · אודות ─────────────
כל העבודה הכבדה (סריקה, אינדוקס, חיפוש, הכנת קטעים) רצה ברקע, והחלון נשאר חי ומציג אחוזים.
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QEvent, QRect, QSettings, QSize, QStringListModel, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCompleter, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from .. import __version__
from ..index import IndexDB
from ..opener import open_at, open_default, open_pdf_external, reveal_in_folder, word_automation_available
from ..search import SearchOptions, Searcher, parse_query, quoted_phrase
from . import pdf_viewer, theme
from .basket_panel import BasketPanel
from .doc_viewer import DocViewer
from .icons import file_icon
from .options import DistancePanel, ScopePanel, SearchSettings, WordsPanel
from .results import ResultsView, doc_name, form_of, ltr, message_html, syntax_table
from .theme import C, T
from .widgets import Combo, FlowLayout, FormChips, OptionChip, SearchField, icon_button, link_button
from .workers import ScanJob, SearchJob

SORT_CHOICES = [("relevance", "הכי מדויק קודם"), ("document", "לפי מסמך ומיקום")]


def _alive(widget):
    try:
        return widget.isVisible()
    except RuntimeError:     # החלון נסגר ונמחק
        return False


def _frame(name: str) -> QFrame:
    f = QFrame()
    f.setObjectName(name)
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

        from .. import APP_NAME
        self.statusMessage.connect(self._show_status)
        self.setWindowTitle(f"{APP_NAME} – Word ו-PDF")
        self._place_window()
        self.options = SearchSettings(self)
        self.options.restore(self.settings)
        self._build()
        self.options.changed.connect(self._options_changed)
        self._refresh_chips()
        self.sort_combo.setCurrentIndex(int(self.settings.value("sort", 0)))
        self.results.configure(self.db_path, SearchOptions().context_words)
        self._update_scope()
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
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("frame")
        self.splitter.setHandleWidth(5)
        self.splitter.setChildrenCollapsible(True)
        root.addWidget(self.splitter)

        self.baskets = BasketPanel(self.db, self.settings)
        self.baskets.setMinimumWidth(T.pad * 24)
        self.baskets.contentsChanged.connect(lambda: self.start_scan())
        self.baskets.basketsChanged.connect(self._baskets_changed)
        self.baskets.scopeChanged.connect(self._scope_changed)
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
        w = _frame("content")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ---- כותרת: שדה החיפוש ושורת השבבים ----
        header = _frame("header")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(T.pad + 2, T.pad, T.pad + 2, 6)
        hl.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(T.gap)
        self.sidebar_btn = icon_button("sidebar", "הצגה / הסתרה של סרגל האוספים (Ctrl+B)", checkable=True)
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
        self.search_btn.setToolTip("חיפוש (Enter)")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.clicked.connect(self.run_search)
        T.sized(self.search_btn, h="h_search")
        row.addWidget(self.sidebar_btn)
        row.addWidget(self.search_edit, 1)
        row.addWidget(self.search_btn)
        T.sized(self.sidebar_btn, h="h_search", w="h_search")
        hl.addLayout(row)

        # שלוש שאלות: איפה, איך כל מילה, איך המילים יחד. בחלון צר השבבים עוברים שורה
        chips = QHBoxLayout()
        chips.setSpacing(4)
        chips.setContentsMargins(0, 0, 0, 0)
        chip_box = QWidget()
        chip_flow = FlowLayout(chip_box, 4, 4)
        policy = chip_box.sizePolicy()
        policy.setHorizontalPolicy(policy.Policy.Expanding)
        policy.setHeightForWidth(True)
        chip_box.setSizePolicy(policy)
        self.scope_chip = OptionChip("חיפוש ב:")
        self.scope_chip.setToolTip("באילו אוספים מחפשים")
        self.words_chip = OptionChip("מילים:")
        self.words_chip.setToolTip("איך למצוא כל מילה: אותיות שימוש, הטיות, כתיב מלא וחסר")
        self.dist_chip = OptionChip("מרחק:")
        self.dist_chip.setToolTip("איך המילים קשורות זו לזו: מרחק, סדר, וכמה מהן חייבות להופיע")
        self.scope_panel = ScopePanel(self)
        self.scope_panel.toggled.connect(self._scope_panel_toggled)
        self.scope_panel.allRequested.connect(self._scope_all)
        self.scope_panel.manageRequested.connect(self._scope_manage)
        self.words_panel = WordsPanel(self.options, self)
        self.dist_panel = DistancePanel(self.options, self)
        self.dist_panel.unquoteRequested.connect(self._unquote)
        for chip, panel in ((self.scope_chip, self.scope_panel), (self.words_chip, self.words_panel),
                            (self.dist_chip, self.dist_panel)):
            chip.clicked.connect(lambda _=False, c=chip, p=panel: self._toggle_panel(c, p))
            panel.closed.connect(lambda c=chip: c.setOpen(False))
            chip_flow.addWidget(chip)
        chips.addWidget(chip_box, 1)
        self.reset_btn = link_button("ברירת מחדל", "החזרת אפשרויות החיפוש לברירת המחדל", "reset")
        self.reset_btn.clicked.connect(self.options.reset)
        self.help_btn = link_button("עזרה בחיפוש", "סימנים מיוחדים: מירכאות, כוכבית, סימן שאלה, או, שלילה", "help")
        self.help_btn.clicked.connect(self._show_syntax)
        for b in (self.reset_btn, self.help_btn):
            b.full_text = b.text()
            chips.addWidget(b, 0, Qt.AlignTop)
        self.chip_box = chip_box
        hl.addLayout(chips)
        lay.addWidget(header)

        # ---- ראש התוצאות: סיכום, מיון, צורות ----
        head_box = _frame("reshead")
        rl = QVBoxLayout(head_box)
        rl.setContentsMargins(T.pad + 2, T.gap, T.pad + 2, T.gap)
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
        self.forms = FormChips()
        self.forms.clicked.connect(self._form_clicked)
        self.forms.hide()
        rl.addWidget(self.forms)
        self.head_box = head_box
        head_box.hide()
        lay.addWidget(head_box)

        self.docs_split = QSplitter(Qt.Horizontal)
        self.docs_split.setObjectName("well")
        self.docs_split.setHandleWidth(1)
        self.file_list = QListWidget()
        self.file_list.setObjectName("doclist")
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
        lay.addWidget(self.docs_split, 1)
        return w

    def _build_status_bar(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        # זום: [−] 100% [+] כבקרה אחת, כמו בשורת המצב של Word
        zoom = _frame("zoombox")
        zl = QHBoxLayout(zoom)
        zl.setContentsMargins(0, 0, 0, 0)
        zl.setSpacing(0)
        minus = icon_button("zoom-out", "הקטנת התצוגה (Ctrl+מינוס)")
        minus.clicked.connect(lambda: self.set_zoom(T.zoom - 0.1))
        plus = icon_button("zoom-in", "הגדלת התצוגה (Ctrl+פלוס)")
        plus.clicked.connect(lambda: self.set_zoom(T.zoom + 0.1))
        self.zoom_label = QPushButton("")
        self.zoom_label.setObjectName("zoomvalue")
        self.zoom_label.setToolTip("חזרה לגודל רגיל (Ctrl+0)")
        self.zoom_label.setCursor(Qt.PointingHandCursor)
        self.zoom_label.clicked.connect(lambda: self.set_zoom(1.0))
        for b in (minus, plus):
            T.sized(b, h="h_chip", w="h_chip", icon="icon")
        T.sized(self.zoom_label, h="h_chip")
        zl.addWidget(minus)                 # כמו ב-Office בעברית: מינוס מימין, פלוס משמאל
        zl.addWidget(self.zoom_label)
        zl.addWidget(plus)
        about = icon_button("info", "אודות התוכנה")
        T.sized(about, h="h_chip", w="h_chip", icon="icon")
        about.clicked.connect(self._about)
        sb.addPermanentWidget(about)
        sb.addPermanentWidget(zoom)
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
        for chip in (self.scope_chip, self.words_chip, self.dist_chip):
            chip.updateGeometry()
        self.forms.relayout()
        self._fit_header()
        self._update_zoom_label()

    def _update_zoom_label(self):
        self.zoom_label.setText(f"{int(round(T.zoom * 100))}%")

    def _toggle_sidebar(self):
        self.sidebar_btn.setChecked(not self.sidebar_btn.isChecked())

    def _sidebar_toggled(self, on):
        self.baskets.setVisible(on)
        self._update_scope()

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

    # ================================================================ במה מחפשים
    @property
    def search_ids(self):
        return self.baskets.search_ids

    def _update_scope(self):
        """השבב "חיפוש ב:" – שמות האוספים ומספר המסמכים, או אזהרה כשלא סומן אוסף."""
        scope = self.baskets.scope()
        all_count = len(self.db.baskets())
        has_items = self.baskets.model.has_items()
        self.scope_chip.setVisible(has_items)
        if not has_items:
            return
        if not scope:
            self.scope_chip.setValue("לא נבחר אוסף")
            self.scope_chip.setWarn(True)
            return
        self.scope_chip.setWarn(False)
        docs = sum(c for _b, _n, c in scope)
        if len(scope) == all_count and all_count > 1:
            names = "כל האוספים"
        elif len(scope) <= 2:
            names = ", ".join(n for _b, n, _c in scope)
        else:
            names = f"{len(scope)} אוספים"
        if len(names) > 28:
            names = names[:26] + "…"
        self.scope_chip.setValue(f"{names} · " + ("מסמך אחד" if docs == 1 else f"{docs:,} מסמכים"))
        if self.scope_panel.isVisible():
            self.scope_panel.set_baskets(self.baskets.all_baskets(), self.search_ids)

    def _scope_panel_toggled(self, bid, on):
        ids = set(self.search_ids)
        (ids.add if on else ids.discard)(bid)
        self.baskets.set_search_ids(ids)

    def _scope_all(self):
        self.baskets.set_search_ids({b for b, _n, _c in self.db.baskets()})

    def _scope_manage(self):
        self.sidebar_btn.setChecked(True)
        self.baskets.tree.setFocus()

    def _scope_changed(self):
        self._update_scope()
        if self.result is not None and self.search_edit.text().strip():
            self.run_search()

    def _baskets_changed(self):
        self._update_scope()
        self.start_scan()

    # ================================================================ אפשרויות (שבבים)
    def _toggle_panel(self, chip, panel):
        import time
        if panel.isVisible() or time.monotonic() - panel.closed_at < 0.25:
            panel.close()                    # לחיצה על השבב של חלונית פתוחה סוגרת אותה
            return
        if panel is self.scope_panel:
            panel.set_baskets(self.baskets.all_baskets(), self.search_ids)
        else:
            panel.sync()
        chip.setOpen(True)
        panel.show_below(chip)

    def _refresh_chips(self):
        o = self.options
        text = self.search_edit.text()
        quoted = quoted_phrase(text) is not None
        self.words_chip.setValue(o.words_text())
        self.words_chip.setOn(not o.words_default())
        if quoted:
            self.dist_chip.setValue("ביטוי מדויק (מירכאות)")
        else:
            self.dist_chip.setValue(o.distance_text())
        self.dist_chip.setLocked(quoted)
        self.dist_chip.setOn(not quoted and not o.distance_default())
        self.dist_chip.setDim(not quoted and o.n_terms < 2 and bool(text.strip()))
        self.dist_panel.set_locked(quoted)
        self.reset_btn.setVisible(not o.is_default())
        QTimer.singleShot(0, self._fit_header)

    def _options_changed(self):
        self.options.save(self.settings)
        self._refresh_chips()
        if self.result is not None and self.search_edit.text().strip():
            self.run_search()

    def _query_changed(self, text):
        n = sum(1 for t in parse_query(text) if not t.negate)
        self.options.set_term_count(n)
        if self.dist_panel.isVisible():
            self.dist_panel.sync()
        self._refresh_chips()

    def _unquote(self):
        q = quoted_phrase(self.search_edit.text())
        if q is not None:
            self.search_edit.setText(q)
            if self.result is not None:
                self.run_search()

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
            self._update_scope()
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
                    "לא ניתן היה לעדכן את האוספים לחיפוש", note or "הסריקה בוטלה. אפשר ללחוץ על 'עדכון מפת החיפוש'.", C.warn))
            else:
                self.run_search()

    @Slot(str)
    def _show_status(self, msg):
        if not self._closing:
            self.statusBar().showMessage(msg, 10000)

    def _maybe_rescan(self):
        """חזרה לחלון אחרי זמן: בודקים ברקע אם נוספו מסמכים לתיקיות האוספים (בלי לחסום)."""
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
            self.results.show_message(message_html("לא סומן אף אוסף לחיפוש", "סמנו ✓ ליד אוסף בסרגל האוספים", C.warn))
            return
        if q in self.history:
            self.history.remove(q)
        self.history.insert(0, q)
        del self.history[50:]
        self.history_model.setStringList(self.history)
        self.settings.setValue("history", self.history)
        self._cancel_search(quiet=True)
        if self.scan is None or self._scan_job is not None:
            # הסריקה רצה (ראשונית, או אחרי שינוי באוסף) – מחכים לה, עם התקדמות, ואז מחפשים
            self._search_waiting_scan = True
            self.results.busy_begin("מכין את האוספים לחיפוש…")
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
        show = bool(res and len(res.files) > 1 and self.docs_split.width() >= T.pad * 74)
        if not show and self.file_list.isVisible() and self.file_list.currentRow() > 0:
            self.file_list.blockSignals(True)
            self.file_list.setCurrentRow(0)
            self.file_list.blockSignals(False)
            self._apply_filters()
        self.file_list.setVisible(show)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._sync_file_list)
        QTimer.singleShot(0, self._fit_header)

    def _fit_header(self):
        """בחלון צר הקישורים "ברירת מחדל" ו"עזרה" מוצגים כסמל בלבד (הטקסט נשאר בתיאור הכלי)."""
        chips = [c for c in (self.scope_chip, self.words_chip, self.dist_chip) if not c.isHidden()]
        need = sum(c.sizeHint().width() + 4 for c in chips)
        links = [b for b in (self.reset_btn, self.help_btn) if not b.isHidden()]
        fm = self.help_btn.fontMetrics()
        need += sum(fm.horizontalAdvance(b.full_text) + T.icon + 3 * T.gap for b in links)
        room = self.chip_box.parentWidget().width() - 2 * (T.pad + 2)
        compact = need > room
        for b in (self.reset_btn, self.help_btn):
            b.setText("" if compact else b.full_text)

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
            hint = "במרחק ובסדר שנבחרו. בשבב 'מרחק' אפשר להגדיל את המרחק, לבחור 'בכל סדר' או 'באותה פסקה'."
        else:
            text = "לא נמצאו תוצאות"
            hint = "בשבב 'מילים' אפשר לבחור 'כל ההטיות' או 'מלא וחסר', ובשבב 'חיפוש ב:' – אוספים נוספים."
        return message_html(text, hint).replace("</body>", near + "</body>")

    def _update_header(self, res, shown, fid):
        self.head_box.show()
        parts = []
        if res.message and not res.total:
            self.summary.setText(f'<span style="color:{C.warn}">{res.message}</span>')
            self.forms.hide()
            return
        if not res.total:
            self.summary.setText(f"לא נמצאו תוצאות ב-{res.searched_files:,} מסמכים")
            self.forms.hide()
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
        # האפשרויות עצמן כתובות בשבבים שמעל, אז לא חוזרים עליהן כאן
        self.summary.setText("  ·  ".join(parts))
        if len(res.forms) > 1 or self.form_filter:
            top = res.forms.most_common(40)
            self.forms.set_forms(top, self.form_filter, max(0, len(res.forms) - 40))
            self.forms.show()
        else:
            self.forms.hide()

    def _form_clicked(self, form):
        form = form or None
        self.form_filter = None if form == self.form_filter else form
        self._apply_filters()

    def _summary_link(self, link):
        if link.startswith("near:"):
            self.options.update(required=int(link[5:]))      # מפעיל חיפוש מחדש
            return
        if link.startswith("form:"):
            self._form_clicked(link[5:])

    def _show_syntax(self):
        box = QMessageBox(self)
        box.setWindowTitle("עזרה בחיפוש")
        box.setTextFormat(Qt.RichText)
        box.setText(
            "<p><b>אפשר לשלב בשאילתה:</b></p>" + syntax_table() +
            "<p><b>השבבים שמתחת לשדה החיפוש:</b></p><ul>"
            "<li><b>חיפוש ב:</b> – באילו אוספים מחפשים.</li>"
            "<li><b>מילים:</b> – צורות המילה: <i>מדויק</i>, <i>עם אותיות שימוש</i> ('דרך' ← 'בדרך', 'והדרך'), "
            "או <i>כל ההטיות</i> ('הלך' ← 'הלכה', 'הולכים', 'וילך'). וכתיב: <i>מלא וחסר</i> ('שמרה' ← 'שמירה', 'שומרה') "
            "או <i>כל אהו״י</i>.</li>"
            "<li><b>מרחק:</b> – <i>צמודות</i>, <i>עד N מילים ביניהן</i> או <i>באותה פסקה</i>; הסדר; וכמה מהמילים "
            "חייבות להופיע. סימני פיסוק אינם נחשבים מילה, והחיפוש הוא בתוך פסקה אחת (ב-PDF – בתוך עמוד אחד).</li>"
            "</ul><p><b>דירוג:</b> קודם התוצאות שכוללות את כל המילים; בהן – מילים צמודות לפני מרוחקות, "
            "ובסדר הנכון לפני סדר הפוך, והצורה הזהה למה שהוקלד לפני צורות עם תחילית או הטיה. "
            "בהתאמה חלקית מילה נדירה שוקלת יותר ממילה נפוצה.</p>"
            "<p><b>הדגשה:</b> בצהוב מסומנות רק המילים שהן חלק מההתאמה עצמה.</p>"
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
