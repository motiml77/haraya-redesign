"""מייצר מקובץ ה-SVG של הלוגו את קבצי האייקון לכל מערכת:
icon.png (256), icon.ico (חלונות, כל הגדלים), icon.icns (מק).

שימוש:  python packaging/make_icons.py
"""

import os
import sys

from PIL import Image
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hebsearch", "assets")


def render(svg: bytes, size: int) -> Image.Image:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    QSvgRenderer(QByteArray(svg)).render(p)
    p.end()
    path = os.path.join(ASSETS, f".tmp_{size}.png")
    img.save(path)
    out = Image.open(path).convert("RGBA")
    out.load()
    os.remove(path)
    return out


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication(sys.argv)  # noqa: F841 – נדרש לציור
    svg = open(os.path.join(ASSETS, "icon.svg"), "rb").read()
    small = open(os.path.join(ASSETS, "icon-small.svg"), "rb").read()
    big = render(svg, 1024)
    big.resize((256, 256), Image.LANCZOS).save(os.path.join(ASSETS, "icon.png"))
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    # בגדלים קטנים – הגרסה הפשוטה, שנשארת ברורה
    frames = [render(small if s <= 32 else svg, s * 4).resize((s, s), Image.LANCZOS) for s in sizes]
    frames[-1].save(os.path.join(ASSETS, "icon.ico"), sizes=[(s, s) for s in sizes],
                    append_images=frames[:-1])
    big.save(os.path.join(ASSETS, "icon.icns"))
    for s, frame in zip(sizes, frames):
        if s in (16, 32):
            frame.save(os.path.join(ASSETS, f"icon-{s}.png"))
    big.resize((512, 512), Image.LANCZOS).save(os.path.join(ASSETS, "icon-512.png"))
    print("icons written to", ASSETS)


if __name__ == "__main__":
    main()
