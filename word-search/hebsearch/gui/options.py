"""חלונית אפשרויות החיפוש: נפתחת מכפתור בשורת החיפוש, במקום לתפוס שורות קבועות על המסך."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ..search import SearchOptions
from .theme import T
from .widgets import Combo, Popup, Stepper, WrapLabel

AHEVI_CHOICES = [("none", "מדויק"), ("vy", "ו׳ י׳ – כתיב מלא וחסר"), ("all", "כל אותיות אהו״י")]
DEFAULTS = {"prefixes": True, "inflect": False, "ahevi": 0, "gap": 0, "paragraph": False, "ordered": True}


class OptionsPopup(Popup):
    changed = Signal()
    helpRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(T.pad * 36)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(T.pad + 2, T.pad + 2, T.pad + 2, T.pad)
        lay.setSpacing(T.gap)

        title = QLabel("אפשרויות חיפוש")
        title.setObjectName("title")
        lay.addWidget(title)

        self.cb_prefixes = QCheckBox("אותיות שימוש (ו, ה, ש, ב, כ, ל, מ)")
        self.cb_prefixes.setToolTip("למשל: חיפוש 'דרך' ימצא גם 'בדרך', 'והדרך', 'כשבדרך'")
        self.cb_inflect = QCheckBox("הטיות (הלך ← הלכה, הליכה, הולכים, וילך…)")
        self.cb_inflect.setToolTip(
            "מוצא צורות נוספות של המילה: סיומות, תחיליות ותנועות בתוך המילה.\n"
            "זהו קירוב – צורות חריגות כמו בית/בתים לא נמצאות.")
        lay.addWidget(self.cb_prefixes)
        lay.addWidget(self.cb_inflect)

        row = QHBoxLayout()
        row.setSpacing(T.gap)
        row.addWidget(QLabel("אותיות אהו״י:"))
        self.ahevi = Combo()
        for _, label in AHEVI_CHOICES:
            self.ahevi.addItem(label)
        self.ahevi.setToolTip("כמה לסבול הבדלים באותיות אהו״י: 'שמרה' ימצא גם 'שמירה', 'שומרה'")
        row.addWidget(self.ahevi, 1)
        lay.addLayout(row)

        sep = QFrame()
        sep.setObjectName("separator")
        lay.addWidget(sep)

        lbl = QLabel("בחיפוש של כמה מילים")
        lbl.setObjectName("caption")
        lay.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(T.gap)
        row.addWidget(QLabel("רווח בין המילים – עד"))
        self.gap = Stepper(0, 99, 0)
        self.gap.setToolTip("כמה מילים מותר שיפרידו בין כל מילת חיפוש לבאה אחריה.\n0 = המילים צמודות זו לזו (צירוף מדויק)")
        row.addWidget(self.gap)
        row.addWidget(QLabel("מילים"))
        row.addStretch(1)
        lay.addLayout(row)
        hint = WrapLabel("0 = המילים צמודות זו לזו, בלי מילה ביניהן. סימני פיסוק (פסיק, נקודה) אינם נחשבים מילה.")
        hint.setObjectName("caption")
        lay.addWidget(hint)
        self.cb_paragraph = QCheckBox("בכל מקום באותה פסקה")
        self.cb_ordered = QCheckBox("שמירה על סדר המילים")
        lay.addWidget(self.cb_paragraph)
        lay.addWidget(self.cb_ordered)

        self.required_row = QWidget()
        rr = QHBoxLayout(self.required_row)
        rr.setContentsMargins(0, 0, 0, 0)
        rr.setSpacing(T.gap)
        rr.addWidget(QLabel("מילים נדרשות:"))
        self.required = Combo()
        self.required.setToolTip("כמה ממילות החיפוש חייבות להופיע יחד.\nתוצאות עם כל המילים מדורגות תמיד לפני תוצאות חלקיות.")
        rr.addWidget(self.required, 1)
        lay.addWidget(self.required_row)
        self.required_row.hide()

        sep2 = QFrame()
        sep2.setObjectName("separator")
        lay.addWidget(sep2)
        bottom = QHBoxLayout()
        help_btn = QPushButton("חיפוש מתקדם (*  ?  |  -)")
        help_btn.setObjectName("flat")
        help_btn.clicked.connect(lambda: (self.close(), self.helpRequested.emit()))
        reset = QPushButton("איפוס")
        reset.setObjectName("flat")
        reset.clicked.connect(self.reset)
        bottom.addWidget(help_btn)
        bottom.addStretch(1)
        bottom.addWidget(reset)
        lay.addLayout(bottom)

        for cb in (self.cb_prefixes, self.cb_inflect, self.cb_paragraph, self.cb_ordered):
            cb.toggled.connect(self._changed)
        self.ahevi.currentIndexChanged.connect(self._changed)
        self.gap.valueChanged.connect(self._changed)
        self.required.currentIndexChanged.connect(self._changed)
        self.cb_paragraph.toggled.connect(lambda on: self.gap.setEnabled(not on))
        self.reset(emit=False)

    # ----- מצב -----
    def _changed(self, *_):
        self.changed.emit()

    def reset(self, emit=True):
        widgets = (self.cb_prefixes, self.cb_inflect, self.cb_paragraph, self.cb_ordered, self.ahevi, self.gap,
                   self.required)
        for w in widgets:
            w.blockSignals(True)
        self.cb_prefixes.setChecked(DEFAULTS["prefixes"])
        self.cb_inflect.setChecked(DEFAULTS["inflect"])
        self.cb_paragraph.setChecked(DEFAULTS["paragraph"])
        self.cb_ordered.setChecked(DEFAULTS["ordered"])
        self.ahevi.setCurrentIndex(DEFAULTS["ahevi"])
        self.gap.setValue(DEFAULTS["gap"], emit=False)
        self.gap.setEnabled(True)
        if self.required.count():
            self.required.setCurrentIndex(0)
        for w in widgets:
            w.blockSignals(False)
        if emit:
            self.changed.emit()

    def set_term_count(self, n: int):
        """מעדכן את בחירת "מילים נדרשות" לפי מספר המילים בשאילתה (מוצגת רק בשתי מילים ומעלה)."""
        current = self.required.currentData() or 0
        self.required.blockSignals(True)
        self.required.clear()
        if n > 1:
            self.required.addItem(f"כל {n} המילים", 0)
            for m in range(n - 1, 0, -1):
                self.required.addItem("לפחות אחת מהן" if m == 1 else f"לפחות {m} מתוך {n}", m)
            idx = self.required.findData(current) if current and current < n else 0
            self.required.setCurrentIndex(max(0, idx))
        self.required.blockSignals(False)
        self.required_row.setVisible(n > 1)

    def options(self) -> SearchOptions:
        return SearchOptions(
            prefixes=self.cb_prefixes.isChecked(),
            inflections=self.cb_inflect.isChecked(),
            ahevi=AHEVI_CHOICES[self.ahevi.currentIndex()][0],
            max_gap=self.gap.value(),
            whole_paragraph=self.cb_paragraph.isChecked(),
            ordered=self.cb_ordered.isChecked(),
            min_terms=self.required.currentData() or 0,
        )

    def non_default(self) -> int:
        """כמה אפשרויות שונות מברירת המחדל (להצגת מספר על הכפתור)."""
        n = 0
        n += self.cb_prefixes.isChecked() != DEFAULTS["prefixes"]
        n += self.cb_inflect.isChecked() != DEFAULTS["inflect"]
        n += self.ahevi.currentIndex() != DEFAULTS["ahevi"]
        n += self.cb_paragraph.isChecked() != DEFAULTS["paragraph"]
        n += (self.gap.value() != DEFAULTS["gap"]) and not self.cb_paragraph.isChecked()
        n += self.cb_ordered.isChecked() != DEFAULTS["ordered"]
        n += bool(self.required.currentData())
        return int(n)

    def describe(self) -> str:
        """תיאור קצר של האפשרויות הפעילות (להצגה ליד התוצאות)."""
        parts = []
        if not self.cb_prefixes.isChecked():
            parts.append("בלי אותיות שימוש")
        if self.cb_inflect.isChecked():
            parts.append("הטיות")
        if self.ahevi.currentIndex():
            parts.append("אהו״י")
        if self.cb_paragraph.isChecked():
            parts.append("בכל הפסקה")
        elif self.gap.value():
            parts.append(f"רווח עד {self.gap.value()}")
        if not self.cb_ordered.isChecked():
            parts.append("בכל סדר")
        if self.required.currentData():
            parts.append(self.required.currentText())
        return " · ".join(parts)

    # ----- שמירה -----
    def restore(self, s: QSettings):
        widgets = (self.cb_prefixes, self.cb_inflect, self.cb_paragraph, self.cb_ordered, self.ahevi, self.gap)
        for w in widgets:
            w.blockSignals(True)
        self.cb_prefixes.setChecked(s.value("prefixes", DEFAULTS["prefixes"], bool))
        self.cb_inflect.setChecked(s.value("inflect", DEFAULTS["inflect"], bool))
        self.ahevi.setCurrentIndex(int(s.value("ahevi", DEFAULTS["ahevi"])))
        self.gap.setValue(int(s.value("gap", DEFAULTS["gap"])), emit=False)
        self.cb_paragraph.setChecked(s.value("paragraph", DEFAULTS["paragraph"], bool))
        self.cb_ordered.setChecked(s.value("ordered", DEFAULTS["ordered"], bool))
        self.gap.setEnabled(not self.cb_paragraph.isChecked())
        for w in widgets:
            w.blockSignals(False)

    def save(self, s: QSettings):
        s.setValue("prefixes", self.cb_prefixes.isChecked())
        s.setValue("inflect", self.cb_inflect.isChecked())
        s.setValue("ahevi", self.ahevi.currentIndex())
        s.setValue("gap", self.gap.value())
        s.setValue("paragraph", self.cb_paragraph.isChecked())
        s.setValue("ordered", self.cb_ordered.isChecked())
