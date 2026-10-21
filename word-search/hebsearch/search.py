"""מנוע החיפוש.

שלבים:
 1. פירוק השאילתה למילים (| = או, -מילה = בלי, * ו-? = תווים כלליים).
 2. לכל מילה: הרצת התבנית (morphology) על אוצר המילים → קבוצת צורות.
 3. שליפת המופעים (פסקה, מיקום) של הצורות מהאינדקס, מהמילה הנדירה לנפוצה,
    וחיתוך ברמת הפסקה.
 4. בדיקת מרחק וסדר בין המילים על המיקומים בלבד – בלי לקרוא טקסט.
 5. קטע התצוגה (20 מילים לפני ו-20 אחרי) נבנה רק לתוצאות שמוצגות בפועל
    (materialize), כך שגם חיפוש עם עשרות אלפי תוצאות חוזר מיד.
"""

import re
import threading
import time
from bisect import bisect_left, bisect_right
from collections import Counter, OrderedDict
from dataclasses import dataclass, field, replace

from .extract import KIND_BODY, KIND_ENDNOTE, KIND_FOOTNOTE, KIND_TEXTBOX
from .matching import find_spans
from .morphology import MatchOptions, normalize_query_word, term_regex
from .normalize import restore_finals, tokenize
from .ranking import Scorer

MAX_VARIANTS = 50000
MAX_TERMS = 12

SEG_TEXT, SEG_MATCH, SEG_GAP, SEG_PARA = 0, 1, 2, 3


@dataclass
class SearchOptions:
    prefixes: bool = True
    inflections: bool = False
    ahevi: str = "none"          # none | vy | all
    max_gap: int = 0             # מספר המילים המרבי בין מילה נבחרת לבאה
    min_terms: int = 0           # כמה מילים לפחות צריכות להימצא (0 = כולן)
    whole_paragraph: bool = False
    ordered: bool = True
    context_words: int = 20      # מילים לפני ואחרי
    max_hits: int = 100000
    sort: str = "relevance"      # relevance | document

    def match_options(self):
        return MatchOptions(self.prefixes, self.inflections, self.ahevi)


@dataclass
class Term:
    text: str
    alts: list
    negate: bool = False
    words: set = field(default_factory=set)


@dataclass
class Hit:
    file_id: int
    path: str
    para_idx: int
    span: tuple              # מיקומי המילים שנמצאו בתוך הפסקה
    words: tuple             # הצורות המנורמלות שנמצאו
    score: float = 0.0       # 0..1 – כמה ההתאמה קרובה לשאילתה
    covered: int = 1         # כמה ממילות החיפוש נמצאו בתוצאה
    exact: bool = False      # בדיוק המילים שהוקלדו, צמודות ובסדר
    # השדות הבאים מתמלאים ב-Searcher.materialize
    ready: bool = False
    line: int = 0            # מספר שורה בעמוד (PDF)
    y: float = -1.0          # גובה השורה בדף בנקודות (PDF) – לקפיצה מדויקת
    para_no: int = 0
    kind: int = KIND_BODY
    note: int = 0
    page: int = 0
    snippet: list = field(default_factory=list)   # [(טקסט, סוג_קטע)]
    needle: str = ""         # הטקסט המקורי של ההתאמה (לאיתור בוורד)
    needle_offset: int = 0

    @property
    def location(self) -> str:
        parts = []
        if self.page:
            parts.append(f"עמוד {self.page}")
        if self.line:
            parts.append(f"שורה {self.line}")
        elif self.kind == KIND_FOOTNOTE:
            parts.append(f"הערת שוליים {self.note}")
        elif self.kind == KIND_ENDNOTE:
            parts.append(f"הערת סיום {self.note}")
        elif self.kind == KIND_TEXTBOX:
            parts.append("תיבת טקסט")
        else:
            parts.append(f"פסקה {self.para_no}")
        return " · ".join(parts)


class Highlight(frozenset):
    """הצורות לסימון בקטעי התצוגה. בחיפוש של כמה מילים (multi) מסומנות רק המילים של ההתאמה עצמה:
    מופע אחר של מילת חיפוש באותו קטע (למשל "איסור" מעט הלאה מהצירוף "איסור ייחוד") אינו חלק
    מההתאמה, ואם יסומן ייראה כאילו נמצאה התאמה עם מרווח."""

    def __new__(cls, words=(), multi=False):
        self = super().__new__(cls, words)
        self.multi = multi
        return self


@dataclass
class SearchResult:
    query: str
    hits: list = field(default_factory=list)
    total: int = 0
    files: list = field(default_factory=list)       # [(file_id, path, count)]
    forms: Counter = field(default_factory=Counter)
    highlight: set = field(default_factory=set)     # כל הצורות שיש לסמן בקטעי התצוגה
    terms: list = field(default_factory=list)
    elapsed: float = 0.0
    truncated: bool = False
    message: str = ""
    searched_files: int = 0
    n_terms: int = 0                                # מספר מילות החיפוש (בלי "-מילה")
    required: int = 0                               # כמה מהן נדרשו
    near_miss: tuple = None                         # (נדרשות, תוצאות) – הצעה כשאין תוצאות
    cancelled: bool = False


def parse_query(query: str):
    query = re.sub(r"(?<=\S)[-־](?=\S)", " ", query)
    terms = []
    for part in query.split():
        neg = part.startswith("-") and len(part) > 1
        if neg:
            part = part[1:]
        alts = [a for a in (normalize_query_word(x) for x in part.split("|")) if a.strip("*?")]
        if alts:
            terms.append(Term(part, alts, neg))
    return terms


class _VocabCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.key = None
        self.joined = ""
        self.ids = {}

    def get(self, db):
        key = (db.path, db.vocab_version())
        with self.lock:
            if key != self.key:
                rows = db.load_vocab()
                self.joined = "\n".join(w for _, w in rows)
                self.ids = {w: i for i, w in rows}
                self.key = key
            return self.joined, self.ids


_vocab_cache = _VocabCache()


class _ParaCache:
    """מטמון LRU לטקסט המפוענח של קבצים (נשמר בין חיפושים).
    מוגבל בנפח (מספר תווים כולל) ולא במספר קבצים: קובץ אחד גדול יכול להיות עשרות מגה-בייט בזיכרון,
    ומטמון של 128 כאלה יכול לתקוע את המחשב."""

    def __init__(self, max_chars=20_000_000):
        self.max_chars = max_chars
        self.total = 0
        self.data = OrderedDict()      # key -> (value, chars)
        self.lock = threading.Lock()

    def get(self, db, fid):
        key = (db.path, fid)
        with self.lock:
            hit = self.data.get(key)
            if hit is not None:
                self.data.move_to_end(key)
                return hit[0]
        paras = db.file_paras(fid)
        body_no, numbers = 0, []
        for p in paras:
            if p[2] == KIND_BODY:
                body_no += 1
            numbers.append(body_no)
        val = (paras, numbers, {})
        chars = sum(len(p[0]) for p in paras) + 1
        with self.lock:
            old = self.data.pop(key, None)
            if old is not None:
                self.total -= old[1]
            self.data[key] = (val, chars)
            self.total += chars
            while self.total > self.max_chars and len(self.data) > 1:
                _, (_, c) = self.data.popitem(last=False)
                self.total -= c
        return val

    def invalidate(self):
        with self.lock:
            self.data.clear()
            self.total = 0


para_cache = _ParaCache()


def _phrase_matches(maps):
    """צירוף צמוד לפי הסדר: מילה i נמצאת במיקום p+i. maps[i] = {מיקום: מילה}.
    מחזיר [(span, words, terms_at)] ללא חפיפות."""
    n = len(maps)
    rest = maps[1:]
    out = []
    last = -1
    for p in sorted(maps[0]):
        if p <= last:
            continue
        ok = True
        for i, m in enumerate(rest, 1):
            if p + i not in m:
                ok = False
                break
        if ok:
            span = tuple(range(p, p + n))
            words = tuple(m[p + i] for i, m in enumerate(maps))
            out.append((span, words, tuple(range(n))))
            last = p + n - 1
    return out


class Searcher:
    def __init__(self, db, context_words=20):
        self.db = db
        self.context_words = context_words

    # ---------- שלב 1-4: מציאת ההתאמות ----------
    def _occurrences(self, ids, fileset, keys=None, on_bytes=None):
        """(קובץ, פסקה) → {מיקום: מילה}. עם keys – רק בפסקאות האלה.
        on_bytes(n): נקרא מדי פעם עם מספר הבתים שנקראו מהאינדקס (לאחוזי התקדמות).

        רשימת המופעים של כל מילה ממוינת לפי פסקה, ולכן כשצריך רק מעט פסקאות
        מתוך רשימה ארוכה (מילה נפוצה) מאתרים אותן בחיפוש בינארי במקום לעבור
        על כל המופעים.
        """
        occ = {}
        want = None
        if keys is not None:
            want = {}
            for f, p in keys:
                want.setdefault(f, []).append(p)
            for v in want.values():
                v.sort()
            fileset = fileset & set(want)
        read = 0
        for wid, fid, arr in self.db.postings(ids, fileset):
            word = self._id_word[wid]
            if on_bytes is not None:
                read += len(arr) * 4
                if read > 400_000:
                    if on_bytes(read) is False:      # בוטל
                        return occ
                    read = 0
            wanted = want.get(fid) if want is not None else None
            if wanted is None or len(wanted) * 8 > len(arr):
                it = iter(arr)
                wset = set(wanted) if wanted is not None else None
                for para, pos in zip(it, it):
                    if wset is not None and para not in wset:
                        continue
                    d = occ.get((fid, para))
                    if d is None:
                        occ[(fid, para)] = {pos: word}
                    else:
                        d[pos] = word
                continue
            paras, poss = arr[0::2], arr[1::2]
            for para in wanted:
                lo = bisect_left(paras, para)
                if lo == len(paras) or paras[lo] != para:
                    continue
                hi = bisect_right(paras, para, lo)
                d = occ.setdefault((fid, para), {})
                for j in range(lo, hi):
                    d[poss[j]] = word
        return occ

    def search(self, query, file_ids, opts: SearchOptions, cancelled=None, progress=None) -> SearchResult:
        """file_ids: מילון מזהה_קובץ → נתיב (קבצי הסל).

        progress(שבר 0..1, טקסט) – דיווח התקדמות אמיתי לפי שלבים; cancelled() – ביטול באמצע.
        """
        t0 = time.perf_counter()
        self.context_words = opts.context_words
        res = SearchResult(query=query, searched_files=len(file_ids))

        def rep(frac, text=""):
            if progress:
                progress(max(0.0, min(1.0, frac)), text)

        def stop():
            if cancelled and cancelled():
                res.cancelled = True
                res.message = "החיפוש בוטל."
                res.elapsed = time.perf_counter() - t0
                return True
            return False

        rep(0.01, "מנתח את השאילתה")
        terms = parse_query(query)
        res.terms = terms
        pos_terms = [t for t in terms if not t.negate]
        neg_terms = [t for t in terms if t.negate]
        if not pos_terms:
            res.message = "יש להקליד לפחות מילה אחת לחיפוש."
            return res
        if not file_ids:
            res.message = "הסל ריק, או שאין בו מסמכים שנקראו בהצלחה."
            return res

        rep(0.02, "טוען את אוצר המילים")
        joined, vocab_ids = _vocab_cache.get(self.db)
        mopts = opts.match_options()
        for i, t in enumerate(terms):
            rx = term_regex(t.alts, mopts)
            t.words = {m.group() for m in rx.finditer(joined)} if rx else set()
            if len(t.words) > MAX_VARIANTS:
                res.message = f"המילה '{t.text}' רחבה מדי ({len(t.words):,} צורות). נסו לצמצם."
                return res
            rep(0.03 + 0.04 * (i + 1) / len(terms), "מחפש צורות של המילים")
        if stop():
            return res
        n = len(pos_terms)
        if n > MAX_TERMS:
            res.message = f"אפשר לחפש עד {MAX_TERMS} מילים בבת אחת."
            return res
        k = n if not opts.min_terms else max(1, min(opts.min_terms, n))
        res.n_terms, res.required = n, k
        missing = [t.text for t in pos_terms if not t.words]
        present = [i for i, t in enumerate(pos_terms) if t.words]
        if len(present) < k:
            res.message = "לא נמצאו במסמכים: " + ", ".join(missing)
            if k == n and n >= 2 and len(present) == n - 1:
                sub = self.search(query, file_ids, replace(opts, min_terms=n - 1), cancelled)
                if sub.total:
                    res.near_miss = (n - 1, sub.total)
            res.elapsed = time.perf_counter() - t0
            return res
        self._id_word = {vocab_ids[w]: w for t in terms for w in t.words}

        # סדר השליפה: מהמילה עם הכי מעט מופעים (לפי גודל הרשימות באינדקס).
        # פסקה עם k מתוך המילים חייבת להכיל לפחות אחת מ-(מספר_המילים - k + 1)
        # הנדירות ביותר – רק אותן שולפים במלואן; את השאר – רק בפסקאות האלה.
        ids_of = {i: [vocab_ids[w] for w in pos_terms[i].words] for i in present}
        cost = {i: self.db.postings_size(ids_of[i]) for i in present}
        present.sort(key=lambda i: cost[i])
        total_cost = max(1, sum(cost[i] for i in present))
        done_cost = 0

        def retrieval(i):
            label = f"שולף את המופעים של «{pos_terms[i].text}»"

            def on_bytes(nbytes):
                frac = (done_cost + min(nbytes_total[0] + nbytes, cost[i])) / total_cost
                nbytes_total[0] += nbytes
                rep(0.08 + 0.38 * frac, label)
                return not stop()

            nbytes_total = [0]
            return on_bytes

        r = len(present) - k + 1
        fileset = set(file_ids)
        occs, keys = {}, set()
        for i in present[:r]:
            occs[i] = self._occurrences(ids_of[i], fileset, on_bytes=retrieval(i))
            if stop():
                return res
            done_cost += cost[i]
            rep(0.08 + 0.38 * done_cost / total_cost, "שולף מופעים")
            keys |= set(occs[i])
        for i in present[r:]:
            if not keys:
                break
            occs[i] = self._occurrences(ids_of[i], fileset, keys, on_bytes=retrieval(i))
            if stop():
                return res
            done_cost += cost[i]
            rep(0.08 + 0.38 * done_cost / total_cost, "שולף מופעים")
            if k == n:
                keys &= set(occs[i])
                fileset = {f for f, _ in keys}
        if k < n:
            keys = {key for key in keys if sum(key in occ for occ in occs.values()) >= k}
        for t in neg_terms:
            if keys and t.words:
                occ = self._occurrences([vocab_ids[w] for w in t.words], {f for f, _ in keys}, keys)
                keys -= set(occ)
        if stop():
            return res

        scorer = Scorer(pos_terms)
        gap = None if opts.whole_paragraph else max(0, opts.max_gap)
        phrase = n >= 2 and k == n and opts.ordered and gap == 0      # צירוף צמוד לפי הסדר – מסלול מהיר
        per_file = Counter()
        best_in_file = {}
        hits = []
        empty = {}
        keys = list(keys)
        total_keys = max(1, len(keys))
        for idx, key in enumerate(keys):
            if idx & 1023 == 0:
                rep(0.47 + 0.45 * idx / total_keys, "בודק התאמות בין המילים")
                if stop():
                    return res
            maps = [occs.get(i, empty).get(key, empty) for i in range(n)]
            if n == 1:
                found = [((p,), (w,), (0,)) for p, w in sorted(maps[0].items())]
            elif phrase:
                found = _phrase_matches(maps)
            else:
                found = []
                for chain in find_spans([sorted(m) for m in maps], gap, opts.ordered, k):
                    found.append((tuple(p for p, _ in chain), tuple(maps[t][p] for p, t in chain),
                                  tuple(t for _, t in chain)))
            if not found:
                continue
            fid, para = key
            per_file[fid] += len(found)
            path = file_ids[fid]
            for span, words, terms_at in found:
                score, exact = scorer.score(span, words, terms_at)
                hits.append(Hit(fid, path, para, span, words, score=score, exact=exact,
                                covered=len(set(terms_at))))
                if score > best_in_file.get(fid, -1):
                    best_in_file[fid] = score

        rep(0.93, "מדרג את התוצאות")
        res.total = len(hits)
        raw_forms = Counter(w for h in hits for w in h.words)
        for w, c in raw_forms.items():
            res.forms[restore_finals(w)] += c
        res.highlight = Highlight(set().union(*(t.words for t in pos_terms)), multi=n >= 2)
        # מסמכים: הטוב ביותר קודם (הציון הגבוה, ואז מספר התוצאות)
        res.files = sorted(((f, file_ids[f], c) for f, c in per_file.items()),
                           key=lambda x: (-round(best_in_file[x[0]], 3), -x[2], x[1].lower()))
        rank = {f: i for i, (f, _, _) in enumerate(res.files)}
        if opts.sort == "document":
            hits.sort(key=lambda h: (rank[h.file_id], h.para_idx, h.span[0]))
        else:
            hits.sort(key=lambda h: (-h.score, rank[h.file_id], h.para_idx, h.span[0]))
        if len(hits) > opts.max_hits:
            hits = hits[: opts.max_hits]
            res.truncated = True
        res.hits = hits
        if not hits and n >= 2 and k == n and not (cancelled and cancelled()):
            # אין צירוף עם כל המילים – כמה תוצאות יש בלי אחת מהן? (מוצע למשתמש בלחיצה)
            sub = self.search(query, file_ids, replace(opts, min_terms=n - 1), cancelled)
            if sub.total:
                res.near_miss = (n - 1, sub.total)
        res.elapsed = time.perf_counter() - t0
        rep(0.97, "מכין את התצוגה")
        return res

    # ---------- שלב 5: קטע תצוגה ----------
    @staticmethod
    def _tokens(entry, idx):
        paras, _, tok_cache = entry
        toks = tok_cache.get(idx)
        if toks is None:
            toks = tok_cache[idx] = tokenize(paras[idx][0])
        return toks

    def materialize(self, hit: Hit, highlight=frozenset()) -> Hit:
        """בונה את קטע התצוגה. highlight – צורות נוספות לסמן במרקר (כל מילות החיפוש)."""
        if hit.ready:
            return hit
        entry = para_cache.get(self.db, hit.file_id)
        paras, numbers = entry[0], entry[1]
        para = paras[hit.para_idx]
        text, page, kind, note, breaks = para[:5]
        toks = self._tokens(entry, hit.para_idx)
        span = [p for p in hit.span if p < len(toks)] or [0]
        matched = set(span)
        first, last = span[0], span[-1]
        ctx = self.context_words

        snippet = []
        if last - first <= 2 * ctx:
            lo, hi = first - ctx, last + ctx
            if lo < 0:
                snippet += self._neighbor(entry, hit.para_idx, -1, -lo, highlight)
            snippet += self._render(text, toks, max(lo, 0), min(hi, len(toks) - 1), matched, highlight)
            if hi > len(toks) - 1:
                snippet += self._neighbor(entry, hit.para_idx, +1, hi - (len(toks) - 1), highlight)
        else:
            r = max(3, ctx // 2)
            windows = []
            for p in span:
                a, b = max(0, p - r), min(len(toks) - 1, p + r)
                if windows and a <= windows[-1][1] + 1:
                    windows[-1][1] = max(windows[-1][1], b)
                else:
                    windows.append([a, b])
            for k, (a, b) in enumerate(windows):
                if k:
                    snippet.append((" … ", SEG_GAP))
                snippet += self._render(text, toks, a, b, matched, highlight)

        start, end = toks[first][0], toks[last][1]
        hit.needle = text[start:end] if end - start <= 200 else text[start:toks[first][1]]
        hit.needle_offset = start
        hit.page = page + sum(1 for b in breaks if b <= start) if page else 0
        if len(para) > 6:  # PDF: שורה בעמוד
            li = bisect_right(para[6], start) - 1
            hit.line = para[5] + li
            if len(para) > 7:
                hit.y = para[7][li]
        hit.para_no, hit.kind, hit.note = numbers[hit.para_idx], kind, note
        hit.snippet = snippet
        hit.ready = True
        return hit

    @staticmethod
    def _render(text, toks, a, b, matched, highlight=frozenset()):
        if not toks:
            return [(text, SEG_TEXT)]
        segs = []
        if a > 0:
            segs.append(("… ", SEG_GAP))
        pos = toks[a][0]
        multi = getattr(highlight, "multi", False)
        for i in range(a, b + 1):
            s, e, norm = toks[i]
            if i in matched or (norm in highlight and not multi):
                if s > pos:
                    segs.append((text[pos:s], SEG_TEXT))
                segs.append((text[s:e], SEG_MATCH))
                pos = e
        end = len(text.rstrip()) if b == len(toks) - 1 else toks[b][1]
        if end > pos:
            segs.append((text[pos:end], SEG_TEXT))
        if b < len(toks) - 1:
            segs.append((" …", SEG_GAP))
        return segs

    def _neighbor(self, entry, pi, direction, need, highlight=frozenset()):
        """מילים מפסקאות סמוכות (מאותו סוג) להשלמת ההקשר."""
        paras = entry[0]
        kind, note = paras[pi][2], paras[pi][3]
        collected = []
        j = pi + direction
        while need > 0 and 0 <= j < len(paras) and abs(j - pi) <= 4:
            if paras[j][2] != kind or paras[j][3] != note:
                if kind != KIND_BODY or paras[j][2] != KIND_TEXTBOX:
                    break
                j += direction
                continue
            toks = self._tokens(entry, j)
            if toks:
                if direction < 0:
                    a = max(0, len(toks) - need)
                    collected = (self._render(paras[j][0], toks, a, len(toks) - 1, (), highlight)
                                 + [(" ¶ ", SEG_PARA)] + collected)
                else:
                    b = min(len(toks) - 1, need - 1)
                    collected += [(" ¶ ", SEG_PARA)] + self._render(paras[j][0], toks, 0, b, (), highlight)
                need -= len(toks)
            j += direction
        return collected

    # ---------- פתיחה במקום המדויק ----------
    def locate(self, hit: Hit):
        """מידע לאיתור התוצאה בוורד.

        מחזיר (מועמדים, יחס): מועמדים = [(טקסט, מספר_המופעים_שלו_לפני_התוצאה)],
        יחס = מיקום התוצאה כחלק מאורך הטקסט (0..1) – לגיבוי, אם הספירה לא מתאימה
        למה שוורד רואה (למשל שינויים במעקב או שדות).
        """
        self.materialize(hit)
        paras = para_cache.get(self.db, hit.file_id)[0]
        before = [p[0] for i, p in enumerate(paras)
                  if i < hit.para_idx and p[2] == hit.kind and (hit.kind == KIND_BODY or p[3] == hit.note)]
        story = [p[0] for p in paras if p[2] == hit.kind and (hit.kind == KIND_BODY or p[3] == hit.note)]
        cur = paras[hit.para_idx][0][:hit.needle_offset]
        out = []
        first_word = re.split(r"\s", hit.needle, maxsplit=1)[0]
        for needle in dict.fromkeys([hit.needle[:250], first_word]):
            if needle:
                k = sum(t.count(needle) for t in before) + cur.count(needle)
                out.append((needle, k))
        total = sum(len(t) + 1 for t in story) or 1
        ratio = (sum(len(t) + 1 for t in before) + len(cur)) / total
        return out, ratio

    def file_hits(self, result, hit):
        """כל התוצאות באותו מסמך, בסדר הופעתן – למעבר הקודמת/הבאה במציג."""
        hits = sorted((h for h in result.hits if h.file_id == hit.file_id),
                      key=lambda h: (h.para_idx, h.span[0]))
        return hits, next(i for i, h in enumerate(hits) if h is hit)
