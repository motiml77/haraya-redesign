# -*- mode: python ; coding: utf-8 -*-
# הגדרות PyInstaller לבניית התוכנה הארוזה (תיקייה עם קובץ הפעלה, ובמק – ‎.app).
# הרצה:  python packaging/build.py   (או: pyinstaller packaging/HebDocSearch.spec)

import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)
from hebsearch import APP_ID, APP_NAME, __version__  # noqa: E402

ASSETS = os.path.join(ROOT, "hebsearch", "assets")
icon = os.path.join(ASSETS, "icon.icns" if sys.platform == "darwin" else "icon.ico")

hidden = ["hebsearch.gui.main_window", "hebsearch.selftest", "pymupdf", "PySide6.QtSvg", "PySide6.QtPdf",
          "PySide6.QtPdfWidgets"]
if sys.platform == "win32":
    hidden += ["win32com", "win32com.client", "pythoncom", "pywintypes", "win32gui"]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(ASSETS, "hebsearch/assets")],
    hiddenimports=hidden,
    # חבילות שלא בשימוש (חלקן תוספות אופציונליות של PyMuPDF) – מקטינות מאוד את ההתקנה
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQuick",
              "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "matplotlib", "numpy", "pandas",
              "onnxruntime", "PIL", "yaml", "lxml", "docx", "IPython", "pytest", "setuptools",
              "pymupdf4llm", "pymupdf_layout", "pymupdf.layout", "networkx", "psutil", "google.protobuf",
              "flatbuffers", "tabulate"],
    noarchive=False,
)

# ספריות Qt שנגררות דרך תוספים ואינן נחוצות (QML/Quick, מקלדת וירטואלית, תצוגות משובצות)
# (QtNetwork נשאר – QtPdf תלוי בו)
_DROP = ("Qt6Qml", "Qt6Quick", "VirtualKeyboard", "Qt6EglFS", "Qt6EglFs", "qtvirtualkeyboard",
         "platforminputcontexts", "/qml/", "QtQuick", "networkinformation", "/tls/")


def _keep(entry):
    name = entry[0].replace("\\", "/")
    return not any(d in name for d in _DROP)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d) and "/translations/" not in d[0].replace("\\", "/")
           or d[0].replace("\\", "/").endswith(("_he.qm", "_en.qm"))]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_ID,
    console=False,
    icon=icon,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_ID, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_ID}.app",
        icon=icon,
        bundle_identifier="org.hebdocsearch.app",
        version=__version__,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleName": APP_NAME,
            "CFBundleShortVersionString": __version__,
            "CFBundleDevelopmentRegion": "he",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSAppleEventsUsageDescription": "פתיחת מסמכים בתוכנות אחרות במקום שנמצא",
        },
    )
