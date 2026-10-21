"""דירוג תוצאות: כמה ההתאמה קרובה למה שהמשתמש הקליד.

ציון בין 0 ל-1 שמורכב משלושה רכיבים:
  * דיוק הצורה (55%) – מילה זהה למילת החיפוש = 1; מילת החיפוש עם תחילית או
    סיומת (והלך, הלכה) = כ-0.85; צורה עם אותיות שנוספו בתוכה (הליכה, הולך)
    או שהושמטו = כ-0.65. כל אות נוספת מורידה מעט.
  * קרבה (35%) – כמה מילים מפרידות בין מילות החיפוש (צירוף צמוד = 1).
  * סדר (10%) – האם המילים מופיעות באותו סדר כמו בשאילתה.
בחיפוש של מילה אחת הציון הוא דיוק הצורה בלבד.
בחיפוש "לפחות N מהמילים" הציון מוכפל ב-(מספר המילים שנמצאו / מספר מילות החיפוש)²,
כך שתוצאה עם כל המילים קודמת בדרך כלל לתוצאה חלקית.
"""

import re


class Scorer:
    def __init__(self, pos_terms):
        self.n = len(pos_terms)
        self.plain = []
        self.wild = []
        for t in pos_terms:
            for a in t.alts:
                if "*" in a or "?" in a:
                    rx = "".join("[^\\n]*" if c == "*" else "[^\\n]" if c == "?" else re.escape(c) for c in a)
                    self.wild.append(re.compile(rx))
                else:
                    self.plain.append(a)
        self._cache = {}

    def word_quality(self, word: str) -> float:
        q = self._cache.get(word)
        if q is not None:
            return q
        best = 0.3
        for alt in self.plain:
            if word == alt:
                best = 1.0
                break
            extra = abs(len(word) - len(alt))
            if alt in word:
                best = max(best, 0.88 - 0.04 * extra)
            else:
                best = max(best, 0.68 - 0.04 * extra)
        for rx in self.wild:
            best = max(best, 0.95 if rx.fullmatch(word) else 0.6)
        self._cache[word] = q = max(0.3, best)
        return q

    def score(self, span, words, terms_at):
        """span: מיקומים; words: הצורות; terms_at: לכל מיקום – אינדקס המילה בשאילתה.
        מחזיר (ציון, האם_מדויק)."""
        quality = sum(self.word_quality(w) for w in words) / len(words)
        if self.n == 1:
            return quality, quality == 1.0
        m = len(set(terms_at))
        window, in_order = _best_window(span, terms_at, m)
        extra = max(0, window - m)
        proximity = 1.0 / (1.0 + 0.5 * extra)
        score = 0.55 * quality + 0.35 * proximity + 0.10 * (1.0 if in_order else 0.0)
        score *= (m / self.n) ** 2
        exact = quality == 1.0 and extra == 0 and in_order and m == self.n
        return score, exact


def _best_window(span, terms_at, n):
    """החלון הקצר ביותר שמכיל את כל מילות השאילתה, והאם הן בסדר בתוכו."""
    if len(span) == n:
        return span[-1] - span[0] + 1, list(terms_at) == sorted(terms_at)
    if len(span) == 1:
        return 1, True
    counts, have, lo = {}, 0, 0
    best = (span[-1] - span[0] + 1, 0, len(span) - 1)
    for hi in range(len(span)):
        t = terms_at[hi]
        counts[t] = counts.get(t, 0) + 1
        if counts[t] == 1:
            have += 1
        while have == n:
            w = span[hi] - span[lo] + 1
            if w < best[0]:
                best = (w, lo, hi)
            tl = terms_at[lo]
            counts[tl] -= 1
            if counts[tl] == 0:
                have -= 1
            lo += 1
    w, a, b = best
    seen, order = set(), []
    for t in terms_at[a:b + 1]:
        if t not in seen:
            seen.add(t)
            order.append(t)
    return w, order == sorted(order)
