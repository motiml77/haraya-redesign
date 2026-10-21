import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hebsearch.extract import KIND_FOOTNOTE, extract_docx  # noqa: E402
from hebsearch.index import IndexDB, resolve_items  # noqa: E402
from hebsearch.morphology import MatchOptions, term_regex  # noqa: E402
from hebsearch.normalize import normalize_word, tokenize  # noqa: E402
from hebsearch.search import SEG_MATCH, Searcher, SearchOptions, para_cache  # noqa: E402

from docx_builder import build_docx  # noqa: E402


def matches(query, words, **kw):
    rx = term_regex([normalize_word(query)], MatchOptions(**kw))
    joined = "\n".join(normalize_word(w) for w in words)
    found = {m.group() for m in rx.finditer(joined)}
    return {w for w in words if normalize_word(w) in found}


class NormalizeTest(unittest.TestCase):
    def test_niqqud_and_finals(self):
        self.assertEqual(normalize_word("בְּרֵאשִׁ֖ית"), "בראשית")
        self.assertEqual(normalize_word("הָלַךְ"), "הלכ")
        self.assertEqual(normalize_word('רש"י'), "רשי")
        self.assertEqual(normalize_word("רש״י"), "רשי")

    def test_tokenize_offsets(self):
        text = 'אָמַר רש"י: "שלום" עַל־הַדֶּרֶךְ.'
        toks = tokenize(text)
        self.assertEqual([t[2] for t in toks], ["אמר", "רשי", "שלומ", "על", "הדרכ"])
        s, e, _ = toks[1]
        self.assertEqual(text[s:e], 'רש"י')


class MorphologyTest(unittest.TestCase):
    WORDS = ["הלך", "הלכה", "הליכה", "הולך", "ההולכים", "וכשהלך", "מלך", "הלכות", "שמר",
             "וַיֵּלֶךְ", "ללכת", "תלכו", "מלכת", "מלכה"]

    def test_exact(self):
        self.assertEqual(matches("הלך", self.WORDS, prefixes=False), {"הלך"})

    def test_prefixes(self):
        self.assertEqual(matches("הלך", self.WORDS), {"הלך", "וכשהלך"})

    def test_inflections(self):
        found = matches("הלך", self.WORDS, inflections=True)
        self.assertTrue({"הלך", "הלכה", "הליכה", "הולך", "ההולכים", "וכשהלך", "הלכות"} <= found)
        self.assertTrue({"וַיֵּלֶךְ", "ללכת", "תלכו"} <= found)
        self.assertEqual(found & {"מלך", "מלכת", "מלכה", "שמר"}, set())

    def test_inflected_query(self):
        found = matches("הליכה", self.WORDS, inflections=True)
        self.assertIn("הלך", found)
        self.assertIn("הלכה", found)

    def test_ahevi(self):
        words = ["שמירה", "שמרה", "שומרה", "שמר"]
        self.assertEqual(matches("שמרה", words, prefixes=False), {"שמרה"})
        self.assertEqual(matches("שמרה", words, prefixes=False, ahevi="vy"), {"שמירה", "שמרה", "שומרה"})
        self.assertEqual(matches("שמרה", words, prefixes=False, ahevi="all"), set(words))


class SearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        filler = " ".join(f"מילה{i}" for i in range(30))
        build_docx(os.path.join(d, "a.docx"), [
            "בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ",
            filler + " וַיֵּלֶךְ משה והלך אל ההר הגבוה " + filler,
            "|בעמוד השני: ההליכה בדרך^1 היא ארוכה",
        ], footnotes={"1": "הערה על הדרך והליכתו"}, table=[["תא ראשון", "שמירת שבת"]])
        sub = os.path.join(d, "sub")
        os.makedirs(sub)
        build_docx(os.path.join(sub, "b.docx"), ["אמר רבי שמעון: הלכה כרבי יהודה", "שומר מצוה"])
        cls.db = IndexDB(os.path.join(d, "index.sqlite3"))
        cls.files = resolve_items([(d, "folder")])
        cls.db.update(cls.db.stale_files(cls.files))
        cls.ids = cls.db.file_ids(cls.files)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        para_cache.invalidate()
        cls.tmp.cleanup()

    def search(self, q, **kw):
        s = Searcher(self.db)
        r = s.search(q, self.ids, SearchOptions(**kw))
        for h in r.hits:
            s.materialize(h)
        return r

    def test_extract(self):
        paras = extract_docx(os.path.join(self.tmp.name, "a.docx"))
        texts = [p[0] for p in paras]
        self.assertIn("שמירת שבת", texts)
        self.assertEqual(paras[2][1], 2)  # עמוד 2
        note = [p for p in paras if p[2] == KIND_FOOTNOTE][0]
        self.assertEqual((note[1], note[3]), (2, 1))

    def test_incremental(self):
        self.assertEqual(self.db.stale_files(self.files), [])

    def test_niqqud_search(self):
        r = self.search("בראשית ברא")
        self.assertEqual(r.total, 1)
        self.assertEqual(r.hits[0].location, "עמוד 1 · פסקה 1")

    def test_snippet_window(self):
        r = self.search("משה")
        h = r.hits[0]
        i = [k for _, k in h.snippet].index(SEG_MATCH)
        before = "".join(t for t, _ in h.snippet[:i]).replace("…", "").split()
        after = "".join(t for t, _ in h.snippet[i + 1:]).replace("…", "").split()
        self.assertEqual((len(before), len(after)), (20, 20))
        self.assertEqual(before[0], "מילה11")
        self.assertEqual([t for t, k in h.snippet if k == SEG_MATCH], ["משה"])

    def test_gap(self):
        self.assertEqual(self.search("משה ההר").total, 0)
        self.assertEqual(self.search("משה ההר", max_gap=2).total, 1)
        self.assertEqual(self.search("ההר משה", max_gap=2).total, 0)
        self.assertEqual(self.search("ההר משה", max_gap=2, ordered=False).total, 1)
        self.assertEqual(self.search("בראשית הארץ", whole_paragraph=True).total, 1)

    def test_inflections_across_files(self):
        r = self.search("הלך", inflections=True)
        forms = set(r.forms)
        self.assertTrue({"והלך", "ההליכה", "הלכה", "והליכתו"} <= forms, forms)
        self.assertEqual(len(r.files), 2)

    def test_footnote_and_table(self):
        r = self.search("הליכתו", inflections=True)
        self.assertTrue(any(h.location == "עמוד 2 · הערת שוליים 1" for h in r.hits))
        self.assertEqual(self.search("שבת").total, 1)

    def test_or_and_not(self):
        self.assertEqual(self.search("שמעון|משה").total, 2)
        self.assertEqual(self.search("הלכה -שמעון").total, 0)

    def test_ahevi_search(self):
        self.assertEqual(self.search("שמר", prefixes=False).total, 0)
        self.assertEqual(self.search("שמר", prefixes=False, ahevi="vy").total, 1)

    def test_locate(self):
        r = self.search("דרך")
        h = [h for h in r.hits if h.kind == 0][0]
        cands, ratio = Searcher(self.db).locate(h)
        self.assertEqual(cands[0], ("בדרך", 0))
        self.assertTrue(0 < ratio < 1)
        h = [h for h in r.hits if h.kind == KIND_FOOTNOTE][0]
        self.assertEqual(Searcher(self.db).locate(h)[0][0], ("הדרך", 0))


if __name__ == "__main__":
    unittest.main()
