import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hebsearch.index import IndexDB, resolve_basket  # noqa: E402
from hebsearch.search import SEG_MATCH, Searcher, SearchOptions, para_cache  # noqa: E402

from docx_builder import build_docx  # noqa: E402

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None

FONT = next((p for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                         "C:/Windows/Fonts/arial.ttf",
                         "/System/Library/Fonts/Supplemental/Arial.ttf",
                         "/Library/Fonts/Arial Unicode.ttf") if os.path.exists(p)), None)


def visual(s):
    """סדר חזותי, כמו שחלק ממחוללי ה-PDF שומרים עברית."""
    r = re.sub(r"[0-9A-Za-z]+", lambda m: m.group()[::-1], s[::-1])
    return r.translate(str.maketrans("()", ")("))


def build_pdf(path, pages):
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        y = 72
        for ln in lines:
            page.insert_text((40, y), visual(ln), fontfile=FONT, fontname="heb", fontsize=11)
            y += 16
    doc.save(path)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = cls.tmp.name
        cls.db = IndexDB(os.path.join(cls.dir, "i.sqlite3"))

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        para_cache.invalidate()
        cls.tmp.cleanup()

    def index(self, items):
        files = resolve_basket(items)[1]
        self.db.update(self.db.stale_files(files))
        return self.db.file_ids(files)

    def search(self, ids, q, **kw):
        s = Searcher(self.db)
        r = s.search(q, ids, SearchOptions(**kw))
        for h in r.hits:
            s.materialize(h, r.highlight)
        return r


class RankingTest(Base):
    def test_exact_form_first(self):
        build_docx(os.path.join(self.dir, "r.docx"), [
            "פסקה ראשונה: ההליכה הארוכה",
            "פסקה שנייה: והלכו כולם",
            "פסקה שלישית: הלך לביתו",
        ])
        ids = self.index([(os.path.join(self.dir, "r.docx"), "file")])
        r = self.search(ids, "הלך", inflections=True)
        self.assertEqual([h.words[0] for h in r.hits], ["הלכ", "והלכו", "ההליכה"])
        self.assertTrue(r.hits[0].exact)
        doc_order = self.search(ids, "הלך", inflections=True, sort="document")
        self.assertEqual([h.para_idx for h in doc_order.hits], [0, 1, 2])

    def test_phrase_proximity_first(self):
        build_docx(os.path.join(self.dir, "p.docx"), [
            "משה רבנו עלה אל ההר",
            "עלה משה אל ההר",
            "משה עלה",
        ])
        ids = self.index([(os.path.join(self.dir, "p.docx"), "file")])
        r = self.search(ids, "משה עלה", whole_paragraph=True)
        # צמוד בסדר הפוך (עלה משה) לפני מרוחק בסדר הנכון (משה רבנו עלה)
        self.assertEqual([h.para_idx for h in r.hits], [2, 1, 0])
        self.assertTrue(r.hits[0].exact)
        self.assertFalse(r.hits[1].exact)

    def test_highlight_all_search_words(self):
        build_docx(os.path.join(self.dir, "h.docx"), ["שבת שלום ושבת קודש"])
        ids = self.index([(os.path.join(self.dir, "h.docx"), "file")])
        r = self.search(ids, "שבת")
        marked = [t for t, k in r.hits[0].snippet if k == SEG_MATCH]
        self.assertEqual(marked, ["שבת", "ושבת"])


class BasketTest(Base):
    def test_exclude(self):
        d = os.path.join(self.dir, "folder")
        os.makedirs(d)
        for n in ("a", "b"):
            build_docx(os.path.join(d, n + ".docx"), ["טקסט"])
        b = os.path.join(d, "b.docx")
        entries, files = resolve_basket([(d, "folder"), (b, "exclude")])
        self.assertEqual(len(entries[0][2]), 2)
        self.assertEqual([os.path.basename(f) for f in files], ["a.docx"])
        bid = self.db.create_basket("בדיקה")
        self.db.add_basket_items(bid, [(d, "folder")])
        self.db.set_excluded(bid, b, True)
        self.assertIn((os.path.abspath(b), "exclude"), self.db.basket_items(bid))
        self.db.set_excluded(bid, b, False)
        self.assertEqual(self.db.basket_items(bid), [(os.path.abspath(d), "folder")])


@unittest.skipUnless(pymupdf and FONT, "pymupdf / Hebrew font not available")
class PdfTest(Base):
    def test_visual_order_pdf(self):
        path = os.path.join(self.dir, "v.pdf")
        build_pdf(path, [["שורה ראשונה בעמוד", "בשנת 1948 נוסדה המדינה (בעזרת ה')"],
                         ["עמוד שני", "שורה שנייה", "והלך משה אל ההר"]])
        ids = self.index([(path, "file")])
        r = self.search(ids, "נוסדה המדינה")
        self.assertEqual(r.total, 1)
        h = r.hits[0]
        self.assertEqual((h.page, h.line), (1, 2))
        self.assertEqual(h.location, "עמוד 1 · שורה 2")
        text = "".join(t for t, _ in h.snippet)
        self.assertIn("בשנת 1948 נוסדה המדינה (בעזרת ה')", text)
        h = self.search(ids, "הלך", inflections=True).hits[0]
        self.assertEqual((h.page, h.line), (2, 3))

    def test_scanned_pdf_reported(self):
        path = os.path.join(self.dir, "empty.pdf")
        doc = pymupdf.open()
        doc.new_page()
        doc.save(path)
        self.index([(path, "file")])
        row = self.db.file_rows([path])[path]
        self.assertEqual(row[3], "error")
        self.assertIn("סרוק", row[4])


if __name__ == "__main__":
    unittest.main()


class BasketEditorTest(Base):
    def test_browse_and_toggle(self):
        from hebsearch.basket import CHECKED, PARTIAL, UNCHECKED, BasketEditor
        root = os.path.join(self.dir, "lib")
        sub = os.path.join(root, "sub")
        deep = os.path.join(sub, "deep")
        os.makedirs(deep)
        a, b, c = (os.path.join(d, n) for d, n in ((root, "a.docx"), (sub, "b.docx"), (deep, "c.docx")))
        for f in (a, b, c):
            build_docx(f, ["טקסט"])
        bid = self.db.create_basket("עיון")
        ed = BasketEditor(self.db, bid)
        names = lambda: sorted(os.path.basename(f) for f in resolve_basket(self.db.basket_items(bid))[1])

        ed.set_checked(b, False, True)                     # מסמך בודד בתוך תת-תיקייה
        self.assertEqual(names(), ["b.docx"])
        self.assertEqual(ed.state(root, True), PARTIAL)
        ed.set_checked(root, True, True)                   # כל התיקייה – כולל תתי-תיקיות
        self.assertEqual(names(), ["a.docx", "b.docx", "c.docx"])
        self.assertEqual(self.db.basket_items(bid), [(os.path.abspath(root), "folder")])
        ed.set_checked(sub, True, False)                   # החרגת תת-תיקייה שלמה
        self.assertEqual(names(), ["a.docx"])
        self.assertEqual((ed.state(root, True), ed.state(c, False)), (PARTIAL, UNCHECKED))
        ed.set_checked(c, False, True)                     # מסמך בתוך תת-תיקייה מוחרגת
        self.assertEqual(names(), ["a.docx", "c.docx"])
        ed.set_checked(sub, True, True)                    # החזרת התת-תיקייה
        self.assertEqual(names(), ["a.docx", "b.docx", "c.docx"])
        self.assertEqual(ed.state(root, True), CHECKED)
        # ✓ מחדש על תיקייה "חלקית" לא מוסיפה אותה פעם נוספת כפריט נפרד, אלא מנקה את ההחרגות שבתוכה
        ed.set_checked(b, False, False)
        self.assertEqual(ed.state(sub, True), PARTIAL)
        ed.set_checked(sub, True, True)
        self.assertEqual(names(), ["a.docx", "b.docx", "c.docx"])
        self.assertEqual(self.db.basket_items(bid), [(os.path.abspath(root), "folder")])
        ed.set_checked(root, True, False)                  # ביטול הכל
        self.assertEqual(self.db.basket_items(bid), [])
