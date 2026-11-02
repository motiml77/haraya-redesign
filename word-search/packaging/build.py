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


VSWHERE = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"


def visual_studio():
    """MSBuild של Visual Studio ותיקיית כלי Office (VSTO) – תוסף VSTO לא נבנה ב-dotnet build."""
    def ask(*args):
        out = subprocess.run([VSWHERE, "-latest", "-products", "*", *args], capture_output=True, text=True).stdout
        return [x.strip() for x in out.splitlines() if x.strip()]
    if not os.path.exists(VSWHERE):
        sys.exit("לבניית התוסף ל-Word נדרש Visual Studio עם רכיב פיתוח ל-Office (Office/SharePoint development)")
    msbuild = ask("-requires", "Microsoft.Component.MSBuild", "-find", r"MSBuild\**\Bin\MSBuild.exe")
    install = ask("-property", "installationPath")
    targets = glob.glob(os.path.join(install[0], "MSBuild", "Microsoft", "VisualStudio", "v*", "OfficeTools",
                                     "Microsoft.VisualStudio.Tools.Office.targets")) if install else []
    if not msbuild or not targets:
        sys.exit("לא נמצאו MSBuild או כלי VSTO של Visual Studio (רכיב Office/SharePoint development)")
    return msbuild[0], os.path.dirname(os.path.dirname(targets[0]))


def signing_certificate():
    """תעודה לחתימת המניפסטים של התוסף (VSTO דורש מניפסטים חתומים). נוצרת בבנייה; המפתח הציבורי
    נכנס לאשף ההתקנה, שרושם אותו ברשימת הפתרונות המהימנים של המשתמש (VSTO Inclusion List)."""
    # קודם מפתח של ספק ההצפנה הקלאסי (הכי נתמך בחתימת מניפסטים), ואם לא – ספק ברירת המחדל
    script = r"""
$ErrorActionPreference = 'Stop'
$common = @{ Type = 'CodeSigningCert'; Subject = 'CN=HebDocSearch Word Addin'; CertStoreLocation = 'Cert:\CurrentUser\My';
             KeyExportPolicy = 'Exportable'; KeyAlgorithm = 'RSA'; KeyLength = 2048; NotAfter = (Get-Date).AddYears(30) }
try {
    $c = New-SelfSignedCertificate @common -KeySpec Signature -Provider 'Microsoft Enhanced RSA and AES Cryptographic Provider'
} catch {
    [Console]::Error.WriteLine('legacy provider failed: ' + $_)
    $c = New-SelfSignedCertificate @common
}
$rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPublicKey($c)
$p = $rsa.ExportParameters($false)
$k = '<RSAKeyValue><Modulus>' + [Convert]::ToBase64String($p.Modulus) + '</Modulus><Exponent>' + [Convert]::ToBase64String($p.Exponent) + '</Exponent></RSAKeyValue>'
Write-Output ('THUMB=' + $c.Thumbprint)
Write-Output ('KEY=' + $k)
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True)
    out = proc.stdout
    if proc.stderr.strip():
        print("  powershell:", proc.stderr.strip()[-3000:], flush=True)
    values = dict(line.strip().split("=", 1) for line in out.splitlines() if "=" in line)
    if proc.returncode != 0 or not values.get("THUMB") or not values.get("KEY", "").startswith("<RSAKeyValue>"):
        sys.exit("יצירת תעודת החתימה לתוסף ל-Word נכשלה: " + out[-2000:] + proc.stderr[-2000:])
    return values["THUMB"], values["KEY"]


VSTO_KEY_FILE = os.path.join(BUILD, "vsto_key.iss")


def word_addin():
    """התוסף ל-Word (חלונות בלבד, VSTO): בונה לתוך <תיקיית התוכנה>\\word, ובודק את רכיב העזר
    (HebDocSearchHelper.exe) – חיפוש אמיתי דרך הצינור, כמו שהתוסף עושה בתוך Word."""
    msbuild, vstools = visual_studio()
    thumb, key = signing_certificate()
    project = os.path.join(ROOT, "word_addin")
    shutil.rmtree(os.path.join(project, "bin"), ignore_errors=True)
    shutil.rmtree(os.path.join(project, "obj"), ignore_errors=True)
    sh(msbuild, os.path.join(project, "HebDocSearch.WordAddin.csproj"), "/t:Rebuild", "/p:Configuration=Release",
       f"/p:VSToolsPath={vstools}", f"/p:ManifestCertificateThumbprint={thumb}", "/p:SignManifests=true",
       "/nologo", "/v:minimal")
    built = os.path.join(project, "bin", "Release")
    out = os.path.join(DIST, APP_ID, "word")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    for name in os.listdir(built):
        if not name.endswith(".pdb"):
            shutil.copy2(os.path.join(built, name), out)
    print("  קבצי התוסף:", sorted(os.listdir(out)))
    for need in ("HebDocSearch.WordAddin.dll", "HebDocSearch.WordAddin.vsto", "HebDocSearch.WordAddin.dll.manifest"):
        if not os.path.exists(os.path.join(out, need)):
            sys.exit(f"בניית התוסף ל-Word נכשלה: חסר {need}")
    os.makedirs(BUILD, exist_ok=True)
    with open(VSTO_KEY_FILE, "w", encoding="utf-8-sig") as f:
        f.write(f'#define VstoPublicKey "{key}"\n')

    helper = os.path.join(DIST, APP_ID, "HebDocSearchHelper.exe")
    req = json.dumps({"cmd": "search", "doc": "selftest", "query": "הלך", "headings_only": False,
                      "options": {"forms": "all"},
                      "paras": [{"t": "הלכות שבת", "h": 1}, {"t": "ההולך בשבת ברשות הרבים", "h": 0}]},
                     ensure_ascii=False)
    proc = subprocess.run([helper], input=json.dumps({"cmd": "ping"}) + "\n" + req + "\n", capture_output=True,
                          text=True, encoding="utf-8", timeout=120)
    lines = [json.loads(x) for x in proc.stdout.splitlines() if x.strip()]
    print("  רכיב העזר:", lines)
    if len(lines) != 2 or not lines[0].get("ok") or lines[1].get("total") != 2:
        sys.exit("רכיב העזר של התוסף ל-Word לא עבד: " + proc.stderr[-2000:])
    print("התוסף ל-Word נבנה ורכיב העזר עובד", flush=True)


def find_iscc():
    for c in (shutil.which("iscc"), r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
              r"C:\Program Files\Inno Setup 6\ISCC.exe"):
        if c and os.path.exists(c):
            return c
    sys.exit("לא נמצא Inno Setup 6 (ISCC.exe). התקינו מ-https://jrsoftware.org/isdl.php")


def package_windows():
    extra = [f"/DVstoKeyFile={VSTO_KEY_FILE}"] if os.path.exists(VSTO_KEY_FILE) else []
    sh(find_iscc(), f"/DAppVersion={__version__}", f"/DSourceDir={os.path.join(DIST, APP_ID)}",
       f"/DOutputDir={DIST}", *extra, os.path.join(ROOT, "packaging", "windows", "installer.iss"))
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
        word_addin()
        outputs = package_windows()
    elif sys.platform == "darwin":
        outputs = package_macos()
    else:
        outputs = package_linux()
    for o in outputs:
        print(f"נוצר: {o}  ({os.path.getsize(o) / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
