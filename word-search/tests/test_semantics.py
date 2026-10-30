"""כללי החיפוש והדירוג מול הגדרה עצמאית (חישוב ישיר): נכונות, מונוטוניות ומדרג הדירוג.

ההגדרות מתועדות ב-docs/SEARCH_RULES.md:
  * התאמה = מיקום שונה לכל מילה; בין כל שתי מילים סמוכות לכל היותר N מילים אחרות (N = הרווח).
  * "לפי הסדר" – אותו סדר כמו בשאילתה; ביטוי במירכאות = צמוד לפי הסדר, בלי קשר להגדרות.
  * דירוג: כל המילים ← קרבה ← סדר ← דיוק הצורה; בהתאמה חלקית מילה נדירה שוקלת יותר מנפוצה.
"""

import itertools
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hebsearch.matching import find_spans  # noqa: E402
from hebsearch.morphology import MatchOptions, word_pattern  # noqa: E402
from hebsearch.normalize import normalize_word, tokenize  # noqa: E402
from hebsearch.ranking import Scorer, term_weights  # noqa: E402
from hebsearch.search import SEG_MATCH, Searcher, SearchOptions, parse_query, quoted_phrase  # noqa: E402

from docx_builder import build_docx  # noqa: E402
from test_v2 import Base  # noqa: E402


def brute(positions, gap, ordered, k):
    """כל ההתאמות האפשריות לפי ההגדרה (חישוב ישיר)."""
    n = len(positions)
    out = []
    for subset in itertools.chain.from_iterable(itertools.combinations(range(n), r) for r in range(k, n + 1)):
        for choice in itertools.product(*[positions[t] for t in subset]):
            if len(set(choice)) < len(choice):
                continue
            order = sorted(range(len(choice)), key=lambda i: choice[i])
            if ordered and [subset[i] for i in order] != sorted(subset):
                continue
            ps = [choice[i] for i in order]
            if gap is not None and any(b - a - 1 > gap for a, b in zip(ps, ps[1:])):
                continue
            out.append(ps)
    return out


class MatchingDefinitionTest(unittest.TestCase):
    def test_find_spans_agrees_with_the_definition(self):
        rng = random.Random(11)
        for _ in range(1500):
            n = rng.randint(2, 4)
            length = rng.randint(4, 14)
            positions = [sorted(rng.sample(range(length), rng.randint(0, min(4, length)))) for _ in range(n)]
            gap = rng.choice([0, 0, 1, 2, 3])
            ordered = rng.random() < 0.5
            k = rng.randint(max(1, n - 1), n)
            got = find_spans(positions, gap, ordered, k)
            self.assertEqual(bool(got), bool(brute(positions, gap, ordered, k)), (positions, gap, ordered, k))
            for chain in got:                                   # כל התאמה שמוחזרת תקפה
                ps, ts = [p for p, _ in chain], [t for _, t in chain]
                self.assertEqual(ps, sorted(set(ps)))
                self.assertGreaterEqual(len(set(ts)), k)
                self.assertTrue(all(p in positions[t] for p, t in chain))
                self.assertTrue(all(b - a - 1 <= gap for a, b in zip(ps, ps[1:])), chain)
                if ordered:
                    self.assertEqual(ts, sorted(ts), chain)
            # מונוטוניות: הרחבת הרווח / ביטול הסדר / הורדת הדרישה / "בכל הפסקה" לא מאבדות תוצאות
            if got:
                self.assertTrue(find_spans(positions, gap + 1, ordered, k))
                self.assertTrue(find_spans(positions, gap, False, k))
                self.assertTrue(find_spans(positions, None, ordered, k))
                if k > 1:
                    self.assertTrue(find_spans(positions, gap, ordered, k - 1))

    def test_adjacent_words_have_no_word_between(self):
        self.assertEqual(find_spans([[3], [4]], 0, True, 2), [[(3, 0), (4, 1)]])
        self.assertEqual(find_spans([[3], [5]], 0, True, 2), [])           # מילה אחת ביניהן
        self.assertEqual(len(find_spans([[3], [5]], 1, True, 2)), 1)


class EndToEndOracleTest(Base):
    """שרשרת מלאה (אינדקס ← שליפה ← צירופים) מול חישוב עצמאי על אותו טקסט."""

    def test_search_agrees_with_an_independent_oracle(self):
        rng = random.Random(5)
        base = ["שבת", "משה", "הלך", "דרך", "בית", "ספר", "עם", "אל", "כי", "לא", "מים", "שם", "איסור", "ייחוד"]
        prefixes = ["", "ו", "ה", "ב", "ל", "מ", "וה", "שב", "כש"]
        paras_of = {}
        files = []
        for i in range(4):
            paras = [" ".join(rng.choice(prefixes) + rng.choice(base) + rng.choice(["", "", ",", "."])
                              for _ in range(rng.randint(3, 30))) for _ in range(20)]
            path = os.path.join(self.dir, f"o{i}.docx")
            build_docx(path, paras)
            files.append(path)
            paras_of[path] = paras
        ids = self.index([(f, "file") for f in files])
        s = Searcher(self.db)
        checked = 0
        for _ in range(250):
            nq = rng.randint(1, 4)
            words = [rng.choice(base) for _ in range(nq)]
            query = " ".join(words) + (" -" + rng.choice(base) if rng.random() < 0.2 else "")
            use_prefixes = rng.random() < 0.7
            gap, ordered = rng.choice([0, 0, 1, 2, 4]), rng.random() < 0.6
            whole = nq > 1 and rng.random() < 0.15
            min_terms = rng.choice([0, 0, max(1, nq - 1)])
            res = s.search(query, ids, SearchOptions(prefixes=use_prefixes, max_gap=gap, ordered=ordered,
                                                     whole_paragraph=whole, min_terms=min_terms))
            terms = parse_query(query)
            mo = MatchOptions(prefixes=use_prefixes)
            rx = [[re.compile(word_pattern(a, mo)) for a in t.alts] for t in terms if not t.negate]
            nrx = [[re.compile(word_pattern(a, mo)) for a in t.alts] for t in terms if t.negate]
            k = nq if not min_terms else max(1, min(min_terms, nq))
            expected = {}
            for f in files:
                for pi, text in enumerate(paras_of[f]):
                    toks = [t[2] for t in tokenize(text)]
                    if any(any(r.fullmatch(w) for r in group) for group in nrx for w in toks):
                        continue
                    positions = [[i for i, w in enumerate(toks) if any(r.fullmatch(w) for r in group)] for group in rx]
                    if sum(1 for p in positions if p) < k:
                        continue
                    found = find_spans(positions, None if whole else gap, ordered, k)
                    if found:
                        expected[(f, pi)] = len(found)
            got = {}
            for h in res.hits:
                got[(h.path, h.para_idx)] = got.get((h.path, h.para_idx), 0) + 1
            self.assertEqual(got, expected, (query, use_prefixes, gap, ordered, whole, min_terms))
            checked += 1
        self.assertEqual(checked, 250)


class RankingRulesTest(Base):
    def make(self, name, paras):
        path = os.path.join(self.dir, name)
        build_docx(path, paras)
        return self.index([(path, "file")])

    def test_phrase_tiers(self):
        """צירוף צמוד בצורות זהות ← צמוד עם תחילית ← צמוד בסדר הפוך ← מרווח של מילה ← מרווח גדול."""
        ids = self.make("tiers.docx", [
            "איסור ייחוד",                            # 0 מדויק
            "באיסור ייחוד",                           # 1 צמוד, תחילית
            "ייחוד איסור",                            # 2 צמוד בסדר הפוך
            "איסור גמור ייחוד",                       # 3 מילה אחת ביניהן
            "איסור א ב ג ד ייחוד",                    # 4 ארבע מילים ביניהן
        ])
        r = self.search(ids, "איסור ייחוד", max_gap=5, ordered=False)
        self.assertEqual([h.para_idx for h in r.hits], [0, 1, 2, 3, 4])
        self.assertTrue(r.hits[0].exact)
        self.assertFalse(r.hits[1].exact)

    def test_spelling_variant_outranks_prefixed_form(self):
        ids = self.make("var.docx", ["ובשמרה ", "שמירה", "שמרה"])
        r = self.search(ids, "שמרה", ahevi="vy")
        self.assertEqual(r.hits[0].para_idx, 2)                      # זהה
        self.assertEqual(r.hits[1].para_idx, 1)                      # כתיב מלא של אותה מילה
        self.assertEqual(r.hits[2].para_idx, 0)                      # תחילית

    def test_rare_word_outweighs_common_words_in_partial_matches(self):
        common = ["של את על אל " + str(i) for i in range(30)]
        ids = self.make("idf.docx", common + ["של את", "את ייחוד"])
        r = self.search(ids, "של את ייחוד", min_terms=2)
        order = [(h.para_idx) for h in r.hits]
        self.assertEqual(order[0], 31)                               # "את ייחוד" (כולל המילה הנדירה) קודם
        self.assertIn(30, order)

    def test_quoted_phrase_overrides_gap_options(self):
        ids = self.make("q.docx", ["איסור ייחוד", "איסור גמור ייחוד", "ייחוד איסור"])
        loose = self.search(ids, "איסור ייחוד", max_gap=5, ordered=False)
        self.assertEqual(loose.total, 3)
        exact = self.search(ids, '"איסור ייחוד"', max_gap=5, ordered=False, whole_paragraph=True)
        self.assertTrue(exact.phrase)
        self.assertEqual([h.para_idx for h in exact.hits], [0])

    def test_only_matched_words_are_marked_in_multiword(self):
        ids = self.make("m.docx", ["איסור ייחוד וגם באיסור אחר"])
        r = self.search(ids, "איסור ייחוד", max_gap=0)
        marked = [t for t, k in r.hits[0].snippet if k == SEG_MATCH]
        self.assertEqual(marked, ["איסור", "ייחוד"])


class RankingUnitsTest(unittest.TestCase):
    def test_term_weights(self):
        self.assertEqual(term_weights([100, 100]), [1.0, 1.0])
        w = term_weights([1000, 250, 0])
        self.assertEqual(w[0], 1.0)
        self.assertAlmostEqual(w[1], 3.0)                            # רבע מהנפוצה: 1 + log2(4)
        self.assertEqual(w[2], 8.0)                                  # מילה שלא קיימת

    def test_quoted_phrase_syntax(self):
        self.assertEqual(quoted_phrase('"איסור ייחוד"'), "איסור ייחוד")
        self.assertEqual(quoted_phrase('“איסור ייחוד”'), "איסור ייחוד")
        self.assertEqual(quoted_phrase('"הרמב״ם אמר"'), "הרמב״ם אמר")
        self.assertIsNone(quoted_phrase('"שבת"'))                    # מילה אחת – לא ביטוי
        self.assertIsNone(quoted_phrase('איסור "ייחוד"'))
        self.assertIsNone(quoted_phrase("איסור ייחוד"))

    def test_scorer_levels(self):
        terms = parse_query("שמרה")
        sc = Scorer(terms, ahevi="vy")
        self.assertEqual(sc.word_quality("שמרה"), 1.0)
        self.assertGreater(sc.word_quality("שמירה"), sc.word_quality("ושמרה"))
        self.assertGreater(sc.word_quality("ושמרה"), sc.word_quality("שומרים"))
        self.assertLess(Scorer(terms).word_quality("שמירה"), 0.7)   # בלי אהו״י – זו הטיה


class MorphologyGoldTest(unittest.TestCase):
    """צורות שחייבות להתאים ושאסור שיתאימו (רשימת זהב קטנה)."""

    @staticmethod
    def matches(query, form, **kw):
        pattern = re.compile("^(?:" + word_pattern(query, MatchOptions(**kw)) + ")$")
        return bool(pattern.match(normalize_word(form)))

    def test_prefixes(self):
        for form in ("דרך", "בדרך", "והדרך", "כשבדרך", "מהדרך", "שבדרך", "ולדרך"):
            self.assertTrue(self.matches("דרך", form), form)
        for form in ("דרכים", "דרכו", "אדרך", "מדרכה"):
            self.assertFalse(self.matches("דרך", form), form)
        self.assertFalse(self.matches("דרך", "בדרך", prefixes=False))
        self.assertTrue(self.matches("דרך", "דרך", prefixes=False))

    def test_niqqud_finals_and_quotes_are_ignored(self):
        self.assertTrue(self.matches("בראשית", "בְּרֵאשִׁית"))
        self.assertTrue(self.matches("הלך", "הָלַךְ"))
        self.assertTrue(self.matches("רש\"י", "רש״י"))
        self.assertTrue(self.matches("רשי", "רש\"י"))

    def test_inflections(self):
        for form in ("הלכה", "הליכה", "הולכים", "וילך", "ללכת"):
            self.assertTrue(self.matches("הלך", form, inflections=True), form)
        self.assertFalse(self.matches("הלך", "הלכה"))               # בלי הטיות – לא

    def test_ahevi(self):
        self.assertTrue(self.matches("שמרה", "שמירה", ahevi="vy"))
        self.assertTrue(self.matches("שמרה", "שומרה", ahevi="vy"))
        self.assertFalse(self.matches("שמרה", "שמירה"))
        # "כל אותיות אהו״י" על מילה שכמעט כולה אהו״י (אהבה ← ב) לא הופך לתבנית שמתאימה לכל דבר
        self.assertTrue(self.matches("אהבה", "אוהבה", ahevi="all"))
        for junk in ("ב", "הב", "אב", "בה"):
            self.assertFalse(self.matches("אהבה", junk, ahevi="all"), junk)

    def test_tokens(self):
        words = lambda t: [x[2] for x in tokenize(t)]               # noqa: E731
        self.assertEqual(words("בית-המדרש"), ["בית", "המדרש"])        # מקף מפריד מילים
        self.assertEqual(words("שלום, עולם. שלום!"), ["שלומ", "עולמ", "שלומ"])   # פיסוק אינו מילה
        self.assertEqual(words("הרמב\"ם אמר"), ["הרמבמ", "אמר"])      # גרשיים בתוך מילה – חלק ממנה
        self.assertEqual(words("ר' עקיבא"), ["ר", "עקיבא"])           # גרש לפני רווח – לא


if __name__ == "__main__":
    unittest.main()
