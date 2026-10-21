"""בדיקות הממשק: מידות סבירות, התאמה למסך, ערכת נושא בהירה, חיפוש ברקע שלא תוקע את החלון.

רצות בלי תצוגה (QT_QPA_PLATFORM=offscreen), ולכן אינן תלויות במסך של המחשב שמריץ אותן.
"""

import os
import random
import sys
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRect, QSettings, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hebsearch.gui import icons, main_window as mw, theme  # noqa: E402
from hebsearch.gui.options import OptionsPopup  # noqa: E402
from hebsearch.index import IndexDB  # noqa: E402
from hebsearch.search import Searcher, SearchOptions  # noqa: E402

from docx_builder import build_docx  # noqa: E402

APP = QApplication.instance() or QApplication([])
SCREEN = QRect(0, 0, 1366, 728)          # מסך נפוץ של מחשב נייד (בלי שורת המשימות)


def settle(win, limit=60.0):
    """מחכה שכל עבודות הרקע של החלון יסתיימו (בלי לחסום את לולאת האירועים)."""
    t0 = time.time()
    while time.time() - t0 < limit:
        APP.processEvents()
        if not (win._scan_job or win._search_job or win._search_waiting_scan or win.results.overlay.is_active()):
            break
        time.sleep(0.005)
    for _ in range(10):
        APP.processEvents()
        time.sleep(0.005)


class GuiBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = cls.tmp.name
        cls._old_data = os.environ.get("HEBSEARCH_DATA")
        os.environ["HEBSEARCH_DATA"] = os.path.join(cls.dir, "data")
        cls.docs = os.path.join(cls.dir, "מסמכים")
        os.makedirs(os.path.join(cls.docs, "הלכה"))
        os.makedirs(os.path.join(cls.docs, "תורה"))
        build_docx(os.path.join(cls.docs, "הלכה", "שבת.docx"), [
            "ההולך בשבת ברשות הרבים צריך לשמור שלא יוציא דבר מרשות לרשות.",
            "כתב הרמב\"ם שההליכה בשבת צריכה להיות שונה מהליכת החול.",
            "והלכה כרבי יהודה שאסור להלך יותר מאלפיים אמה חוץ לתחום.",
        ])
        build_docx(os.path.join(cls.docs, "תורה", "בראשית.docx"), [
            "וַיֹּאמֶר יְהוָה אֶל-אַבְרָם, לֶךְ-לְךָ מֵאַרְצְךָ וּמִמּוֹלַדְתְּךָ.",
            "וַיֵּלֶךְ אַבְרָם, כַּאֲשֶׁר דִּבֶּר אֵלָיו יְהוָה.",
        ])
        build_docx(os.path.join(cls.docs, "מכתב.docx"), ["שלום וברכה, הלכנו כל המשפחה לטיול בהרי ירושלים."])
        cls.settings = QSettings(os.path.join(cls.dir, "settings.ini"), QSettings.IniFormat)
        cls._old_rect = mw.MainWindow._screen_rect
        mw.MainWindow._screen_rect = lambda self: SCREEN
        mw.prepare_app(APP, cls.settings)

    @classmethod
    def tearDownClass(cls):
        mw.MainWindow._screen_rect = cls._old_rect
        theme.apply(APP, 1.0)
        if cls._old_data is None:
            os.environ.pop("HEBSEARCH_DATA", None)
        else:
            os.environ["HEBSEARCH_DATA"] = cls._old_data
        cls.tmp.cleanup()

    def new_window(self, name="index.sqlite3"):
        self.settings.clear()
        win = mw.MainWindow(os.path.join(self.dir, name), self.settings)
        win.show()
        self.addCleanup(self.close_window, win)
        settle(win)
        return win

    @staticmethod
    def close_window(win):
        win.close()
        win.deleteLater()


class LayoutTest(GuiBase):
    """הפרופורציות: חלון שנכנס במסך, שדה חיפוש קומפקטי, סרגל סלים גבוה."""

    def test_window_fits_every_common_screen(self):
        for w, h in ((1366, 728), (1280, 680), (1024, 560), (800, 560), (1920, 1040), (2560, 1400)):
            geo = theme.fit_geometry(QRect(0, 0, w, h))
            self.assertLessEqual(geo.width(), w, (w, h))
            self.assertLessEqual(geo.height(), h, (w, h))
            self.assertGreaterEqual(geo.left(), 0)
            self.assertGreaterEqual(geo.top(), 0)
            self.assertLessEqual(geo.right(), w)
            self.assertLessEqual(geo.bottom(), h)
            self.assertLessEqual(geo.width(), 1180)       # גם במסך ענק לא נפתח "ענק"

    def test_main_window_opens_inside_the_screen(self):
        win = self.new_window()
        self.assertLessEqual(win.width(), SCREEN.width())
        self.assertLessEqual(win.height(), SCREEN.height())
        self.assertGreaterEqual(win.width(), 800)

    def test_search_row_is_compact(self):
        win = self.new_window()
        for name in ("search_edit", "search_btn", "options_btn", "sidebar_btn"):
            h = getattr(win, name).height()
            self.assertLessEqual(h, 36, f"{name} גבוה מדי: {h}px")
            self.assertGreaterEqual(h, 24, f"{name} נמוך מדי: {h}px")
        # כל כרטיס החיפוש (שדה + שוליים) לא תופס יותר מ-10% מגובה החלון
        card = win.search_edit.parentWidget()
        self.assertLessEqual(card.height(), 0.10 * win.height() + 20)

    def test_fonts_are_professional_sized(self):
        win = self.new_window()
        self.assertLessEqual(APP.font().pixelSize(), 14)
        self.assertGreaterEqual(APP.font().pixelSize(), 12)             # המינימום המומלץ לטקסט
        self.assertLessEqual(win.search_edit.font().pixelSize(), 15)
        self.assertLessEqual(win.search_btn.font().pixelSize(), 14)

    def test_basket_tree_gets_most_of_the_sidebar_height(self):
        win = self.new_window()
        win.baskets.add_paths([self.docs])
        settle(win)
        win.baskets.tabs.setCurrentIndex(0)
        APP.processEvents()
        share = win.baskets.tree.height() / win.height()
        self.assertGreaterEqual(share, 0.45, f"עץ הסל נמוך מדי: {win.baskets.tree.height()} מתוך {win.height()}")
        browser = win.baskets.browser.view
        win.baskets.tabs.setCurrentIndex(1)
        APP.processEvents()
        self.assertGreaterEqual(browser.height() / win.height(), 0.45, "עץ הבחירה מהמחשב נמוך מדי")

    def test_zoom_scales_everything_together(self):
        win = self.new_window()
        base = win.search_edit.height()
        win.set_zoom(1.3)
        self.addCleanup(win.set_zoom, 1.0)
        APP.processEvents()
        self.assertGreater(win.search_edit.height(), base)
        self.assertLessEqual(win.search_edit.height(), round(base * 1.4))
        win.set_zoom(0.8)
        self.assertLess(win.search_edit.height(), base)


class ThemeTest(GuiBase):
    def test_light_theme_even_when_the_os_is_dark(self):
        """בחלונות במצב כהה Qt צובע אזורים בשחור אם לא מגדירים פלטה מפורשת."""
        from PySide6.QtGui import QColor
        hints = APP.styleHints()
        dark = QPalette()
        for role in (QPalette.Window, QPalette.Base, QPalette.Button):
            dark.setColor(role, QColor("#202020"))
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
            dark.setColor(role, QColor("#f0f0f0"))
        if hasattr(hints, "setColorScheme"):
            hints.setColorScheme(Qt.ColorScheme.Dark)
        APP.setPalette(dark)
        theme.apply(APP, 1.0)
        for role in (QPalette.Window, QPalette.Base, QPalette.Button):
            self.assertGreater(APP.palette().color(role).lightness(), 200, role)
        self.assertLess(APP.palette().color(QPalette.Text).lightness(), 80)

    def test_every_ui_icon_renders(self):
        for name in icons._SVG:
            pm = icons.ui_icon(name).pixmap(16, 16)
            self.assertFalse(pm.isNull(), name)
            img = pm.toImage()
            self.assertTrue(any(img.pixelColor(x, y).alpha() > 0 for x in range(img.width()) for y in range(img.height())),
                            f"הסמל {name} ריק")

    def test_document_icons_exist_with_fallback(self):
        for name in ("a.docx", "a.pdf", "a.doc"):
            self.assertFalse(icons.file_icon(name).isNull(), name)
            self.assertFalse(icons.file_icon(name).pixmap(16, 16).isNull(), name)
        self.assertFalse(icons.folder_icon().isNull())
        self.assertEqual(set(icons.describe_system_icons()), {"docx", "pdf", "doc", "folder"})


class OptionsTest(GuiBase):
    def test_options_roundtrip(self):
        pop = OptionsPopup()
        self.assertEqual(pop.non_default(), 0)
        self.assertEqual(pop.describe(), "")
        pop.cb_inflect.setChecked(True)
        pop.gap.setValue(3)
        pop.set_term_count(3)
        pop.required.setCurrentIndex(pop.required.findData(2))
        opts = pop.options()
        self.assertTrue(opts.inflections)
        self.assertEqual(opts.max_gap, 3)
        self.assertEqual(opts.min_terms, 2)
        self.assertEqual(pop.non_default(), 3)
        self.assertIn("הטיות", pop.describe())
        pop.save(self.settings)
        other = OptionsPopup()
        other.restore(self.settings)
        self.assertEqual(other.options().max_gap, 3)
        self.assertTrue(other.options().inflections)
        pop.reset()
        self.assertEqual(pop.non_default(), 0)

    def test_paragraph_mode_disables_gap(self):
        pop = OptionsPopup()
        pop.cb_paragraph.setChecked(True)
        self.assertFalse(pop.gap.isEnabled())
        self.assertTrue(pop.options().whole_paragraph)


class SearchFlowTest(GuiBase):
    def test_search_shows_results_without_blocking(self):
        win = self.new_window()
        win.baskets.add_paths([self.docs])
        settle(win)
        self.assertEqual(win.db.baskets()[0][2], 3)
        win.search_edit.setText("הלך")
        win.options.cb_inflect.setChecked(True)
        win.run_search()
        settle(win)
        self.assertIsNotNone(win.result)
        self.assertGreaterEqual(win.result.total, 4)
        self.assertEqual(win.results.list.model().rowCount(), min(win.result.total, 30))
        self.assertIn("תוצאות", win.summary.text())

    def test_empty_search_and_missing_basket_selection_are_friendly(self):
        win = self.new_window()
        win.baskets.add_paths([self.docs])
        settle(win)
        win.search_edit.setText("   ")
        win.run_search()                    # לא קורס ולא מחפש
        self.assertIsNone(win._search_job)
        win.search_ids = set()
        win.search_edit.setText("הלך")
        win.run_search()
        self.assertIsNone(win._search_job)

    def test_new_search_replaces_a_running_one(self):
        win = self.new_window()
        win.baskets.add_paths([self.docs])
        settle(win)
        win.search_edit.setText("הלך")
        win.run_search()
        win.search_edit.setText("שבת")
        win.run_search()                    # השנייה מבטלת את הראשונה
        settle(win)
        self.assertEqual(win.result.highlight and "שבת" in " ".join(win.result.highlight), True)

    def test_basket_tree_counts_follow_exclusions(self):
        win = self.new_window()
        win.baskets.add_paths([self.docs])
        settle(win)
        model = win.baskets.model
        top = model.index(0, 0)
        node = model.node_at(top)
        self.assertEqual(node.total, 3)
        self.assertEqual(model.included_count(node), 3)
        sub = next(k for k in node.kids if k.name == "תורה")
        win.baskets.editor.set_checked(sub.path, True, False)
        model.refresh()
        self.assertEqual(model.included_count(node), 2)
        self.assertEqual(model.included_count(sub), 0)
        win.baskets.editor.set_checked(sub.path, True, True)
        model.refresh()
        self.assertEqual(model.included_count(node), 3)


class ResponsivenessTest(GuiBase):
    """הגרסה הראשונה "קפאה" בזמן חיפוש: כל העבודה רצה על חוט הממשק. כאן מוודאים שהלולאה ממשיכה לפעום."""

    def test_event_loop_keeps_running_during_a_heavy_search(self):
        rng = random.Random(7)
        vocab = ["של", "את", "על", "אל", "הוא", "היא", "כי", "לא", "אשר", "ויאמר", "משה", "העם", "הלך", "בדרך"] + \
                [f"מילה{i}" for i in range(200)]
        big = os.path.join(self.dir, "גדולים")
        os.makedirs(big)
        for i in range(6):                                  # עד 8 קבצים: אינדוקס בתהליך אחד, בלי מאגר תהליכים
            words = [rng.choice(vocab) if rng.random() < 0.6 else rng.choice(vocab[:6]) for _ in range(40_000)]
            build_docx(os.path.join(big, f"ספר{i}.docx"), [" ".join(words[j:j + 200]) for j in range(0, len(words), 200)])
        win = self.new_window("big.sqlite3")
        win.baskets.add_paths([big])
        gaps, last = [], [time.perf_counter()]

        def tick():
            now = time.perf_counter()
            gaps.append(now - last[0])
            last[0] = now

        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(tick)
        timer.start()
        settle(win, 120)                                   # אינדוקס
        win.search_edit.setText("של את על")
        win.options.cb_paragraph.setChecked(True)
        gaps.clear()
        last[0] = time.perf_counter()
        t0 = time.perf_counter()
        win.run_search()
        settle(win, 120)
        total = time.perf_counter() - t0
        timer.stop()
        self.assertIsNotNone(win.result)
        self.assertGreater(win.result.total, 1000)
        worst = max(gaps)
        # ללא חוט רקע כל החיפוש היה חוסם את הלולאה לכל משך החיפוש; כאן הפער הגדול ביותר קטן בהרבה
        self.assertLess(worst, max(0.8, total * 0.5), f"הממשק נתקע {worst * 1000:.0f}ms בחיפוש של {total:.2f}s")


class EngineProgressTest(unittest.TestCase):
    def test_progress_is_monotonic_and_cancel_is_fast(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(5):
                build_docx(os.path.join(tmp, f"d{i}.docx"), [f"ויאמר משה אל העם הלך בדרך {i}"] * 40)
            db = IndexDB(os.path.join(tmp, "i.sqlite3"))
            files = [os.path.join(tmp, f"d{i}.docx") for i in range(5)]
            db.update(db.stale_files(files))
            ids = db.file_ids(files)
            seen = []
            res = Searcher(db).search("ויאמר משה", ids, SearchOptions(), progress=lambda f, t="": seen.append(f))
            self.assertEqual(res.total, 200)
            self.assertTrue(seen)
            self.assertTrue(all(0.0 <= f <= 1.0 for f in seen))
            self.assertEqual(seen, sorted(seen))
            t0 = time.perf_counter()
            res = Searcher(db).search("ויאמר משה", ids, SearchOptions(), cancelled=lambda: True)
            self.assertTrue(res.cancelled)
            self.assertLess(time.perf_counter() - t0, 1.0)
            db.close()


if __name__ == "__main__":
    unittest.main()
