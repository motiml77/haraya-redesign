"""חיפוש בתוך מסמך אחד שכבר פתוח (בשביל התוסף ל-Word).

התוסף שולח את פסקאות המסמך (טקסט + רמת כותרת), ומקבל תוצאות עם מיקום מדויק של המילים בתוך
כל פסקה. החיפוש עצמו הוא אותו מנוע של התוכנה: הפסקאות נשמרות במפת חיפוש זמנית בזיכרון
(SQLite ‎:memory:‎) ו-Searcher רץ עליה כרגיל – אותו נרמול, אותן צורות, אותו דירוג.

פרוטוקול (שורת JSON לכל בקשה ולכל תשובה, UTF-8, דרך stdin/stdout):
    {"cmd": "ping"}                                   → {"ok": true, "version": "..."}
    {"cmd": "index", "doc": "<מפתח>", "paras": [...]}  → {"ok": true, "paras": n, "headings": n, "elapsed": שניות}
        בונה מראש (ברקע, אחרי שהמסמך נטען) את מפת החיפוש של המסמך – גם המלאה וגם של הכותרות
    {"cmd": "relevel", "from": "<מפתח קודם>", "doc": "<מפתח חדש>", "levels": [0..9, ...]}
        אותו טקסט עם רמות כותרות חדשות (אחרי שהתוסף קרא את הכותרות): משתמשים שוב במפת החיפוש
        המלאה שכבר נבנתה, ובונים רק את מפת הכותרות → כמו index; need_paras אם המפתח הקודם לא במטמון
    {"cmd": "search", "doc": "<מפתח>", "paras": [{"t": "...", "h": 0..9}, ...],   (paras – רק כשהמסמך השתנה)
     "query": "...", "options": {"forms": "prefixes", "spelling": "none", "distance": "adjacent",
     "near": 3, "ordered": true, "required": 0}, "headings_only": false, "limit": 500}
        → {"ok": true, "total": N, "shown": n, "hits": [...], "forms": [[צורה, מספר], ...],
           "phrase": bool, "elapsed": שניות, "message": "", "headings": מספר הכותרות במסמך}
        → {"ok": false, "need_paras": true}            כשהמסמך לא במטמון ולא נשלחו פסקאות
    hit = {"para": אינדקס הפסקה במסמך, "ranges": [[התחלה, סוף], ...] (תווים בתוך הפסקה),
           "snippet": [[טקסט, סוג], ...], "heading": "הכותרת שמעל", "path": ["כותרת 1", "כותרת 2", ...],
           "score": 0..1, "exact": bool, "covered": כמה ממילות החיפוש נמצאו}
    path – שרשרת הכותרות שהפסקה נמצאת תחתיהן, מהרמה העליונה ועד הקרובה (לכותרת עצמה: הכותרות שמעליה)
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from collections import OrderedDict

from .extract import KIND_BODY
from .index import IndexDB, pack_paras, word_postings
from .normalize import tokenize
from .search import Searcher, options_from_choices, parse_query

DOC_PATH = "word://active-document"


class DocIndex:
    """מפת חיפוש בזיכרון לפסקאות של מסמך אחד (או רק לכותרות שלו)."""

    def __init__(self, paras, only_headings=False):
        self.all_paras = paras
        self.levels = [int(p.get("h") or 0) for p in paras]
        self.texts = [str(p.get("t") or "") for p in paras]
        if only_headings:
            self.map = [i for i, lvl in enumerate(self.levels) if 0 < lvl < 10]
        else:
            self.map = list(range(len(paras)))
        rows = [[self.texts[i], 0, KIND_BODY, 0, []] for i in self.map]
        self.db = IndexDB(":memory:")
        # המטמונים של המנוע ממופתחים לפי נתיב המפה – כל מפה זמנית מקבלת נתיב משלה
        self.db.path = f":memory:{uuid.uuid4().hex}"
        self.db.store({"path": DOC_PATH, "mtime": 0, "size": 0, "paras": pack_paras(rows), "n_paras": len(rows),
                       "words": word_postings(rows), "status": "ok", "message": ""})
        self.db.conn.commit()
        self.file_ids = self.db.file_ids([DOC_PATH])          # {מזהה: נתיב} – כמו שהמנוע מצפה
        self.fid = next(iter(self.file_ids), None)
        self.searcher = Searcher(self.db, context_words=12)       # החלונית ב-Word צרה
        self.searcher.neighbors = False      # כל תוצאה – רק מהפסקה שלה (בלי ¶ ומילים מפסקאות סמוכות)
        self.paths = self._heading_paths()

    def _heading_paths(self):
        """לכל פסקה: שרשרת הכותרות שהיא נמצאת תחתיהן (מעבר אחד על המסמך; שרשראות זהות משותפות)."""
        paths, stack, current = [], [], ()
        for text, level in zip(self.texts, self.levels):
            text = " ".join(text.split())
            if 0 < level < 10 and text:
                while stack and stack[-1][0] >= level:
                    stack.pop()
                paths.append(tuple(t for _, t in stack))       # לכותרת עצמה: רק מה שמעליה
                stack.append((level, text))
                current = tuple(t for _, t in stack)
            else:
                paths.append(current)
        return paths

    def with_levels(self, paras):
        """אותה מפת חיפוש (אותו טקסט) עם רמות כותרות אחרות – בלי לבנות את המפה מחדש."""
        clone = object.__new__(DocIndex)
        clone.__dict__.update(self.__dict__)
        clone.all_paras = paras
        clone.levels = [int(p.get("h") or 0) for p in paras]
        clone.paths = clone._heading_paths()
        return clone

    def heading_above(self, idx: int) -> str:
        """הכותרת הקרובה ביותר מעל הפסקה (לא כולל הפסקה עצמה אם היא כותרת)."""
        path = self.paths[idx] if 0 <= idx < len(self.paths) else ()
        return path[-1] if path else ""

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass


class DocSearchService:
    """מטמון של כמה מסמכים אחרונים (מפתח = מזהה המסמך + גרסת הטקסט), וחיפוש בהם."""

    def __init__(self, keep=8):
        self.keep = keep
        self.docs = OrderedDict()          # מפתח → {"paras": [...], False: DocIndex, True: DocIndex}

    def _store(self, key, entry):
        self.docs[key] = entry
        self.docs.move_to_end(key)
        while len(self.docs) > self.keep:
            _, old = self.docs.popitem(last=False)
            in_use = {id(e[k].db) for e in self.docs.values() for k in (False, True) if k in e}
            for k in (False, True):
                if k in old and id(old[k].db) not in in_use:      # מפה משותפת (relevel) נסגרת רק כשאין בה שימוש
                    old[k].close()

    def _index(self, key, paras, only_headings):
        entry = self.docs.get(key)
        if entry is None:
            if paras is None:
                return None
            entry = {"paras": paras}
            self._store(key, entry)
        self.docs.move_to_end(key)
        if only_headings not in entry:
            entry[only_headings] = DocIndex(entry["paras"], only_headings)
        return entry[only_headings]

    def index(self, req: dict) -> dict:
        t0 = time.perf_counter()
        key = str(req.get("doc") or "")
        full = self._index(key, req.get("paras"), False)
        if full is None:
            return {"ok": False, "need_paras": True}
        self._index(key, None, True)
        headings = sum(1 for lvl in full.levels if 0 < lvl < 10)
        return {"ok": True, "paras": len(full.texts), "headings": headings,
                "elapsed": round(time.perf_counter() - t0, 3)}

    def relevel(self, req: dict) -> dict:
        t0 = time.perf_counter()
        src = self.docs.get(str(req.get("from") or ""))
        levels = req.get("levels")
        if src is None or not isinstance(levels, list) or len(levels) != len(src["paras"]):
            return {"ok": False, "need_paras": True}
        key = str(req.get("doc") or "")
        paras = [{"t": p.get("t") or "", "h": int(lvl or 0)} for p, lvl in zip(src["paras"], levels)]
        entry = {"paras": paras}
        if False in src:
            entry[False] = src[False].with_levels(paras)
        self._store(key, entry)
        full = self._index(key, None, False)
        self._index(key, None, True)
        headings = sum(1 for lvl in full.levels if 0 < lvl < 10)
        return {"ok": True, "paras": len(paras), "headings": headings, "elapsed": round(time.perf_counter() - t0, 3)}

    def has(self, key: str) -> bool:
        return key in self.docs

    def search(self, req: dict) -> dict:
        t0 = time.perf_counter()
        key = str(req.get("doc") or "")
        only_headings = bool(req.get("headings_only"))
        idx = self._index(key, req.get("paras"), only_headings)
        if idx is None:
            return {"ok": False, "need_paras": True}
        query = str(req.get("query") or "").strip()
        headings = sum(1 for lvl in idx.levels if 0 < lvl < 10)
        if not query:
            return {"ok": True, "total": 0, "shown": 0, "hits": [], "forms": [], "phrase": False,
                    "elapsed": 0.0, "message": "", "headings": headings}
        o = req.get("options") or {}
        n_terms = sum(1 for t in parse_query(query) if not t.negate)
        opts = options_from_choices(o.get("forms", "prefixes"), o.get("spelling", "none"),
                                    o.get("distance", "adjacent"), o.get("near", 3), o.get("ordered", True),
                                    int(o.get("required", 0) or 0), n_terms)
        if idx.fid is None:                      # אין טקסט (למשל: אין כותרות במסמך)
            return {"ok": True, "total": 0, "shown": 0, "hits": [], "forms": [], "phrase": False,
                    "elapsed": 0.0, "message": "", "headings": headings}
        res = idx.searcher.search(query, idx.file_ids, opts)
        limit = max(1, int(req.get("limit") or 500))
        # בתוך מסמך אחד – לפי סדר הופעה במסמך כמו בחיפוש של Word, אבל ההתאמות המלאות קודם
        hits = sorted(res.hits, key=lambda h: (-h.covered, h.para_idx, h.span[0] if h.span else 0))
        out = []
        for h in hits[:limit]:
            idx.searcher.materialize(h, res.highlight)
            text = idx.texts[idx.map[h.para_idx]]
            toks = tokenize(text)
            ranges = [[toks[p][0], toks[p][1]] for p in sorted(h.span) if p < len(toks)]
            para = idx.map[h.para_idx]
            if only_headings:                   # הכותרת עצמה בלבד, בלי כותרות שכנות כ"הקשר"
                snippet, last = [], 0
                for a, b in ranges:
                    if a > last:
                        snippet.append([text[last:a], 0])
                    snippet.append([text[a:b], 1])
                    last = b
                if last < len(text):
                    snippet.append([text[last:], 0])
            else:
                snippet = [[t, k] for t, k in h.snippet]
            out.append({
                "para": para,
                "ranges": ranges,
                "snippet": snippet,
                "heading": idx.heading_above(para) if not only_headings else "",
                "path": list(idx.paths[para]),
                "level": idx.levels[para],
                "score": round(float(h.score), 3),
                "exact": bool(h.exact),
                "covered": int(h.covered),
            })
        return {"ok": True, "total": res.total, "shown": len(out), "hits": out,
                "forms": [[f, c] for f, c in res.forms.most_common(30)], "phrase": bool(res.phrase),
                "n_terms": res.n_terms, "elapsed": round(time.perf_counter() - t0, 3),
                "message": res.message or "", "headings": headings}


def handle(service: DocSearchService, line: str) -> dict:
    try:
        req = json.loads(line)
    except ValueError as e:
        return {"ok": False, "error": f"bad json: {e}"}
    cmd = req.get("cmd")
    try:
        if cmd == "ping":
            from . import __version__
            return {"ok": True, "version": __version__}
        if cmd == "search":
            return service.search(req)
        if cmd == "index":
            return service.index(req)
        if cmd == "relevel":
            return service.relevel(req)
        return {"ok": False, "error": f"unknown command: {cmd}"}
    except Exception as e:  # התוסף מציג את השגיאה ולא נתקע
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def serve(stdin=None, stdout=None) -> int:
    """לולאת השירות: שורה נכנסת → שורה יוצאת, עד שהצינור נסגר (Word נסגר)."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for s in (stdin, stdout):
        try:
            s.reconfigure(encoding="utf-8", newline="\n")
        except Exception:
            pass
    service = DocSearchService()
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        if line == '{"cmd": "quit"}' or line == '{"cmd":"quit"}':
            break
        stdout.write(json.dumps(handle(service, line), ensure_ascii=False) + "\n")
        stdout.flush()
    return 0
