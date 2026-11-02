"""חיפוש של כמה מילים (2–6) מקצה לקצה: אינדקס, שליפה, צירופים ודירוג."""

import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hebsearch.index import IndexDB, resolve_items  # noqa: E402
from hebsearch.normalize import normalize_text  # noqa: E402
from hebsearch.search import SEG_MATCH, Searcher, SearchOptions, para_cache  # noqa: E402

from docx_builder import build_docx  # noqa: E402
from test_matching import brute_intervals, max_disjoint  # noqa: E402


class Fixture(unittest.TestCase):
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

    def index(self, name, paragraphs):
        path = os.path.join(self.dir, name)
        build_docx(path, paragraphs)
        files = resolve_items([(path, "file")])
        self.db.update(self.db.stale_files(files))
        return self.db.file_ids(files)

    def search(self, ids, q, **kw):
        s = Searcher(self.db)
        r = s.search(q, ids, SearchOptions(**kw))
        for h in r.hits:
            s.materialize(h, r.highlight)
        return r


class MultiWordTest(Fixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ids = cls.index(cls, "m.docx", [
            "וַיֹּאמֶר מֹשֶׁה אֶל הָעָם זִכְרוּ אֶת הַיּוֹם הַזֶּה אֲשֶׁר יְצָאתֶם מִמִּצְרַיִם",   # 0
            "ומשה אמר לכל העם שיזכרו היטב את היום הגדול ההוא",                               # 1
            "היום הזה זכרו את משה ואת העם",                                                  # 2
            "משה ראה את העם והלך אל ההר; אחר כך זכר את היום",                                 # 3
            "שבת שלום ומבורך, שבת קודש לה'",                                                  # 4
            "אמר רבי עקיבא ואהבת לרעך כמוך זה כלל גדול בתורה",                                # 5
            "כלל גדול בתורה אמר רבי עקיבא: ואהבת לרעך כמוך",                                  # 6
        ])

    def test_four_word_phrase_with_niqqud(self):
        r = self.search(self.ids, "ויאמר משה אל העם")
        self.assertEqual([h.para_idx for h in r.hits], [0])
        self.assertTrue(r.hits[0].exact)
        self.assertEqual([t for t, k in r.hits[0].snippet if k == SEG_MATCH][:4],
                         ["וַיֹּאמֶר", "מֹשֶׁה", "אֶל", "הָעָם"])

    def test_six_word_phrase(self):
        # "עקיבא: ואהבת" – הנקודתיים אינם מילה, ולכן גם פסקה 6 היא צירוף צמוד
        r = self.search(self.ids, "אמר רבי עקיבא ואהבת לרעך כמוך")
        self.assertEqual(sorted(h.para_idx for h in r.hits), [5, 6])
        self.assertTrue(all(h.exact for h in r.hits))
        # הרווח הגדול ביותר בין מילים נבחרות סמוכות הוא 2 בשתי הפסקאות (עקיבא … כמוך)
        r = self.search(self.ids, "רבי עקיבא כלל גדול בתורה כמוך", max_gap=1, ordered=False)
        self.assertEqual(r.total, 0)
        r = self.search(self.ids, "רבי עקיבא כלל גדול בתורה כמוך", max_gap=2, ordered=False)
        self.assertEqual(sorted(h.para_idx for h in r.hits), [5, 6])

    def test_gap_and_order_with_four_words(self):
        q = "משה העם זכר היום"
        self.assertEqual(self.search(self.ids, q).total, 0)
        r = self.search(self.ids, q, max_gap=4, inflections=True)
        self.assertEqual(sorted(h.para_idx for h in r.hits), [0, 1])   # בפסקה 3 יש 5 מילים בין העם לזכר
        r = self.search(self.ids, q, max_gap=5, inflections=True)
        self.assertEqual(sorted(h.para_idx for h in r.hits), [0, 1, 3])
        r = self.search(self.ids, q, max_gap=5, inflections=True, ordered=False)
        self.assertEqual(sorted(h.para_idx for h in r.hits), [0, 1, 2, 3])

    def test_whole_paragraph_four_words(self):
        r = self.search(self.ids, "משה העם היום זכרו", whole_paragraph=True, inflections=True)
        self.assertEqual(sorted(h.para_idx for h in r.hits), [0, 1, 2, 3])
        self.assertEqual({h.covered for h in r.hits}, {4})

    def test_repeated_word(self):
        self.assertEqual(self.search(self.ids, "שבת שבת", max_gap=3).total, 1)
        self.assertEqual(self.search(self.ids, "שבת שבת שבת", max_gap=3).total, 0)

    def test_partial_and_near_miss(self):
        q = "משה העם היום ירושלים"                         # ירושלים לא מופיעה בכלל
        r = self.search(self.ids, q, whole_paragraph=True)
        self.assertEqual(r.total, 0)
        self.assertIn("ירושלים", r.message)
        self.assertEqual(r.near_miss[0], 3)                 # הצעה: 3 מתוך 4
        r = self.search(self.ids, q, whole_paragraph=True, min_terms=3)
        self.assertTrue(r.total > 0)
        self.assertTrue(all(h.covered == 3 for h in r.hits))

    def test_partial_ranks_full_first(self):
        r = self.search(self.ids, "אמר רבי עקיבא כלל", max_gap=8, ordered=False, min_terms=3)
        self.assertEqual(r.hits[0].covered, 4)
        self.assertTrue(r.hits[0].score >= max(h.score for h in r.hits))

    def test_negation_with_many_words(self):
        r = self.search(self.ids, "משה העם היום -זכרו -זכר", whole_paragraph=True, inflections=False)
        self.assertEqual(sorted(h.para_idx for h in r.hits), [1])


class RandomPipelineTest(Fixture):
    """מסמכים אקראיים ושאילתות אקראיות – השוואה לסריקה ישירה של הטקסט."""

    def test_against_direct_scan(self):
        rnd = random.Random(99)
        common = ["אבן", "בית", "גשם", "דרך", "הר", "ורד"]
        rare = ["זית", "חלב", "טל", "ים"]
        docs = {}
        for d in range(6):
            paras = []
            for _ in range(60):
                words = [rnd.choice(common) for _ in range(rnd.randint(4, 14))]
                for _ in range(rnd.randint(0, 2)):
                    words.insert(rnd.randrange(len(words) + 1), rnd.choice(rare))
                paras.append(" ".join(words))
            docs[f"r{d}.docx"] = paras
            build_docx(os.path.join(self.dir, f"r{d}.docx"), paras)
        files = resolve_items([(self.dir, "folder")])
        self.db.update(self.db.stale_files(files))
        ids = self.db.file_ids(files)
        searcher = Searcher(self.db)
        vocab = common + rare
        checked = with_hits = 0
        for _ in range(250):
            n = rnd.choice([2, 3, 4, 4, 5])
            query = [rnd.choice(vocab) for _ in range(n)]
            gap = rnd.choice([0, 1, 2, 4])
            ordered = rnd.random() < 0.5
            k = rnd.choice([0, 0, n - 1]) if n > 2 else 0
            res = searcher.search(" ".join(query), ids, SearchOptions(
                prefixes=False, max_gap=gap, ordered=ordered, min_terms=k))
            required = k or n
            expected = 0
            for paras in docs.values():
                for text in paras:
                    toks = normalize_text(text)
                    positions = [[i for i, w in enumerate(toks) if w == normalize_text(q)[0]] for q in query]
                    if required == n:
                        expected += max_disjoint(brute_intervals(positions, gap, ordered, required)) \
                            if all(positions) else 0
                    else:
                        expected += bool(brute_intervals(positions, gap, ordered, required))
            got = res.total if required == n else len({(h.file_id, h.para_idx) for h in res.hits})
            self.assertEqual(got, expected, (query, gap, ordered, k))
            checked += 1
            with_hits += bool(expected)
        self.assertGreater(with_hits, 60)


if __name__ == "__main__":
    unittest.main()
