"""בדיקות לאלגוריתם הצירופים, כולל השוואה לחיפוש ממצה (כל ההשמות האפשריות)."""

import itertools
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hebsearch.matching import find_spans  # noqa: E402


def valid(chain, positions, gap, ordered):
    ps = [p for p, _ in chain]
    ts = [t for _, t in chain]
    return (len(set(ps)) == len(ps) and len(set(ts)) == len(ts)
            and all(p in positions[t] for p, t in chain)
            and ps == sorted(ps)
            and (gap is None or all(b - a - 1 <= gap for a, b in zip(ps, ps[1:])))
            and (not ordered or ts == sorted(ts)))


def brute_intervals(positions, gap, ordered, k):
    """כל ההתאמות האפשריות כמקטעים (התחלה, סוף)."""
    n = len(positions)
    out = set()
    for size in range(k, n + 1):
        for terms in itertools.combinations(range(n), size):
            for combo in itertools.product(*(positions[t] for t in terms)):
                chain = sorted(zip(combo, terms))
                if valid(chain, positions, gap, ordered):
                    out.add((chain[0][0], chain[-1][0]))
    return out


def max_disjoint(intervals):
    count, end = 0, -1
    for s, e in sorted(intervals, key=lambda x: x[1]):
        if s > end:
            count, end = count + 1, e
    return count


class FindSpansTest(unittest.TestCase):
    def test_greedy_trap(self):
        # מילה 2 מופיעה ב-1 וב-3; רק 3 מאפשר להגיע למילה 3 שב-6 (רווח עד 2)
        self.assertEqual(find_spans([[0], [1, 3], [6]], gap=2), [[(0, 0), (3, 1), (6, 2)]])

    def test_four_word_phrase(self):
        pos = [[0, 10], [1, 11], [2, 15], [3, 12]]
        self.assertEqual(find_spans(pos, gap=0), [[(0, 0), (1, 1), (2, 2), (3, 3)]])
        self.assertEqual(find_spans(pos, gap=0, ordered=False), [[(0, 0), (1, 1), (2, 2), (3, 3)]])

    def test_repeated_word_needs_two_occurrences(self):
        # "שבת שבת": אותה מילה פעמיים – צריך שני מופעים שונים
        self.assertEqual(find_spans([[4], [4]], gap=3), [])
        self.assertEqual(find_spans([[4, 6], [4, 6]], gap=3), [[(4, 0), (6, 1)]])

    def test_order(self):
        pos = [[5], [2]]
        self.assertEqual(find_spans(pos, gap=3, ordered=True), [])
        self.assertEqual(find_spans(pos, gap=3, ordered=False), [[(2, 1), (5, 0)]])

    def test_partial_prefers_more_words(self):
        # 3 מתוך 4 נדרשות; ליד יש גם את הרביעית – לוקחים את כל ה-4
        pos = [[0], [1], [2], [4]]
        self.assertEqual(len(find_spans(pos, gap=1, required=3)[0]), 4)
        self.assertEqual(len(find_spans([[0], [1], [2], [9]], gap=1, required=3)[0]), 3)

    def test_whole_paragraph(self):
        self.assertEqual(len(find_spans([[0], [50], [99]], gap=None)), 1)
        self.assertEqual(find_spans([[0], [50], []], gap=None), [])
        self.assertEqual(len(find_spans([[0], [50], []], gap=None, required=2)), 1)

    def test_against_brute_force(self):
        rnd = random.Random(2024)
        cases = 0
        for _ in range(6000):
            n = rnd.choice([2, 3, 4, 5, 6])
            gap = rnd.choice([0, 1, 2, 3, 5])
            ordered = rnd.random() < 0.5
            k = rnd.choice([n, n, max(1, n - 1), max(1, n - 2)])
            length = rnd.randint(3, 16)
            # לפעמים מילה אחת מתאימה לכמה מילות חיפוש (כמו הלך/הלכה עם הטיות)
            positions = [sorted(rnd.sample(range(length), rnd.randint(0, 3))) for _ in range(n)]
            got = find_spans(positions, gap, ordered, k)
            want = brute_intervals(positions, gap, ordered, k)
            for chain in got:
                self.assertTrue(valid(chain, positions, gap, ordered), (positions, gap, ordered, chain))
                self.assertGreaterEqual(len(chain), k)
            ends = [c[-1][0] for c in got]
            starts = [c[0][0] for c in got]
            self.assertTrue(all(s > e for s, e in zip(starts[1:], ends)), "התאמות חופפות")
            if k == n:
                # כל המילים: מספר ההתאמות הנפרדות המרבי
                self.assertEqual(len(got), max_disjoint(want), (positions, gap, ordered, k, got))
            else:
                # חלק מהמילים: מעדיפים התאמה עם יותר מילים, אבל שום התאמה לא הולכת לאיבוד –
                # כל התאמה אפשרית נמצאת בתוך תוצאה שהוחזרה או צמודה אליה
                reach = gap + 1
                for s0, e0 in want:
                    self.assertTrue(any(s0 <= c[-1][0] + reach and e0 >= c[0][0] - reach for c in got),
                                    (positions, gap, ordered, k, got, (s0, e0)))
            cases += bool(want)
        self.assertGreater(cases, 2000)


if __name__ == "__main__":
    unittest.main()
