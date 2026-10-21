"""דירוג תוצאות: כמה ההתאמה קרובה למה שהמשתמש הקליד.

ציון בין 0 ל-1 שמורכב משלושה רכיבים:
  * דיוק הצורה (55%) – מילה זהה למילת החיפוש = 1; מילת החיפוש עם תחילית או
    סיומת (והלך, הלכה) = כ-0.85; צורה עם אותיות שנוספו בתוכה (הליכה, הולך)
    או שהושמטו = כ-0.65. כל אות נוספת מורידה מעט.
  * קרבה (35%) – כמה מילים מפרידות בין מילות החיפוש (צירוף צמוד = 1).
  * סדר (10%) – האם המילים מופיעות באותו סדר כמו בשאילתה.
בחיפוש של מילה אחת הציון הוא דיוק הצורה בלבד.
בחיפוש "לפחות N מהמילים" הציון מוכפל ב-(כיסוי)², כך שתוצאה עם כל המילים קודמת לתוצאה חלקית.
הכיסוי מחושב לפי משקל כל מילה (כמו IDF במנועי חיפוש): מילה נדירה במסמכים חשובה יותר ממילה נפוצה
(של, את, על), ולכן התאמה חלקית שכוללת את המילה הנדירה קודמת להתאמה חלקית שכוללת רק מילים נפוצות.
כשהמשקלים שווים הכיסוי הוא פשוט מספר המילים שנמצאו חלקי מספר מילות החיפוש.
"""

import re

from .morphology import AHEVI_SETS


def term_weights(costs):
    """משקל לכל מילת חיפוש לפי הנפוצות שלה באינדקס (costs – גודל רשימות המופעים; 0 = לא קיימת).
    הנפוצה ביותר מקבלת 1, ומילה נדירה פי 2 – 2, פי 4 – 3 וכן הלאה (לוגריתמי, עד 8)."""
    import math
    known = [c for c in costs if c > 0]
    if not known:
        return [1.0] * len(costs)
    top = max(known)
    return [min(8.0, 1.0 + math.log2(top / c)) if c > 0 else 8.0 for c in costs]


class Scorer:
    def __init__(self, pos_terms, weights=None, ahevi="none"):
        self.n = len(pos_terms)
        self.weights = list(weights) if weights else [1.0] * self.n
        self.total_weight = sum(self.weights) or 1.0
        self.matres = AHEVI_SETS.get(ahevi, "")
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
            if self.matres:
                # כתיב מלא/חסר (שמרה ↔ שמירה) הוא אותה מילה באיות אחר – כמעט זהה, לא "הטיה"
                sw, sa = self._skeleton(word), self._skeleton(alt)
                if sw == sa:
                    best = max(best, 0.95 - 0.01 * extra)
                    continue
                if sa in sw:
                    best = max(best, 0.86 - 0.04 * abs(len(sw) - len(sa)))
                    continue
            if alt in word:
                best = max(best, 0.88 - 0.04 * extra)
            else:
                best = max(best, 0.68 - 0.04 * extra)
        for rx in self.wild:
            best = max(best, 0.95 if rx.fullmatch(word) else 0.6)
        self._cache[word] = q = max(0.3, best)
        return q

    def _skeleton(self, word):
        """המילה בלי אותיות אהו״י – חוץ מהראשונה (ו בתחילת מילה היא לרוב תחילית, לא כתיב מלא)."""
        return word[:1] + "".join(c for c in word[1:] if c not in self.matres)

    def coverage(self, terms_at):
        """כמה מ"משקל" מילות החיפוש נמצא בהתאמה (1 = כולן)."""
        found = set(terms_at)
        if len(found) >= self.n:
            return 1.0
        return sum(self.weights[t] for t in found) / self.total_weight

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
        score *= self.coverage(terms_at) ** 2
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
