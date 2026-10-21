"""צילומי מסך של הממשק האמיתי – כדי לראות את המראה כפי שהוא בחלונות / מק / לינוקס בלי מחשב פיזי.

    python tools/screenshots.py OUT_DIR [--offscreen] [--screen 1366x768]

מכין מסמכי דוגמה (וורד ו-PDF), מפעיל את החלון הראשי ועובר בו על המצבים העיקריים
(חיפוש, אפשרויות, מציגי מסמכים, זום, חלון צר ועוד). לכל מצב נשמר PNG, וב-report.json
נשמרים המידות שנמדדו, הגופן, הסמלים שמערכת ההפעלה סיפקה ועוד.
"""

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
import time
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--offscreen", action="store_true", help="בלי חלון אמיתי (לינוקס / בדיקה מקומית)")
    ap.add_argument("--screen", default="", help="מדמה מסך בגודל WxH (שטח פנוי, בלי שורת משימות)")
    args = ap.parse_args()
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    out = os.path.abspath(args.out)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    tmp = tempfile.mkdtemp(prefix="hebshots-")
    os.environ["HEBSEARCH_DATA"] = os.path.join(tmp, "data")

    from PySide6.QtCore import QRect, QSettings, QSysInfo, QTimer, qVersion
    from PySide6.QtGui import QFont, QGuiApplication, QImage, QPageSize, QPdfWriter, QTextDocument
    from PySide6.QtWidgets import QApplication

    from docx_builder import build_docx
    from hebsearch import __version__
    from hebsearch.gui import icons, main_window as mw, theme
    from hebsearch.paths import default_db_path

    report = {"version": __version__, "python": sys.version.split()[0], "qt": qVersion(),
              "os": platform.platform(), "kernel": QSysInfo.prettyProductName(), "shots": {}, "errors": []}

    # ------------------------------------------------------------ מסמכי דוגמה
    docs = os.path.join(tmp, "מסמכים")
    for sub in ("תורה", "הלכה", "ספרים"):
        os.makedirs(os.path.join(docs, sub))
    build_docx(os.path.join(docs, "תורה", "בראשית פרק יב.docx"), [
        "וַיֹּאמֶר יְהוָה אֶל-אַבְרָם, לֶךְ-לְךָ מֵאַרְצְךָ וּמִמּוֹלַדְתְּךָ וּמִבֵּית אָבִיךָ, אֶל-הָאָרֶץ, אֲשֶׁר אַרְאֶךָּ.",
        "וְאֶעֶשְׂךָ, לְגוֹי גָּדוֹל, וַאֲבָרֶכְךָ, וַאֲגַדְּלָה שְׁמֶךָ; וֶהְיֵה, בְּרָכָה.",
        "וַיֵּלֶךְ אַבְרָם, כַּאֲשֶׁר דִּבֶּר אֵלָיו יְהוָה, וַיֵּלֶךְ אִתּוֹ, לוֹט; וְאַבְרָם, בֶּן-חָמֵשׁ שָׁנִים וְשִׁבְעִים שָׁנָה, בְּצֵאתוֹ, מֵחָרָן.",
        "|וַיַּעֲבֹר אַבְרָם, בָּאָרֶץ, עַד מְקוֹם שְׁכֶם, עַד אֵלוֹן מוֹרֶה; וְהַכְּנַעֲנִי, אָז בָּאָרֶץ.",
        "וַיִּסַּע אַבְרָם, הָלוֹךְ וְנָסוֹעַ הַנֶּגְבָּה.^1",
    ], footnotes={"1": "רש\"י: הלוך ונסוע – לסירוגין, יושב כאן חודש או יותר ונוסע משם ונוטה אהלו במקום אחר."})
    build_docx(os.path.join(docs, "הלכה", "הלכות שבת – סיכום.docx"), [
        "פרק א: מלאכות שבת",
        "ההולך בשבת ברשות הרבים צריך לשמור שלא יוציא דבר מרשות לרשות, ומי שהלך בדרך וחשכה לו נותן כיסו לנכרי.",
        "כתב הרמב\"ם שההליכה בשבת צריכה להיות שונה מהליכת החול, ולכן אין לפסוע פסיעה גסה.",
        "שמירת שבת שקולה כנגד כל המצוות, וכל השומר שבת כהלכתו מוחלין לו על כל עוונותיו.",
        "והלכה כרבי יהודה שאסור להלך יותר מאלפיים אמה חוץ לתחום, ומי שהלכו בהיתר מותר לחזור.",
    ], table=[["מלאכה", "הגדרה"], ["הוצאה", "המוציא מרשות היחיד לרשות הרבים"]])
    build_docx(os.path.join(docs, "מכתב לחבר.docx"), [
        "שלום וברכה לידידי היקר,",
        "רציתי לספר לך שבשבוע שעבר הלכנו כל המשפחה לטיול בהרי ירושלים, וההליכה בשבילים היתה מרוממת ומלאת שמחה.",
        "בברכת שבת שלום ומבורך.",
    ])

    app = QApplication(sys.argv[:1])

    def make_pdf(path, paras):
        doc = QTextDocument()
        doc.setDefaultFont(QFont(theme.system_family() if theme._SYSTEM_FAMILY else "Arial", 12))
        doc.setHtml('<div dir="rtl">' + "".join(f"<p>{p}</p>" for p in paras) + "</div>")
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.A5))
        doc.print_(writer)

    make_pdf(os.path.join(docs, "ספרים", "מסילת ישרים – פרק ב.pdf"), [
        "פרק ב: בביאור מידת הזהירות",
        "ענין הזהירות הוא שיהיה האדם נזהר במעשיו ובעניניו, כלומר מתבונן ומפקח על מעשיו ודרכיו הטובים הם אם לא.",
        "ומשל למה הדבר דומה, לעור שהולך על שפת הנהר, אשר הסכנה בו ודאית. כי ההולך בדרך בלא זהירות הוא כמי שהלך בעיניים עצומות.",
    ] + ["והנה התבונן וראה כי מלבד שהדבר הזה מחויב מצד השכל, הנה הוא מבואר בתורה ובדברי חכמים. " * 3] * 6)

    # ------------------------------------------------------------ אפליקציה
    settings = QSettings(os.path.join(tmp, "settings.ini"), QSettings.IniFormat)
    if args.screen:
        sw, sh = (int(x) for x in args.screen.lower().split("x"))
        mw.MainWindow._screen_rect = lambda self: QRect(0, 0, sw, sh)
    hints = app.styleHints()
    report["os_color_scheme"] = str(hints.colorScheme()) if hasattr(hints, "colorScheme") else "n/a"   # לפני שהתוכנה קובעת ערכה בהירה
    report["os_palette_window_lightness"] = app.palette().color(app.palette().ColorRole.Window).lightness()
    mw.prepare_app(app, settings)
    report["app_palette_window_lightness"] = app.palette().color(app.palette().ColorRole.Window).lightness()
    scr = QGuiApplication.primaryScreen()
    report["screen"] = {"geometry": list(scr.geometry().getRect()), "available": list(scr.availableGeometry().getRect()),
                        "dpr": scr.devicePixelRatio(), "logical_dpi": scr.logicalDotsPerInch(), "platform": app.platformName()}
    report["font"] = {"family": theme.system_family(), "app_font": app.font().family(), "px": app.font().pixelSize(),
                      "zoom": theme.T.zoom}
    report["system_icons"] = icons.describe_system_icons()
    report["style"] = app.style().objectName()

    win = mw.MainWindow(default_db_path(), settings)
    win.show()

    def idle(maxt=90):
        t0 = time.time()
        while time.time() - t0 < maxt:
            app.processEvents()
            if not (win._scan_job or win._search_job or win._search_waiting_scan or win.results.overlay.is_active()):
                break
            time.sleep(0.01)
        for _ in range(15):
            app.processEvents()
            time.sleep(0.01)

    def spin(sec):
        t0 = time.time()
        while time.time() - t0 < sec:
            app.processEvents()
            time.sleep(0.01)

    def darkness(img: QImage) -> float:
        dark = total = 0
        for y in range(0, img.height(), 3):
            for x in range(0, img.width(), 3):
                total += 1
                if img.pixelColor(x, y).lightness() < 70:
                    dark += 1
        return round(dark / max(1, total), 4)

    counter = [0]

    def shot(name, widget=None, note=""):
        counter[0] += 1
        widget = widget or win
        img = widget.grab().toImage()
        fname = f"{counter[0]:02d}_{name}.png"
        img.save(os.path.join(out, fname))
        report["shots"][fname] = {"size": [img.width(), img.height()], "dark_share": darkness(img), "note": note}
        print("  ", fname, img.width(), "x", img.height())

    def step(name, fn):
        try:
            fn()
        except Exception:
            report["errors"].append({"step": name, "error": traceback.format_exc()[-1500:]})
            print("!!", name, traceback.format_exc()[-500:])

    def geo(w):
        g = w.geometry()
        return [g.width(), g.height()]

    idle()
    step("welcome", lambda: shot("welcome"))

    def browser():
        win.baskets.tabs.setCurrentIndex(1)
        win.baskets.browser.reveal(docs)
        spin(2.0)
        shot("browse_tab", note="עץ בחירה מהמחשב (כוננים ותיקיות) עם סמלי המערכת")
        win.baskets.tabs.setCurrentIndex(0)
    step("browser", browser)

    def basket():
        win.baskets.add_paths([docs])
        idle()
        shot("basket")
    step("basket", basket)

    def results():
        win.search_edit.setText("הלך")
        win.options.cb_inflect.setChecked(True)
        t0 = time.perf_counter()
        win.run_search()
        idle()
        report["search_seconds"] = round(time.perf_counter() - t0, 3)
        shot("results")
    step("results", results)

    def options():
        win._show_options()
        spin(0.4)
        shot("options", win.options)
        win.options.close()
        spin(0.2)
    step("options", options)

    def by_document():
        win.sort_combo.setCurrentIndex(1)
        idle()
        shot("by_document")
        win.sort_combo.setCurrentIndex(0)
        idle()
    step("by_document", by_document)

    def busy():
        win.results.busy_begin("מחפש…")
        win.results.busy_progress(0.42, "שולף את המופעים של «הלך»\nמסמך 3 מתוך 7")
        spin(0.6)
        shot("busy_overlay", note="ספינר, אחוזים וכפתור ביטול")
        win.results.busy_end()
        spin(0.2)
    step("busy", busy)

    def viewers():
        hits = win.result.hits
        word_hit = next(h for h in hits if not h.path.lower().endswith(".pdf"))
        win.preview_hit(word_hit)
        idle()
        shot("viewer_word", win.viewers[-1])
        pdf_hit = next((h for h in hits if h.path.lower().endswith(".pdf")), None)
        if pdf_hit:
            win.preview_hit(pdf_hit)
            idle()
            spin(1.0)
            shot("viewer_pdf", win.viewers[-1])
        for v in list(win.viewers):
            v.close()
    step("viewers", viewers)

    def two_baskets():
        win.baskets.db.create_basket("שיעורים")
        win.baskets.reload_baskets()
        win._baskets_changed()
        idle()
        shot("two_baskets")
    step("two_baskets", two_baskets)

    def zooms():
        for z in (1.25, 0.85):
            win.set_zoom(z)
            idle()
            shot(f"zoom_{int(z * 100)}")
        win.set_zoom(1.0)
        idle()
    step("zooms", zooms)

    def narrow():
        win.resize(900, 560)
        idle()
        shot("narrow_900x560")
        win.sidebar_btn.setChecked(False)
        idle()
        shot("no_sidebar_narrow")
        win.sidebar_btn.setChecked(True)
        win.resize(1180, 700)
        idle()
    step("narrow", narrow)

    report["metrics"] = {
        "window": geo(win), "search_field": geo(win.search_edit), "search_button": geo(win.search_btn),
        "options_button": geo(win.options_btn), "basket_tree": geo(win.baskets.tree),
        "browser_tree": geo(win.baskets.browser.view), "results": geo(win.results),
    }
    win.close()
    report["ok"] = not report["errors"]
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: report[k] for k in ("screen", "font", "system_icons", "metrics", "errors")}, ensure_ascii=False, indent=1))
    QTimer.singleShot(0, app.quit)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
