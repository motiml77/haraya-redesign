"""מערכת העיצוב: צבעים, מידות, פלטה ו-QSS – מקור אחד לכל הממשק.

עקרונות:
  * מידות בפיקסלים לוגיים (Qt מכפיל אותן אוטומטית ב-DPI של המסך), בסולם של 4px.
  * צפיפות של תוכנת עבודה מקצועית: כתב בסיס 13px, כיתוב קטן 12px (המינימום ש-
    Microsoft ממליצה עליו), בקרות בגובה 28px ושדה חיפוש בגובה 32px.
    טקסט התוצאות (תוכן לקריאה, עם ניקוד) גדול מעט יותר – 15px.
  * ערכת נושא בהירה קבועה: Fusion + פלטה מפורשת. בלי זה, בחלונות במצב כהה Qt
    צובע בשחור כל אזור שה-QSS לא מכסה (תיבות סימון, פסי גלילה, רקעים).
  * "זום" (Ctrl +/-) מכפיל את כל המידות יחד, כך שהפרופורציות נשמרות.
"""

from __future__ import annotations

import sys
import weakref

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory


class C:
    """צבעים."""
    bg = "#f3f4f7"            # רקע החלון
    chrome = "#f1f3f7"        # המסגרת: סרגל הסלים ושורת המצב
    surface = "#ffffff"       # כרטיסים, רשימות
    surface_alt = "#f7f8fa"   # שורות לסירוגין, שדות
    well = "#f4f5f8"          # השקע שבו מוצגים כרטיסי התוצאות
    hover = "#eef1f7"
    track = "#eceff4"         # מסילה של בורר מקטעים
    track_hover = "#e2e6ed"
    border = "#e1e5ec"
    border_strong = "#c8cfdb"
    text = "#1c2330"
    text2 = "#4a5568"
    muted = "#7b8596"
    accent = "#2563eb"
    accent_hover = "#1e4fc7"
    accent_pressed = "#1a43a8"
    accent_soft = "#eaf1ff"
    accent_sel = "#d6e4ff"
    ok = "#13803d"
    ok_bg = "#dff5e6"
    warn = "#a55a00"
    warn_bg = "#fdf0d5"
    danger = "#c0262d"
    marker = "#ffe94a"        # מרקר צהוב
    marker_text = "#1c2330"
    current = "#ff9f1c"       # התוצאה הנוכחית במציג המסמך


class _Theme:
    """מידות לפי זום. אובייקט יחיד (T) שמתעדכן במקום."""

    BASE = {
        "caption": 12, "body": 13, "title": 14, "input": 14, "snippet": 15, "result": 14, "hero": 20,
        "h_ctl": 28, "h_search": 32, "h_row": 26, "h_chip": 24, "h_tab": 32,
        "pad": 10, "gap": 8, "radius": 6, "radius_lg": 8, "icon": 16,
    }

    def __init__(self):
        self.zoom = 1.0
        self.family = ""
        self._sized = []
        self.set_zoom(1.0)

    def set_zoom(self, zoom: float):
        self.zoom = max(0.7, min(1.8, round(zoom, 2)))
        for key, value in self.BASE.items():
            setattr(self, key, max(1, round(value * self.zoom)))
        self.apply_sized()

    # ----- גבהים שמתעדכנים בזום -----
    def sized(self, widget, **dims):
        """מקבע מידות של ווידג'ט לפי שמות מידות (h_ctl, h_search…) ורושם אותן לעדכון בזום."""
        self._sized.append((weakref.ref(widget), dims))
        self._apply_one(widget, dims)
        return widget

    def _apply_one(self, widget, dims):
        for dim, token in dims.items():
            value = getattr(self, token) if isinstance(token, str) else token() if callable(token) else token
            if dim == "h":
                widget.setFixedHeight(value)
            elif dim == "w":
                widget.setFixedWidth(value)
            elif dim == "min_h":
                widget.setMinimumHeight(value)
            elif dim == "min_w":
                widget.setMinimumWidth(value)
            elif dim == "max_w":
                widget.setMaximumWidth(value)
            elif dim == "size":
                widget.setFixedSize(value, value)
            elif dim == "icon":
                widget.setIconSize(QSize(value, value))

    def apply_sized(self):
        alive = []
        for ref, dims in self._sized:
            w = ref()
            if w is not None:
                try:
                    self._apply_one(w, dims)
                    alive.append((ref, dims))
                except RuntimeError:  # הווידג'ט נמחק
                    pass
        self._sized = alive


T = _Theme()


def make_palette() -> QPalette:
    p = QPalette()
    roles = {
        QPalette.Window: C.bg, QPalette.WindowText: C.text, QPalette.Base: C.surface,
        QPalette.AlternateBase: C.surface_alt, QPalette.ToolTipBase: C.text, QPalette.ToolTipText: "#ffffff",
        QPalette.Text: C.text, QPalette.Button: C.surface, QPalette.ButtonText: C.text,
        QPalette.BrightText: "#ffffff", QPalette.Link: C.accent, QPalette.LinkVisited: C.accent_pressed,
        QPalette.Highlight: C.accent, QPalette.HighlightedText: "#ffffff",
        QPalette.Light: "#ffffff", QPalette.Midlight: "#eceff5", QPalette.Mid: C.border_strong,
        QPalette.Dark: "#9aa4b5", QPalette.Shadow: "#000000", QPalette.PlaceholderText: C.muted,
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    disabled = {QPalette.WindowText: "#a3acbb", QPalette.Text: "#a3acbb", QPalette.ButtonText: "#a3acbb",
                QPalette.Highlight: "#c3cde0", QPalette.HighlightedText: "#ffffff"}
    for role, color in disabled.items():
        p.setColor(QPalette.Disabled, role, QColor(color))
    if hasattr(QPalette, "Accent"):          # Qt 6.6+
        p.setColor(QPalette.Accent, QColor(C.accent))
    return p


_INDICATORS = {
    "check": '<path d="M3.6 8.3l2.9 2.9 5.9-6.3" fill="none" stroke="#ffffff" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round"/>',
    "dash": '<path d="M4.2 8h7.6" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>',
}


def _indicator(name: str) -> str:
    """סמני תיבת סימון (V, מקף) כקובצי SVG קטנים – ה-QSS יכול לצייר תמונה רק מקובץ."""
    import os
    import tempfile
    folder = os.path.join(tempfile.gettempdir(), "hebdocsearch-ui")
    path = os.path.join(folder, f"{name}.svg")
    if not os.path.exists(path):
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">'
                    f'{_INDICATORS[name]}</svg>')
    return path.replace("\\", "/")


def build_qss() -> str:
    """כל העיצוב. מערכת הכפתורים:
        primary   – פעולה ראשית אחת בכל אזור (חיפוש, סיום): מילוי כחול עם עומק עדין
        (ברירת מחדל) – משני: לבן עם מסגרת וקו תחתון כהה מעט, כמו כפתור מוגבה
        soft      – פעולה חיובית שאינה ראשית (סל חדש): רקע כחול בהיר
        link      – פעולה טקסטואלית (ברירת מחדל, עזרה): בלי מסגרת, רקע רק במעבר עכבר
        ghost     – כפתור סמל (QToolButton): שקוף, רקע במעבר עכבר, כחול כשהוא דלוק
        formchip  – שבב סינון קטן; OptionChip ו-Segmented מצוירים בקוד (widgets.py)."""
    t = T
    check, dash = _indicator("check"), _indicator("dash")
    return f"""
* {{ outline: 0; }}
QWidget {{ color: {C.text}; font-size: {t.body}px; }}
QMainWindow, QDialog, QMessageBox {{ background: {C.bg}; }}
#central {{ background: {C.chrome}; }}
#panel {{ background: {C.surface}; border: 1px solid {C.border}; border-radius: {t.radius_lg}px; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: {t.title}px; font-weight: 600; }}
QLabel#muted {{ color: {C.muted}; }}
QLabel#caption {{ color: {C.muted}; font-size: {t.caption}px; }}
QLabel#section {{ color: {C.text2}; font-size: {t.caption}px; font-weight: 600; }}
QLabel#summary {{ color: {C.text2}; }}
QLabel#hero {{ font-size: {t.hero}px; font-weight: 600; color: {C.accent}; }}
QLabel#percent {{ font-size: {t.hero + 6}px; font-weight: 600; color: {C.accent}; }}
QToolTip {{ background: {C.text}; color: #ffffff; border: none; padding: 4px 8px; font-size: {t.caption}px; }}

/* ---------- המסגרת: סרגל | תוכן ---------- */
QSplitter#frame::handle {{ background: {C.chrome}; }}
QSplitter#frame::handle:hover {{ background: {C.accent_sel}; }}
#sidebar {{ background: {C.chrome}; border: none; }}
#content {{ background: {C.surface}; border: none; border-right: 1px solid {C.border}; }}
#header {{ background: {C.surface}; border: none; border-bottom: 1px solid {C.border}; }}
#reshead {{ background: {C.surface}; border: none; border-bottom: 1px solid {C.border}; }}
QSplitter#well {{ background: {C.well}; }}
QSplitter#well::handle {{ background: {C.border}; }}
QListWidget#doclist {{ background: {C.surface}; border: none; border-radius: 0; padding: 4px; }}
QListView#results {{ background: {C.well}; border: none; border-radius: 0; }}

/* ---------- כפתור משני (ברירת מחדל) ---------- */
QPushButton {{
    background: {C.surface}; color: {C.text}; border: 1px solid {C.border_strong}; border-bottom-color: #b3bccb;
    border-radius: {t.radius}px; padding: 0 {t.pad + 2}px; min-height: {t.h_ctl - 2}px;
}}
QPushButton:hover {{ background: #f7f9fc; border-color: #aeb8c9; border-bottom-color: #9ea9bc; }}
QPushButton:pressed {{ background: {C.hover}; border-color: #aeb8c9; padding-top: 1px; }}
QPushButton:disabled {{ color: #a3acbb; background: {C.surface_alt}; border-color: {C.border}; }}

/* ---------- ראשי ---------- */
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a7af3, stop:1 {C.accent});
    color: #ffffff; border: 1px solid #1f58d8; border-bottom-color: #1a48b4; font-weight: 600;
    border-radius: {t.radius}px; padding: 0 {t.pad + 10}px; min-height: {t.h_ctl - 2}px;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2f6ff0, stop:1 {C.accent_hover});
    border-color: #1a4cc0;
}}
QPushButton#primary:pressed {{ background: {C.accent_pressed}; border-color: {C.accent_pressed}; padding-top: 1px; }}
QPushButton#primary:disabled {{ background: #a9c2f5; border-color: #a9c2f5; color: #ffffff; }}

/* ---------- רך ---------- */
QPushButton#soft, QToolButton#soft {{
    background: {C.accent_soft}; color: {C.accent}; border: 1px solid #d3e0fc; font-weight: 600;
    border-radius: {t.radius}px; padding: 0 {t.pad}px;
}}
QPushButton#soft:hover, QToolButton#soft:hover {{ background: {C.accent_sel}; border-color: #b7cdfb; }}
QPushButton#soft:pressed, QToolButton#soft:pressed {{ background: #c4d6fd; }}

/* ---------- קישור ---------- */
QPushButton#link, QPushButton#flat {{
    background: transparent; color: {C.accent}; border: 1px solid transparent; border-radius: {t.radius}px;
    padding: 0 {t.gap}px; min-height: {t.h_chip - 2}px;
}}
QPushButton#link:hover, QPushButton#flat:hover {{ background: {C.accent_soft}; color: {C.accent_hover}; }}
QPushButton#link:pressed, QPushButton#flat:pressed {{ background: {C.accent_sel}; }}

/* ---------- שבב סינון (צורות שנמצאו) ---------- */
QPushButton#formchip {{
    background: {C.surface}; color: {C.accent}; border: 1px solid #d3e0fc; border-radius: {t.h_chip // 2}px;
    padding: 0 {t.gap + 2}px; min-height: {t.h_chip - 2}px; font-size: {t.caption}px;
}}
QPushButton#formchip:hover {{ background: {C.accent_soft}; border-color: #b7cdfb; }}
QPushButton#formchip:checked {{ background: {C.accent}; color: #ffffff; border-color: {C.accent}; font-weight: 600; }}

/* ---------- כפתור סמל (רפאים) ---------- */
QToolButton {{
    background: transparent; border: 1px solid transparent; border-radius: {t.radius}px;
    padding: 0 {t.gap}px; color: {C.text2}; min-height: {t.h_ctl - 2}px;
}}
QToolButton:hover {{ background: {C.hover}; }}
QToolButton:pressed {{ background: #e2e7ef; }}
QToolButton:checked {{ background: {C.accent_soft}; border-color: #d3e0fc; color: {C.accent}; }}
QToolButton:checked:hover {{ background: {C.accent_sel}; }}
QToolButton:disabled {{ color: #b4bcc9; }}
QToolButton::menu-indicator {{ image: none; width: 0px; }}
QToolButton#bordered {{ border-color: {C.border_strong}; border-bottom-color: #b3bccb; background: {C.surface}; }}
QToolButton#bordered:hover {{ background: #f7f9fc; border-color: #aeb8c9; }}
QToolButton#fab {{
    background: {C.surface}; border: 1px solid {C.border_strong}; border-radius: {(t.h_ctl + 4) // 2}px; padding: 0;
}}
QToolButton#fab:hover {{ background: {C.accent_soft}; border-color: {C.accent}; }}

/* ---------- בורר מספרי ---------- */
QFrame#stepper {{ background: {C.surface}; border: 1px solid {C.border_strong}; border-radius: {t.radius}px; }}
QFrame#stepper:disabled {{ background: {C.surface_alt}; border-color: {C.border}; }}
QFrame#stepper QLabel {{ font-weight: 600; }}
QToolButton#step {{ border: none; border-radius: {t.radius - 1}px; background: transparent; min-height: 0; padding: 0; }}
QToolButton#step:hover {{ background: {C.hover}; }}
QToolButton#step:pressed {{ background: {C.accent_sel}; }}
QToolButton#step:disabled {{ background: transparent; }}

/* ---------- שדות ---------- */
QLineEdit {{
    background: {C.surface}; border: 1px solid {C.border_strong}; border-radius: {t.radius}px;
    padding: 0 {t.gap}px; min-height: {t.h_ctl - 2}px; selection-background-color: {C.accent_sel};
    selection-color: {C.text};
}}
QLineEdit:hover {{ border-color: #aeb8c9; }}
QLineEdit:focus {{ border: 1px solid {C.accent}; }}
QLineEdit#search {{
    font-size: {t.input}px; min-height: {t.h_search - 2}px; padding: 0 {t.gap}px 1px {t.gap}px;
    background: {C.surface_alt}; border-radius: {t.radius_lg}px;
}}
QLineEdit#search:hover {{ background: {C.surface}; }}
QLineEdit#search:focus {{ background: {C.surface}; border: 1px solid {C.accent}; border-bottom: 2px solid {C.accent}; padding-bottom: 0; }}
QLineEdit:disabled {{ background: {C.surface_alt}; color: #a3acbb; }}
QLineEdit QToolButton {{ min-height: 0; min-width: 0; padding: 0; border: none; background: transparent; }}

QComboBox {{
    background: {C.surface}; border: 1px solid {C.border_strong}; border-bottom-color: #b3bccb;
    border-radius: {t.radius}px; padding: 0 {t.gap}px; min-height: {t.h_ctl - 2}px;
}}
QComboBox:hover {{ border-color: #aeb8c9; background: #f7f9fc; }}
QComboBox:focus, QComboBox:on {{ border-color: {C.accent}; }}
QComboBox:disabled {{ background: {C.surface_alt}; color: #a3acbb; border-color: {C.border}; }}
QComboBox::drop-down {{ width: 20px; border: none; }}
QComboBox QAbstractItemView {{
    background: {C.surface}; border: 1px solid {C.border_strong}; selection-background-color: {C.accent_soft};
    selection-color: {C.accent}; padding: 2px; outline: 0;
}}
QComboBox QAbstractItemView::item {{ min-height: {t.h_ctl - 4}px; padding: 0 {t.gap}px; }}

/* ---------- תיבות סימון וכפתורי בחירה ---------- */
QCheckBox, QRadioButton {{ spacing: 7px; min-height: {t.h_ctl - 6}px; background: transparent; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: #a3acbb; }}
QCheckBox::indicator, QTreeView::indicator {{
    width: 15px; height: 15px; border: 1.5px solid #9aa5b8; border-radius: 4px; background: {C.surface};
}}
QCheckBox::indicator:hover, QTreeView::indicator:hover {{ border-color: {C.accent}; }}
QCheckBox::indicator:checked, QTreeView::indicator:checked {{
    background: {C.accent}; border-color: {C.accent}; image: url("{check}");
}}
QCheckBox::indicator:indeterminate, QTreeView::indicator:indeterminate {{
    background: {C.accent}; border-color: {C.accent}; image: url("{dash}");
}}
QCheckBox::indicator:disabled {{ background: {C.surface_alt}; border-color: {C.border_strong}; }}
QRadioButton::indicator {{
    width: 15px; height: 15px; border: 1.5px solid #9aa5b8; border-radius: 8px; background: {C.surface};
}}
QRadioButton::indicator:hover {{ border-color: {C.accent}; }}
QRadioButton::indicator:checked {{
    border-color: {C.accent};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                stop:0 {C.accent}, stop:0.48 {C.accent}, stop:0.56 {C.surface}, stop:1 {C.surface});
}}
QRadioButton::indicator:disabled {{ border-color: {C.border_strong}; }}

QMenu {{ background: {C.surface}; border: 1px solid {C.border_strong}; border-radius: {t.radius_lg}px; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}
QMenu::item:selected {{ background: {C.accent_soft}; color: {C.accent}; }}
QMenu::item:disabled {{ color: #a3acbb; }}
QMenu::separator {{ height: 1px; background: {C.border}; margin: 4px 6px; }}

QTabWidget::pane {{ border: none; }}
QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
QTabBar::tab {{
    background: transparent; color: {C.text2}; padding: 0 {t.pad}px; min-height: {t.h_tab - 3}px;
    border: none; border-bottom: 2px solid transparent; margin-left: 2px;
}}
QTabBar::tab:selected {{ color: {C.accent}; border-bottom: 2px solid {C.accent}; font-weight: 600; }}
QTabBar::tab:hover:!selected {{ color: {C.text}; background: {C.hover}; border-top-left-radius: 4px; border-top-right-radius: 4px; }}

QAbstractItemView {{
    background: {C.surface}; alternate-background-color: {C.surface_alt}; border: 1px solid {C.border};
    border-radius: {t.radius}px; outline: 0; selection-background-color: {C.accent_sel}; selection-color: {C.text};
}}
QListView#plain, QTreeView#plain {{ border: none; }}
QTreeView#nav {{ background: transparent; border: none; }}
QTreeView::item {{ min-height: {t.h_row}px; padding-right: 2px; }}
QTreeView::item:hover {{ background: #e6eaf1; }}
QTreeView::item:selected {{ background: {C.accent_sel}; color: {C.text}; }}
QListWidget::item {{ min-height: {t.h_row}px; padding: 0 {t.gap}px; border-radius: {t.radius}px; }}
QListWidget::item:hover {{ background: {C.hover}; }}
QListWidget::item:selected {{ background: {C.accent_soft}; color: {C.accent}; }}
QHeaderView::section {{
    background: {C.surface_alt}; border: none; border-bottom: 1px solid {C.border}; padding: 4px 6px; color: {C.muted};
}}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #c3cad7; min-height: 40px; border-radius: 4px; margin: 2px 3px 2px 3px; }}
QScrollBar::handle:vertical:hover {{ background: #9aa5b8; margin: 2px 2px 2px 2px; }}
QScrollBar::handle:vertical:pressed {{ background: {C.accent}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #c3cad7; min-width: 40px; border-radius: 4px; margin: 3px 2px; }}
QScrollBar::handle:horizontal:hover {{ background: #9aa5b8; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; background: none; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QAbstractScrollArea#results QScrollBar:vertical {{ background: transparent; width: 14px; border: none; }}
QAbstractScrollArea#results QScrollBar::handle:vertical {{ margin: 3px 3px; min-height: 48px; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 8px; }}
QSplitter::handle:horizontal:hover {{ background: {C.accent_sel}; }}
QSplitter::handle:vertical {{ height: 8px; }}

QProgressBar {{ border: none; background: {C.border}; border-radius: 3px; max-height: 6px; min-height: 6px; text-align: center; }}
QProgressBar::chunk {{ background: {C.accent}; border-radius: 3px; }}

/* ---------- שורת מצב ---------- */
QStatusBar {{ background: {C.chrome}; color: {C.muted}; border-top: 1px solid {C.border}; font-size: {t.caption}px; }}
QStatusBar::item {{ border: none; }}
QStatusBar QToolButton {{ min-height: 0; padding: 0; }}
QFrame#zoombox {{ background: transparent; border: none; }}
QPushButton#zoomvalue {{
    background: transparent; border: 1px solid transparent; border-radius: {t.radius}px; color: {C.text2};
    font-size: {t.caption}px; padding: 0 6px; min-height: 0; min-width: 40px;
}}
QPushButton#zoomvalue:hover {{ background: {C.hover}; }}

QTextBrowser {{ border: none; background: transparent; }}

/* ---------- מציג מסמך ---------- */
#viewer {{ background: {C.well}; }}
#pagearea {{ background: {C.well}; }}
QTextBrowser#page {{
    background: {C.surface}; border: 1px solid {C.border}; border-bottom: none;
    border-top-left-radius: {t.radius_lg}px; border-top-right-radius: {t.radius_lg}px;
}}
QFrame#navgroup {{ background: {C.surface}; border: 1px solid {C.border_strong}; border-radius: {t.radius}px; }}
QFrame#navgroup QToolButton {{ border-radius: {t.radius - 1}px; }}
QLabel#counter {{ color: {C.text2}; font-weight: 600; padding: 0 {t.gap}px; min-width: 60px; }}
QFrame#vsep {{ background: {C.border}; min-width: 1px; max-width: 1px; border: none; }}
QFrame#popup {{ background: {C.surface}; border: 1px solid {C.border_strong}; border-radius: {t.radius_lg}px; }}
QFrame#notice {{ background: {C.accent_soft}; border: 1px solid #d3e0fc; border-radius: {t.radius}px; }}
QFrame#separator {{ background: {C.border}; max-height: 1px; min-height: 1px; border: none; }}
"""


_SYSTEM_FAMILY = None
_STYLE_SET = False


def system_family() -> str:
    global _SYSTEM_FAMILY
    if _SYSTEM_FAMILY is None:
        app = QApplication.instance()
        fam = app.font().family() if app else ""
        if sys.platform == "win32" and (not fam or fam.lower() in ("sans serif", "ms shell dlg 2", "ms shell dlg")):
            fam = "Segoe UI"
        _SYSTEM_FAMILY = fam or "Sans Serif"
    return _SYSTEM_FAMILY


def read_font_css() -> str:
    """משפחת הגופנים לטקסט קריאה בתוך HTML (מציג המסמכים)."""
    return f"'{system_family()}', 'Segoe UI', 'Arial', 'Noto Sans Hebrew', sans-serif"


def ui_font(px: int | None = None, weight: int | None = None) -> QFont:
    f = QFont(system_family())
    f.setPixelSize(px or T.body)
    if weight is not None:
        f.setWeight(QFont.Weight(weight))
    return f


def apply(app: QApplication, zoom: float | None = None):
    """מחיל על האפליקציה את העיצוב: סגנון Fusion, פלטה בהירה, גופן ו-QSS."""
    system_family()
    if zoom is not None:
        T.set_zoom(zoom)
    global _STYLE_SET
    if not _STYLE_SET:
        app.setStyle(QStyleFactory.create("Fusion"))
        _STYLE_SET = True
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):           # Qt 6.8+: מתעלם ממצב כהה של מערכת ההפעלה
        hints.setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(make_palette())
    app.setFont(ui_font(T.body))
    app.setStyleSheet(build_qss())


def fit_geometry(avail: QRect, want_w: int = 1180, want_h: int = 740, fraction: float = 0.9) -> QRect:
    """גודל וקבוע התחלתי של החלון: בתוך השטח הפנוי של המסך (בלי שורת המשימות), ממורכז."""
    w = max(320, min(want_w, int(avail.width() * fraction), avail.width()))
    h = max(240, min(want_h, int(avail.height() * fraction), avail.height()))
    x = avail.x() + (avail.width() - w) // 2
    y = avail.y() + (avail.height() - h) // 2
    return QRect(x, y, w, h)


def default_zoom(avail: QRect) -> float:
    """זום התחלתי לפי גובה המסך: מסכים נמוכים (למשל 768 או חלונות ב-150%) מקבלים תצוגה צפופה יותר."""
    h = avail.height()
    if h <= 640:
        return 0.9
    if h <= 760:
        return 0.95
    return 1.0
