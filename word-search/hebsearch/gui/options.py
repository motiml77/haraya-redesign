"""אפשרויות החיפוש: שלוש שאלות, כל אחת בשבב משלה בשורה שמתחת לשדה החיפוש.

    חיפוש ב:   באילו אוספים מחפשים              ScopePanel
    מילים:     איך למצוא כל מילה               WordsPanel     – צורות המילה + כתיב
    מרחק:      איך המילים קשורות זו לזו        DistancePanel  – מרחק + סדר + כמה מהמילים

החלוקה כמו בפרויקט השו"ת ובמנועים המקצועיים: צורות המילה הן תכונה של כל מילה, והיחס בין
המילים הוא בחירה אחת (צמודות / עד N / באותה פסקה) – לא מספר ותיבת סימון שמבטלת אותו.
SearchSettings מחזיק את המצב, שומר אותו באותם מפתחות כמו בגרסאות הקודמות ומתרגם ל-SearchOptions.
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QRadioButton, QVBoxLayout, QWidget,
)

from ..search import SearchOptions
from .theme import C, T
from .widgets import Combo, Popup, Segmented, Stepper, WrapLabel, link_button

FORMS = [("exact", "מדויק"), ("prefixes", "עם אותיות שימוש"), ("all", "כל ההטיות")]
SPELLING = [("none", "כפי שהוקלד"), ("vy", "מלא וחסר (ו׳ י׳)"), ("all", "כל אהו״י")]
SPELLING_SHORT = {"vy": "מלא וחסר", "all": "כל אהו״י"}
DISTANCES = ("adjacent", "near", "paragraph")
ORDER = [(True, "לפי הסדר שהוקלד"), (False, "בכל סדר")]
DEFAULTS = {"forms": "prefixes", "spelling": "none", "distance": "adjacent", "near": 3, "ordered": True}

# דוגמה לכל בחירה: (המילה, הצורות שיימצאו, הסבר)
FORM_EXAMPLES = {
    "exact": ("דרך", ["דרך"], "רק המילה כפי שהוקלדה."),
    "prefixes": ("דרך", ["דרך", "בדרך", "והדרך", "כשבדרך"], "גם כשלפניה ו׳ ה׳ ש׳ ב׳ כ׳ ל׳ מ׳."),
    "all": ("הלך", ["הלכה", "הולכים", "וילך", "ללכת"],
            "גם סיומות, תחיליות ותנועות בתוך המילה. זה קירוב ולא מילון."),
}
SPELLING_EXAMPLES = {
    "none": ("שמרה", ["שמרה"], ""),
    "vy": ("שמרה", ["שמרה", "שמירה", "שומרה"], ""),
    "all": ("מילתא", ["מילתא", "מילתה"], "גם הבדלים באותיות א׳ ו-ה׳."),
}


def _num_words(n: int) -> str:
    return "מילה אחת" if n == 1 else f"{n} מילים"


class SearchSettings(QObject):
    """המצב של אפשרויות החיפוש (בלי ממשק)."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.forms = DEFAULTS["forms"]
        self.spelling = DEFAULTS["spelling"]
        self.distance = DEFAULTS["distance"]
        self.near = DEFAULTS["near"]
        self.ordered = DEFAULTS["ordered"]
        self.required = 0            # כמה מהמילים חייבות להופיע (0 = כולן)
        self.n_terms = 0             # כמה מילים יש בשאילתה כרגע

    # ----- שינוי -----
    def update(self, **values):
        dirty = False
        for key, value in values.items():
            if key == "near":
                value = max(1, min(99, int(value)))
            if getattr(self, key) != value:
                setattr(self, key, value)
                dirty = True
        if dirty:
            self.changed.emit()

    def reset(self):
        self.update(required=0, **DEFAULTS)

    def set_term_count(self, n: int):
        """מספר המילים בשאילתה. "לפחות m" שכבר לא אפשרי (m >= n) חוזר בשקט ל"כולן"."""
        self.n_terms = n
        if self.required and self.required >= n:
            self.required = 0

    def required_choices(self):
        n = self.n_terms
        if n < 2:
            return [(0, "כל המילים")]
        out = [(0, f"כל {n} המילים")]
        for m in range(n - 1, 0, -1):
            out.append((m, "לפחות אחת מהן" if m == 1 else f"לפחות {m} מתוך {n}"))
        return out

    # ----- תיאור -----
    def words_default(self) -> bool:
        return self.forms == DEFAULTS["forms"] and self.spelling == DEFAULTS["spelling"]

    def distance_default(self) -> bool:
        return (self.distance == DEFAULTS["distance"] and self.ordered == DEFAULTS["ordered"]
                and not self.required)

    def is_default(self) -> bool:
        return self.words_default() and self.distance_default()

    def words_text(self) -> str:
        text = dict(FORMS)[self.forms]
        if self.spelling in SPELLING_SHORT:
            text += " · " + SPELLING_SHORT[self.spelling]
        return text

    def distance_text(self) -> str:
        text = {"adjacent": "צמודות", "near": f"עד {_num_words(self.near)}", "paragraph": "באותה פסקה"}[self.distance]
        text += ", לפי הסדר" if self.ordered else ", בכל סדר"
        if self.required and self.required < self.n_terms:
            text += " · " + ("לפחות אחת" if self.required == 1 else f"לפחות {self.required} מתוך {self.n_terms}")
        return text

    # ----- תרגום לחיפוש -----
    def options(self) -> SearchOptions:
        return SearchOptions(
            prefixes=self.forms != "exact",
            inflections=self.forms == "all",
            ahevi=self.spelling,
            max_gap=self.near if self.distance == "near" else 0,
            whole_paragraph=self.distance == "paragraph",
            ordered=self.ordered,
            min_terms=self.required if self.required < self.n_terms else 0,
        )

    # ----- שמירה (מפתחות תואמים לגרסאות קודמות) -----
    def restore(self, s: QSettings):
        prefixes = s.value("prefixes", True, bool)
        inflect = s.value("inflect", False, bool)
        self.forms = "all" if inflect else ("prefixes" if prefixes else "exact")
        try:
            ahevi = int(s.value("ahevi", 0))
        except (TypeError, ValueError):
            ahevi = 0
        self.spelling = SPELLING[max(0, min(2, ahevi))][0]
        try:
            gap = int(s.value("gap", 0))
            near = int(s.value("near", DEFAULTS["near"]))
        except (TypeError, ValueError):
            gap, near = 0, DEFAULTS["near"]
        self.near = max(1, min(99, gap or near))
        if s.value("paragraph", False, bool):
            self.distance = "paragraph"
        else:
            self.distance = "near" if gap > 0 else "adjacent"
        self.ordered = s.value("ordered", True, bool)
        self.changed.emit()

    def save(self, s: QSettings):
        s.setValue("prefixes", self.forms != "exact")
        s.setValue("inflect", self.forms == "all")
        s.setValue("ahevi", [k for k, _ in SPELLING].index(self.spelling))
        s.setValue("gap", self.near if self.distance == "near" else 0)
        s.setValue("near", self.near)
        s.setValue("paragraph", self.distance == "paragraph")
        s.setValue("ordered", self.ordered)


# ---------------------------------------------------------------- רכיבי חלונית
def _section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("section")
    return lbl


def _separator() -> QFrame:
    sep = QFrame()
    sep.setObjectName("separator")
    return sep


def _example_html(word: str, forms, note: str = "") -> str:
    marks = " ".join(
        f'<span style="background:{C.marker}; color:{C.marker_text}">&nbsp;{escape(f)}&nbsp;</span>' for f in forms)
    html = (f'<span style="color:{C.muted}">דוגמה:</span> <b>{escape(word)}</b> '
            f'<span style="color:{C.muted}">←</span> {marks}')
    if note:
        html += f'<br><span style="color:{C.muted}">{escape(note)}</span>'
    return html


class _Panel(Popup):
    def __init__(self, settings: SearchSettings, width_pads: int, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setMinimumWidth(T.pad * width_pads)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(T.pad + 4, T.pad + 2, T.pad + 4, T.pad + 2)
        self.lay.setSpacing(6)
        settings.changed.connect(self.sync)

    def gap(self, h: int = 8):
        self.lay.addSpacing(h)


class WordsPanel(_Panel):
    """איך למצוא כל מילה: שני סולמות מהצר לרחב, ודוגמה שמתחלפת לפי הבחירה."""

    def __init__(self, settings: SearchSettings, parent=None):
        super().__init__(settings, 40, parent)
        self.lay.addWidget(_section("צורות המילה"))
        self.forms = Segmented([label for _, label in FORMS])
        self.forms.setAccessibleName("צורות המילה")
        self.forms.changed.connect(lambda i: settings.update(forms=FORMS[i][0]))
        self.lay.addWidget(self.forms)
        self.forms_example = WrapLabel("")
        self.forms_example.setTextFormat(Qt.RichText)
        self.lay.addWidget(self.forms_example)
        self.gap()
        self.lay.addWidget(_section("כתיב"))
        self.spelling = Segmented([label for _, label in SPELLING])
        self.spelling.setAccessibleName("כתיב")
        self.spelling.changed.connect(lambda i: settings.update(spelling=SPELLING[i][0]))
        self.lay.addWidget(self.spelling)
        self.spelling_example = WrapLabel("")
        self.spelling_example.setTextFormat(Qt.RichText)
        self.lay.addWidget(self.spelling_example)
        self.gap(4)
        self.lay.addWidget(_separator())
        foot = WrapLabel("ניקוד, טעמים, גרשיים ואותיות סופיות אינם משנים אף פעם.")
        foot.setObjectName("caption")
        self.lay.addWidget(foot)
        self.sync()

    def sync(self):
        s = self.settings
        self.forms.setIndex([k for k, _ in FORMS].index(s.forms), animate=True)
        self.spelling.setIndex([k for k, _ in SPELLING].index(s.spelling), animate=True)
        self.forms_example.setText(_example_html(*FORM_EXAMPLES[s.forms]))
        self.spelling_example.setText(_example_html(*SPELLING_EXAMPLES[s.spelling]))


class DistancePanel(_Panel):
    """איך המילים קשורות זו לזו: מרחק (בחירה אחת), סדר, וכמה מהמילים חייבות להופיע."""
    unquoteRequested = Signal()

    def __init__(self, settings: SearchSettings, parent=None):
        super().__init__(settings, 36, parent)
        # הודעה כשהשאילתה במירכאות (ההגדרות כאן לא חלות עליה)
        self.lock_box = QFrame()
        self.lock_box.setObjectName("notice")
        lb = QVBoxLayout(self.lock_box)
        lb.setContentsMargins(T.pad, T.gap, T.pad, T.gap)
        lb.setSpacing(2)
        msg = WrapLabel("השאילתה במירכאות, ולכן מחפשים ביטוי מדויק: המילים צמודות ולפי הסדר.")
        lb.addWidget(msg)
        self.unquote_btn = link_button("הסרת המירכאות")
        self.unquote_btn.clicked.connect(lambda: (self.close(), self.unquoteRequested.emit()))
        lb.addWidget(self.unquote_btn, 0, Qt.AlignRight)
        self.lay.addWidget(self.lock_box)

        self.body = QWidget()
        bl = QVBoxLayout(self.body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)
        bl.addWidget(_section("מרחק בין המילים"))
        self.r_adjacent = QRadioButton("צמודות")
        self.r_near = QRadioButton("עד")
        self.r_paragraph = QRadioButton("באותה פסקה")
        self.group = QButtonGroup(self)
        for i, r in enumerate((self.r_adjacent, self.r_near, self.r_paragraph)):
            r.setCursor(Qt.PointingHandCursor)
            self.group.addButton(r, i)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.r_adjacent)
        hint = QLabel('· למשל "איסור ייחוד"')
        hint.setObjectName("caption")
        row.addWidget(hint)
        row.addStretch(1)
        bl.addLayout(row)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.r_near)
        self.near = Stepper(1, 99, DEFAULTS["near"])
        self.near.setToolTip("כמה מילים מותר שיפרידו בין כל מילת חיפוש לבאה אחריה.\n"
                             "סימני פיסוק (פסיק, נקודה) אינם נחשבים מילה.")
        row.addWidget(self.near)
        row.addWidget(QLabel("מילים ביניהן"))
        row.addStretch(1)
        bl.addLayout(row)
        bl.addWidget(self.r_paragraph)
        bl.addSpacing(8)
        bl.addWidget(_section("סדר המילים"))
        self.order = Segmented([label for _, label in ORDER])
        self.order.setAccessibleName("סדר המילים")
        bl.addWidget(self.order)
        bl.addSpacing(8)
        bl.addWidget(_section("כמה מהמילים חייבות להופיע"))
        self.required = Combo()
        self.required.setToolTip("תוצאות עם כל המילים מדורגות תמיד לפני תוצאות חלקיות.")
        bl.addWidget(self.required)
        self.lay.addWidget(self.body)
        self.gap(4)
        self.lay.addWidget(_separator())
        self.foot = WrapLabel("חל כשמחפשים שתי מילים או יותר. שאילתה במירכאות מחפשת תמיד ביטוי מדויק.")
        self.foot.setObjectName("caption")
        self.lay.addWidget(self.foot)

        self.group.idClicked.connect(lambda i: settings.update(distance=DISTANCES[i]))
        self.near.valueChanged.connect(self._near_changed)
        self.order.changed.connect(lambda i: settings.update(ordered=ORDER[i][0]))
        self.required.currentIndexChanged.connect(self._required_changed)
        self.set_locked(False)
        self.sync()

    def _near_changed(self, v):
        # שינוי המספר בוחר גם את האפשרות "עד N מילים"
        self.settings.update(near=v, distance="near")

    def _required_changed(self, _i):
        if self.required.signalsBlocked():
            return
        self.settings.update(required=self.required.currentData() or 0)

    def set_locked(self, locked: bool):
        self.lock_box.setVisible(locked)
        self.body.setEnabled(not locked)

    def sync(self):
        s = self.settings
        for b in (self.r_adjacent, self.r_near, self.r_paragraph):
            b.blockSignals(True)
        self.group.button(DISTANCES.index(s.distance)).setChecked(True)
        for b in (self.r_adjacent, self.r_near, self.r_paragraph):
            b.blockSignals(False)
        self.near.setValue(s.near, emit=False)
        self.order.setIndex(0 if s.ordered else 1, animate=True)
        self.required.blockSignals(True)
        self.required.clear()
        for m, label in s.required_choices():
            self.required.addItem(label, m)
        idx = self.required.findData(s.required)
        self.required.setCurrentIndex(max(0, idx))
        self.required.setEnabled(s.n_terms >= 2)
        self.required.blockSignals(False)


class ScopePanel(Popup):
    """באילו אוספים מחפשים: אותם סימונים כמו בעץ האוספים, בלי לפתוח את הסרגל."""
    toggled = Signal(int, bool)
    allRequested = Signal()
    manageRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(T.pad * 26)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(T.pad + 4, T.pad + 2, T.pad + 4, T.pad)
        self.lay.setSpacing(4)
        self.lay.addWidget(_section("באילו אוספים לחפש"))
        self.rows = QVBoxLayout()
        self.rows.setSpacing(2)
        self.lay.addLayout(self.rows)
        self.lay.addSpacing(4)
        self.lay.addWidget(_separator())
        self.all_btn = link_button("סימון כל האוספים")
        self.all_btn.clicked.connect(self.allRequested)
        self.manage_btn = link_button("ניהול האוספים בסרגל…")
        self.manage_btn.clicked.connect(lambda: (self.close(), self.manageRequested.emit()))
        self.lay.addWidget(self.all_btn, 0, Qt.AlignRight)
        self.lay.addWidget(self.manage_btn, 0, Qt.AlignRight)
        self.boxes = {}

    def set_baskets(self, baskets, selected):
        """baskets: [(מזהה, שם, מספר מסמכים)]."""
        while self.rows.count():
            item = self.rows.takeAt(0)
            w = item.widget() or (item.layout() and None)
            if item.layout() is not None:
                while item.layout().count():
                    sub = item.layout().takeAt(0).widget()
                    if sub is not None:
                        sub.deleteLater()
            if w is not None:
                w.deleteLater()
        self.boxes = {}
        for bid, name, count in baskets:
            row = QHBoxLayout()
            row.setSpacing(T.gap)
            cb = QCheckBox(name)
            cb.setCursor(Qt.PointingHandCursor)
            cb.setChecked(bid in selected)
            cb.toggled.connect(lambda on, b=bid: self.toggled.emit(b, on))
            n = QLabel("מסמך אחד" if count == 1 else f"{count:,} מסמכים")
            n.setObjectName("caption")
            row.addWidget(cb, 1)
            row.addWidget(n)
            self.rows.addLayout(row)
            self.boxes[bid] = cb
        self.all_btn.setVisible(len(baskets) > 1)
        self.adjustSize()
