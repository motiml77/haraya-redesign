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
from dataclasses import dataclass, field

from .extract import KIND_BODY, KIND_ENDNOTE, KIND_FOOTNOTE, KIND_TEXTBOX
from .morphology import MatchOptions, normalize_query_word, term_regex
from .normalize import restore_finals, tokenize

MAX_VARIANTS = 50000

SEG_TEXT, SEG_MATCH, SEG_GAP, SEG_PARA = 0, 1, 2, 3


@dataclass
class SearchOptions:
    prefixes: bool = True
    inflections: bool = False
    ahevi: str = "none"          # none | vy | all
    max_gap: int = 0             # מספר המילים המרבי בין מילה למילה
    whole_paragraph: bool = False
    ordered: bool = True
    context_words: int = 20      # מילים לפני ואחרי
    max_hits: int = 100000

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
    # השדות הבאים מתמלאים ב-Searcher.materialize
    ready: bool = False
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
        if self.kind == KIND_FOOTNOTE:
            parts.append(f"הערת שוליים {self.note}")
        elif self.kind == KIND_ENDNOTE:
            parts.append(f"הערת סיום {self.note}")
        elif self.kind == KIND_TEXTBOX:
            parts.append("תיבת טקסט")
        else:
            parts.append(f"פסקה {self.para_no}")
        return " · ".join(parts)


@dataclass
class SearchResult:
    query: str
    hits: list = field(default_factory=list)
    total: int = 0
    files: list = field(default_factory=list)       # [(file_id, path, count)]
    forms: Counter = field(default_factory=Counter)
    terms: list = field(default_factory=list)
    elapsed: float = 0.0
    truncated: bool = False
    message: str = ""
    searched_files: int = 0


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
    """מטמון LRU לטקסט המפוענח של קבצים (נשמר בין חיפושים)."""

    def __init__(self, size=128):
        self.size = size
        self.data = OrderedDict()
        self.lock = threading.Lock()

    def get(self, db, fid):
        key = (db.path, fid)
        with self.lock:
            if key in self.data:
                self.data.move_to_end(key)
                return self.data[key]
        paras = db.file_paras(fid)
        body_no, numbers = 0, []
        for p in paras:
            if p[2] == KIND_BODY:
                body_no += 1
            numbers.append(body_no)
        val = (paras, numbers, {})
        with self.lock:
            self.data[key] = val
            while len(self.data) > self.size:
                self.data.popitem(last=False)
        return val

    def invalidate(self):
        with self.lock:
            self.data.clear()


para_cache = _ParaCache()


def _find_ordered(positions, gap):
    """התאמות לפי הסדר: כל מילה אחרי הקודמת, עם עד gap מילים ביניהן."""
    out, last_end = [], -1
    for p0 in positions[0]:
        if p0 <= last_end:
            continue
        span, cur = [p0], p0
        for plist in positions[1:]:
            j = bisect_right(plist, cur)
            if j == len(plist) or (gap is not None and plist[j] - cur - 1 > gap):
                span = None
                break
            cur = plist[j]
            span.append(cur)
        if span:
            out.append(span)
            last_end = cur
    return out


def _find_unordered(positions, gap):
    """התאמות בכל סדר: כל המילים בתוך חלון של n + (n-1)*gap מילים."""
    n = len(positions)
    limit = None if gap is None else n + (n - 1) * gap
    out, last_end = [], -1
    for p0 in positions[0]:
        if p0 <= last_end:
            continue
        chosen, used = [p0], {p0}
        for plist in positions[1:]:
            best = None
            j = bisect_left(plist, p0)
            for k in (j - 1, j, j + 1, j - 2, j + 2):
                if 0 <= k < len(plist) and plist[k] not in used and plist[k] > last_end:
                    if best is None or abs(plist[k] - p0) < abs(best - p0):
                        best = plist[k]
            if best is None:
                chosen = None
                break
            chosen.append(best)
            used.add(best)
        if not chosen:
            continue
        lo, hi = min(chosen), max(chosen)
        if limit is None or hi - lo + 1 <= limit:
            out.append(sorted(chosen))
            last_end = hi
    return out


class Searcher:
    def __init__(self, db, context_words=20):
        self.db = db
        self.context_words = context_words

    # ---------- שלב 1-4: מציאת ההתאמות ----------
    def _occurrences(self, ids, fileset, keys=None):
        """(קובץ, פסקה) → {מיקום: מילה}"""
        occ = {}
        for wid, fid, arr in self.db.postings(ids, fileset):
            word = self._id_word[wid]
            it = iter(arr)
            for para, pos in zip(it, it):
                key = (fid, para)
                if keys is not None and key not in keys:
                    continue
                d = occ.get(key)
                if d is None:
                    occ[key] = {pos: word}
                else:
                    d[pos] = word
        return occ

    def search(self, query, file_ids, opts: SearchOptions, cancelled=None) -> SearchResult:
        """file_ids: מילון מזהה_קובץ → נתיב (קבצי הסל)."""
        t0 = time.perf_counter()
        self.context_words = opts.context_words
        res = SearchResult(query=query, searched_files=len(file_ids))
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

        joined, vocab_ids = _vocab_cache.get(self.db)
        mopts = opts.match_options()
        for t in terms:
            rx = term_regex(t.alts, mopts)
            t.words = {m.group() for m in rx.finditer(joined)} if rx else set()
            if len(t.words) > MAX_VARIANTS:
                res.message = f"המילה '{t.text}' רחבה מדי ({len(t.words):,} צורות). נסו לצמצם."
                return res
        missing = [t.text for t in pos_terms if not t.words]
        if missing:
            res.message = "לא נמצאו במסמכים: " + ", ".join(missing)
            res.elapsed = time.perf_counter() - t0
            return res
        self._id_word = {vocab_ids[w]: w for t in terms for w in t.words}

        # מהמילה הנדירה לנפוצה: כל שלב מצמצם את הקבצים שנבדקים בשלב הבא
        fileset = set(file_ids)
        per_term, keys = [], None
        for t in sorted(pos_terms, key=lambda t: len(t.words)):
            occ = self._occurrences([vocab_ids[w] for w in t.words], fileset, keys)
            keys = set(occ) if keys is None else keys & set(occ)
            per_term.append((t, occ))
            if not keys:
                break
            fileset = {f for f, _ in keys}
            if cancelled and cancelled():
                res.message = "החיפוש בוטל."
                return res
        for t in neg_terms:
            if keys and t.words:
                occ = self._occurrences([vocab_ids[w] for w in t.words], fileset, keys)
                keys -= set(occ)
        per_term.sort(key=lambda x: pos_terms.index(x[0]))
        occs = [occ for _, occ in per_term]

        gap = None if opts.whole_paragraph else max(0, opts.max_gap)
        per_file = Counter()
        hits = []
        for key in keys or ():
            maps = [occ[key] for occ in occs]
            if len(maps) == 1:
                spans = [[p] for p in maps[0]]
            else:
                positions = [sorted(m) for m in maps]
                if opts.whole_paragraph:
                    spans = [sorted({p for plist in positions for p in plist})]
                elif opts.ordered:
                    spans = _find_ordered(positions, gap)
                else:
                    spans = _find_unordered(positions, gap)
            if not spans:
                continue
            merged = {}
            for m in maps:
                merged.update(m)
            fid, para = key
            per_file[fid] += len(spans)
            for span in spans:
                hits.append(Hit(fid, file_ids[fid], para, tuple(span),
                                tuple(merged[p] for p in span)))

        res.total = len(hits)
        for h in hits:
            res.forms.update(restore_finals(w) for w in h.words)
        res.files = sorted(((f, file_ids[f], c) for f, c in per_file.items()),
                           key=lambda x: (-x[2], x[1].lower()))
        rank = {f: i for i, (f, _, _) in enumerate(res.files)}
        hits.sort(key=lambda h: (rank[h.file_id], h.para_idx, h.span[0]))
        if len(hits) > opts.max_hits:
            hits = hits[: opts.max_hits]
            res.truncated = True
        res.hits = hits
        res.elapsed = time.perf_counter() - t0
        return res

    # ---------- שלב 5: קטע תצוגה ----------
    @staticmethod
    def _tokens(entry, idx):
        paras, _, tok_cache = entry
        toks = tok_cache.get(idx)
        if toks is None:
            toks = tok_cache[idx] = tokenize(paras[idx][0])
        return toks

    def materialize(self, hit: Hit) -> Hit:
        if hit.ready:
            return hit
        entry = para_cache.get(self.db, hit.file_id)
        paras, numbers = entry[0], entry[1]
        text, page, kind, note, breaks = paras[hit.para_idx]
        toks = self._tokens(entry, hit.para_idx)
        span = [p for p in hit.span if p < len(toks)] or [0]
        matched = set(span)
        first, last = span[0], span[-1]
        ctx = self.context_words

        snippet = []
        if last - first <= 2 * ctx:
            lo, hi = first - ctx, last + ctx
            if lo < 0:
                snippet += self._neighbor(entry, hit.para_idx, -1, -lo)
            snippet += self._render(text, toks, max(lo, 0), min(hi, len(toks) - 1), matched)
            if hi > len(toks) - 1:
                snippet += self._neighbor(entry, hit.para_idx, +1, hi - (len(toks) - 1))
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
                snippet += self._render(text, toks, a, b, matched)

        start, end = toks[first][0], toks[last][1]
        hit.needle = text[start:end] if end - start <= 200 else text[start:toks[first][1]]
        hit.needle_offset = start
        hit.page = page + sum(1 for b in breaks if b <= start) if page else 0
        hit.para_no, hit.kind, hit.note = numbers[hit.para_idx], kind, note
        hit.snippet = snippet
        hit.ready = True
        return hit

    @staticmethod
    def _render(text, toks, a, b, matched):
        if not toks:
            return [(text, SEG_TEXT)]
        segs = []
        if a > 0:
            segs.append(("… ", SEG_GAP))
        pos = toks[a][0]
        for i in range(a, b + 1):
            s, e, _ = toks[i]
            if i in matched:
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

    def _neighbor(self, entry, pi, direction, need):
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
                    collected = (self._render(paras[j][0], toks, a, len(toks) - 1, ())
                                 + [(" ¶ ", SEG_PARA)] + collected)
                else:
                    b = min(len(toks) - 1, need - 1)
                    collected += [(" ¶ ", SEG_PARA)] + self._render(paras[j][0], toks, 0, b, ())
                need -= len(toks)
            j += direction
        return collected

    # ---------- פתיחה במקום המדויק ----------
    def locate(self, hit: Hit):
        """מחזיר מועמדים לאיתור בוורד: [(טקסט, מספר_המופעים_שלפניו)]."""
        self.materialize(hit)
        paras = para_cache.get(self.db, hit.file_id)[0]
        before = [p[0] for i, p in enumerate(paras)
                  if i < hit.para_idx and p[2] == hit.kind and (hit.kind == KIND_BODY or p[3] == hit.note)]
        cur = paras[hit.para_idx][0][:hit.needle_offset]
        out = []
        first_word = re.split(r"\s", hit.needle, maxsplit=1)[0]
        for needle in dict.fromkeys([hit.needle[:250], first_word]):
            if needle:
                k = sum(t.count(needle) for t in before) + cur.count(needle)
                out.append((needle, k))
        return out
