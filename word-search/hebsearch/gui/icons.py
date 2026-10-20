"""אייקונים קטנים לסוגי מסמכים, מצוירים בקוד (בלי קבצי תמונה)."""

import os
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from ..extract import DOC_EXTS, PDF_EXTS

_KINDS = {
    "word": ("#2b579a", "W"),
    "pdf": ("#d93025", "PDF"),
    "doc": ("#5f6b7a", "DOC"),
}


def doc_kind(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXTS:
        return "pdf"
    if ext in DOC_EXTS:
        return "doc"
    return "word"


@lru_cache(maxsize=None)
def kind_icon(kind: str) -> QIcon:
    color, label = _KINDS[kind]
    icon = QIcon()
    for size in (16, 20, 24, 32):
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


def file_icon(path: str) -> QIcon:
    return kind_icon(doc_kind(path))
