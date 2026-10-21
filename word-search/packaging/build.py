"""בניית התקנה מלאה למערכת הנוכחית.

    python packaging/build.py

  חלונות – dist/HebDocSearch-Setup-<גרסה>.exe  (אשף התקנה בעברית; נדרש Inno Setup 6)
  מק     – dist/HebDocSearch-<גרסה>-macOS-<arm64|x86_64>.dmg
  לינוקס – dist/HebDocSearch-<גרסה>-linux-x86_64.tar.gz  (עם install.sh)

לפני האריזה התוכנה הבנויה מריצה בדיקה עצמית (--selftest); אם היא נכשלת – הבנייה נכשלת.
"""

import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from hebsearch import APP_ID, __version__  # noqa: E402

DIST = os.path.join(ROOT, "dist")
for _stream in (sys.stdout, sys.stderr):   # עברית בחלון הפקודה של חלונות
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
BUILD = os.path.join(ROOT, "build")


def sh(*cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def pyinstaller():
    shutil.rmtree(os.path.join(DIST, APP_ID), ignore_errors=True)
    sh(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
       "--distpath", DIST, "--workpath", BUILD, os.path.join(ROOT, "packaging", "HebDocSearch.spec"))


def app_executable():
    if sys.platform == "darwin":
        return os.path.join(DIST, f"{APP_ID}.app", "Contents", "MacOS", APP_ID)
    return os.path.join(DIST, APP_ID, APP_ID + (".exe" if sys.platform == "win32" else ""))


def selftest():
    report = os.path.join(BUILD, "selftest.json")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run([app_executable(), "--selftest", report, "--gui"], env=env, timeout=600)
    data = json.load(open(report, encoding="utf-8"))
    for name, c in data["checks"].items():
        print(f"  {'✓' if c['ok'] else '✗'} {name}  {c.get('detail', '')}  {c.get('error', '')}")
    if proc.returncode != 0 or not data["ok"]:
        sys.exit("הבדיקה העצמית של התוכנה הארוזה נכשלה")
    print("הבדיקה העצמית עברה", flush=True)


def find_iscc():
    for c in (shutil.which("iscc"), r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
              r"C:\Program Files\Inno Setup 6\ISCC.exe"):
        if c and os.path.exists(c):
            return c
    sys.exit("לא נמצא Inno Setup 6 (ISCC.exe). התקינו מ-https://jrsoftware.org/isdl.php")


def package_windows():
    sh(find_iscc(), f"/DAppVersion={__version__}", f"/DSourceDir={os.path.join(DIST, APP_ID)}",
       f"/DOutputDir={DIST}", os.path.join(ROOT, "packaging", "windows", "installer.iss"))
    return glob.glob(os.path.join(DIST, f"{APP_ID}-Setup-*.exe"))


def package_macos():
    arch = platform.machine()
    out = os.path.join(DIST, f"{APP_ID}-{__version__}-macOS-{arch}.dmg")
    sh("bash", os.path.join(ROOT, "packaging", "macos", "build_dmg.sh"),
       os.path.join(DIST, f"{APP_ID}.app"), out)
    return [out]


def package_linux():
    stage = os.path.join(BUILD, "linux-package", f"{APP_ID}-{__version__}")
    shutil.rmtree(os.path.dirname(stage), ignore_errors=True)
    shutil.copytree(os.path.join(DIST, APP_ID), os.path.join(stage, APP_ID))
    for name in ("install.sh", "uninstall.sh", "hebdocsearch.desktop"):
        shutil.copy(os.path.join(ROOT, "packaging", "linux", name), stage)
    shutil.copy(os.path.join(ROOT, "hebsearch", "assets", "icon-512.png"), os.path.join(stage, "icon.png"))
    out = os.path.join(DIST, f"{APP_ID}-{__version__}-linux-{platform.machine()}.tar.gz")
    with tarfile.open(out, "w:gz") as tar:
        tar.add(stage, arcname=os.path.basename(stage))
    return [out]


def main():
    pyinstaller()
    selftest()
    if sys.platform == "win32":
        outputs = package_windows()
    elif sys.platform == "darwin":
        outputs = package_macos()
    else:
        outputs = package_linux()
    for o in outputs:
        print(f"נוצר: {o}  ({os.path.getsize(o) / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
