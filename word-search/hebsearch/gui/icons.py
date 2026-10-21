"""אייקונים.

  * סמלי ממשק (חיפוש, תיקייה, רענון…) – SVG קטן שנצבע ומצויר בקוד, בכל גודל וצבע, חד בכל DPI.
  * סמלי קבצים – הסמלים של מערכת ההפעלה: בחלונות אלה הסמלים של וורד, PDF והתיקיות כפי שהם
    מוצגים בסייר (נשלפים לפי הסיומת, פעם אחת לכל סוג, ולא לפי כל קובץ – כדי לא להאט).
    אם המערכת לא מחזירה סמל (או מחזירה סמל כללי בלבד), נעשה שימוש בסמל מצויר (W / PDF).
"""

from __future__ import annotations

import os
from functools import lru_cache

from PySide6.QtCore import QByteArray, QFileInfo, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFileIconProvider

from ..extract import DOC_EXTS, PDF_EXTS
from .theme import C

# ---------------------------------------------------------------- סמלי ממשק (viewBox 24x24)
_FOLDER = ('<path d="M3.5 6.5A1.5 1.5 0 0 1 5 5h4.2a1.5 1.5 0 0 1 1.1.5l1.2 1.3H19a1.5 1.5 0 0 1 1.5 1.5v9.2'
           'A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z"/>')
_FILE = ('<path d="M7.5 3.5h6L19 9v10a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 6 19V5a1.5 1.5 0 0 1 1.5-1.5z"/>'
         '<path d="M13.5 3.5V9H19"/>')

_SVG = {
    "search": '<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5.5 5.5"/>',
    "folder": _FOLDER,
    "folder-plus": _FOLDER + '<path d="M12 10.5v5M9.5 13h5"/>',
    "file": _FILE,
    "file-plus": _FILE + '<path d="M12.2 12.5v5M9.7 15h5"/>',
    "refresh": '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5V9H15"/>',
    "sliders": '<path d="M4 7h8M16 7h4M4 17h4M12 17h8"/><circle cx="14" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5"/><path d="M12 8h.01"/>',
    "trash": '<path d="M5 7h14"/><path d="M9.5 7V5h5v2"/><path d="M7 7l.8 12h8.4L17 7"/>',
    "pencil": '<path d="M5 19l.8-3.8L15.5 5.5a1.8 1.8 0 0 1 2.5 0l.5.5a1.8 1.8 0 0 1 0 2.5L8.8 18.2z"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "chevron-down": '<path d="M6.5 9.5l5.5 5.5 5.5-5.5"/>',
    "chevron-up": '<path d="M6.5 14.5l5.5-5.5 5.5 5.5"/>',
    "x": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "arrow-up": '<path d="M12 19V5.5M6 11.5l6-6 6 6"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    "external": ('<path d="M13.5 4.5h6v6"/><path d="M19.5 4.5L11 13"/>'
                 '<path d="M17.5 14v4a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V8A1.5 1.5 0 0 1 6 6.5h4"/>'),
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "warning": '<path d="M12 4.5l8.5 14.5h-17z"/><path d="M12 10v4.5"/><path d="M12 17h.01"/>',
    "more": '<circle cx="6" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="18" cy="12" r="1.3"/>',
    "sidebar": '<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M15 5v14"/>',
    "copy": '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6.5a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2"/>',
    "up-folder": _FOLDER + '<path d="M12 16v-5M9.8 13l2.2-2.2L14.2 13"/>',
    "expand": '<path d="M14 4.5h5.5V10M10 19.5H4.5V14M19.5 4.5L13.5 10.5M4.5 19.5l6-6"/>',
    "home": '<path d="M4.5 11L12 4.5l7.5 6.5"/><path d="M6.5 9.5V19h11V9.5"/>',
    "drive": '<rect x="3.5" y="8" width="17" height="8" rx="2"/><path d="M16.5 12h.01M13.5 12h.01"/>',
}

_NORMAL, _ACTIVE, _DISABLED = C.text2, C.accent, "#b4bcc9"


def _svg_pixmap(name: str, color: str, size: int) -> QPixmap:
    body = _SVG[name]
    fill = "currentColor" if name == "more" else "none"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}" '
           f'fill="{fill}" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
           f'color="{color}">{body}</svg>')
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(p)
    p.end()
    return QPixmap.fromImage(img)


@lru_cache(maxsize=None)
def ui_icon(name: str, color: str = _NORMAL, active: str = _ACTIVE, disabled: str = _DISABLED) -> QIcon:
    """סמל ממשק בכמה גדלים ובשלושה מצבים (רגיל / מעבר עכבר / מושבת)."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 48):
        icon.addPixmap(_svg_pixmap(name, color, size), QIcon.Normal)
        icon.addPixmap(_svg_pixmap(name, active, size), QIcon.Active)
        icon.addPixmap(_svg_pixmap(name, disabled, size), QIcon.Disabled)
    return icon


def ui_pixmap(name: str, color: str = _NORMAL, size: int = 16) -> QPixmap:
    return _svg_pixmap(name, color, size * 2)


# ---------------------------------------------------------------- סמלי קבצים
_KINDS = {"word": ("#2b579a", "W"), "pdf": ("#d93025", "PDF"), "doc": ("#5f6b7a", "DOC")}


def doc_kind(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXTS:
        return "pdf"
    if ext in DOC_EXTS:
        return "doc"
    return "word"


@lru_cache(maxsize=None)
def drawn_kind_icon(kind: str) -> QIcon:
    """הסמל המצויר (גיבוי): ריבוע צבעוני עם W / PDF."""
    color, label = _KINDS[kind]
    icon = QIcon()
    for size in (16, 20, 24, 32, 48):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(Qt.NoPen)
        r = QRectF(size * 0.1, size * 0.04, size * 0.8, size * 0.92)
        p.drawRoundedRect(r, size * 0.14, size * 0.14)
        f = QFont("Arial")
        f.setBold(True)
        f.setPixelSize(int(size * (0.5 if len(label) == 1 else 0.3)))
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(r, Qt.AlignCenter, label)
        p.end()
        icon.addPixmap(pm)
    return icon


_provider = None
_by_ext: dict = {}
_folder_icon = None
_generic = None


def _prov() -> QFileIconProvider:
    global _provider
    if _provider is None:
        _provider = QFileIconProvider()
    return _provider


def _image(icon: QIcon, size: int = 32) -> QImage:
    return icon.pixmap(QSize(size, size)).toImage()


def _generic_image() -> QImage:
    global _generic
    if _generic is None:
        _generic = _image(_prov().icon(QFileIconProvider.File))
    return _generic


_probe_dir = None


def _probe_path(ext: str) -> str:
    """קובץ ריק זמני עם הסיומת – כך מערכת ההפעלה מחזירה את הסמל האמיתי של הסוג (גם בחלונות)."""
    global _probe_dir
    import atexit
    import shutil
    import tempfile
    if _probe_dir is None:
        _probe_dir = tempfile.mkdtemp(prefix="hebdoc-icons-")
        atexit.register(shutil.rmtree, _probe_dir, True)
    path = os.path.join(_probe_dir, "document" + ext)
    if not os.path.exists(path):
        open(path, "wb").close()
    return path


def system_file_icon(ext: str) -> QIcon | None:
    """הסמל של מערכת ההפעלה לסוג קובץ (לפי סיומת, למשל '.docx'), או None אם אין סמל ייחודי."""
    ext = ext.lower()
    if ext in _by_ext:
        return _by_ext[ext]
    result = None
    try:
        icon = _prov().icon(QFileInfo(_probe_path(ext)))
        if not icon.isNull():
            img = _image(icon)
            generic = _generic_image()
            # סמל זהה לסמל ה"קובץ" הכללי = למערכת אין סמל ייחודי לסוג הזה
            if not img.isNull() and (generic.isNull() or img != generic):
                result = icon
    except Exception:
        result = None
    _by_ext[ext] = result
    return result


def file_icon(path: str) -> QIcon:
    """סמל של מסמך: הסמל של מערכת ההפעלה (וורד / PDF…), ואם אין – הסמל המצויר."""
    ext = os.path.splitext(path)[1]
    native = system_file_icon(ext) if ext else None
    return native if native is not None else drawn_kind_icon(doc_kind(path))


def kind_icon(kind: str) -> QIcon:
    return {"word": file_icon("x.docx"), "pdf": file_icon("x.pdf"), "doc": file_icon("x.doc")}[kind]


def folder_icon() -> QIcon:
    """סמל התיקייה של מערכת ההפעלה."""
    global _folder_icon
    if _folder_icon is None:
        icon = _prov().icon(QFileIconProvider.Folder)
        _folder_icon = icon if not icon.isNull() else ui_icon("folder", "#e0a82e", "#e0a82e")
    return _folder_icon


def describe_system_icons() -> dict:
    """לדוח הבדיקה העצמית: האם המערכת סיפקה סמלים ייחודיים לוורד / PDF / תיקיות."""
    return {
        "docx": system_file_icon(".docx") is not None,
        "pdf": system_file_icon(".pdf") is not None,
        "doc": system_file_icon(".doc") is not None,
        "folder": not _prov().icon(QFileIconProvider.Folder).isNull(),
    }
