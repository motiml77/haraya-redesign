"""חיפוש בתוך מסמך אחד שכבר פתוח (בשביל התוסף ל-Word).

התוסף שולח את פסקאות המסמך (טקסט + רמת כותרת), ומקבל תוצאות עם מיקום מדויק של המילים בתוך
כל פסקה. החיפוש עצמו הוא אותו מנוע של התוכנה: הפסקאות נשמרות במפת חיפוש זמנית בזיכרון
(SQLite ‎:memory:‎) ו-Searcher רץ עליה כרגיל – אותו נרמול, אותן צורות, אותו דירוג.

פרוטוקול (שורת JSON לכל בקשה ולכל תשובה, UTF-8, דרך stdin/stdout):
    {"cmd": "ping"}                                   → {"ok": true, "version": "..."}
    {"cmd": "index", "doc": "<מפתח>", "paras": [...]}  → {"ok": true, "paras": n, "headings": n, "elapsed": שניות}
        בונה מראש (ברקע, אחרי שהמסמך נטען) את מפת החיפוש של המסמך – גם המלאה וגם של הכותרות
    במקום paras אפשר לשלוח "text": "<טביעת האצבע של הטקסט>" ו-"levels": "0010020…" (ספרה לכל פסקה):
        מפת החיפוש המלאה נשמרת בדיסק לפי טביעת האצבע של הטקסט, כך שמסמך שכבר נפתח פעם לא נבנה מחדש.
        אם אין מפה כזו בדיסק → need_paras, והתוסף שולח את הפסקאות (עם "text", כדי שתישמר).
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
import os
import re
import sys
import time
import uuid
from collections import OrderedDict

from .extract import KIND_BODY
from .index import INDEX_VERSION, IndexDB, pack_paras, word_postings
from .normalize import tokenize
from .search import Searcher, options_from_choices, parse_query

DOC_PATH = "word://active-document"


CACHE_KEEP_FILES = 40                 # מפות חיפוש של מסמכים בדיסק: האחרונות שנעשה בהן שימוש
CACHE_KEEP_BYTES = 600 * 1024 * 1024


def _store_doc(db, rows):
    # דחיסה קלה: בדחיסה הרגילה (רמה 6) הדחיסה לבדה לקחה כמעט חצי מזמן בניית המפה של מסמך
    db.store({"path": DOC_PATH, "mtime": 0, "size": 0, "paras": pack_paras(rows, 1), "n_paras": len(rows),
              "words": word_postings(rows), "status": "ok", "message": ""})
    db.conn.commit()


class DocCache:
    """מפות החיפוש המלאות של מסמכים, בדיסק – לפי טביעת האצבע של הטקסט (ולפי גרסת המפה של המנוע)."""

    def __init__(self, folder):
        self.folder = folder

    def file(self, text_hash):
        name = re.sub(r"[^0-9A-Za-z]+", "-", str(text_hash or "")).strip("-")
        return os.path.join(self.folder, f"doc-v{INDEX_VERSION}-{name}.sqlite3") if name else None

    def open(self, text_hash):
        """(מפה לקריאה בלבד, טקסטים) אם המסמך כבר בדיסק; אחרת None."""
        path = self.file(text_hash)
        if not path or not os.path.exists(path):
            return None
        db = None
        try:
            db = IndexDB(path, ensure_schema=False)
            ids = db.file_ids([DOC_PATH])
            texts = [str(r[0]) for r in db.file_paras(next(iter(ids)))]
            os.utime(path, None)                     # "נעשה בו שימוש"
            return db, texts
        except Exception:                            # קובץ פגום או חלקי – בונים מחדש
            if db is not None:
                db.close()
            try:
                os.remove(path)
            except OSError:
                pass
            return None

    def build(self, text_hash, rows):
        """בונה את המפה לקובץ זמני ומחליף בבת אחת; מחזיר מפה פתוחה לקריאה, או None אם אי אפשר לשמור."""
        path = self.file(text_hash)
        if not path:
            return None
        tmp = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
        try:
            os.makedirs(self.folder, exist_ok=True)
            db = IndexDB(tmp)
            try:
                _store_doc(db, rows)
                db.conn.execute("PRAGMA journal_mode=DELETE")      # קובץ אחד, בלי קובצי ‎-wal
            finally:
                db.close()
            try:
                os.replace(tmp, path)
            except OSError:                          # תהליך אחר כבר שמר (ופתח) את אותו מסמך
                if not os.path.exists(path):
                    raise
            self.cleanup(keep=path)
            db = IndexDB(path, ensure_schema=False)
            row = db.conn.execute("SELECT n_paras FROM files WHERE path=?", (DOC_PATH,)).fetchone()
            if not row or row[0] != len(rows):       # קובץ של מסמך אחר שלא הצלחנו להחליף – עובדים בזיכרון
                db.close()
                return None
            return db
        except Exception:
            return None
        finally:
            for extra in (tmp, tmp + "-wal", tmp + "-shm"):
                try:
                    os.remove(extra)
                except OSError:
                    pass

    def cleanup(self, keep=None):
        try:
            files = []
            for name in os.listdir(self.folder):
                full = os.path.join(self.folder, name)
                if name.endswith(".tmp") and time.time() - os.path.getmtime(full) > 3600:
                    os.remove(full)
                elif name.startswith("doc-v") and name.endswith(".sqlite3"):
                    st = os.stat(full)
                    files.append((st.st_mtime, st.st_size, full))
            files.sort(reverse=True)
            total = 0
            for i, (_mtime, size, full) in enumerate(files):
                total += size
                current = f"doc-v{INDEX_VERSION}-" in os.path.basename(full)
                if full != keep and (not current or i >= CACHE_KEEP_FILES or total > CACHE_KEEP_BYTES):
                    try:
                        os.remove(full)              # קובץ שפתוח עכשיו (ב-Windows) פשוט נשאר
                    except OSError:
                        pass
        except OSError:
            pass


class DocIndex:
    """מפת חיפוש לפסקאות של מסמך אחד (או רק לכותרות שלו). מפת הכותרות תמיד בזיכרון (קטנה);
    המפה המלאה – בזיכרון, או בקובץ מטמון בדיסק אם ניתן (db: מפה שכבר נפתחה מהדיסק)."""

    def __init__(self, paras, only_headings=False, cache=None, text_hash=None, db=None):
        self.all_paras = paras
        self.levels = [int(p.get("h") or 0) for p in paras]
        self.texts = [str(p.get("t") or "") for p in paras]
        if only_headings:
            self.map = [i for i, lvl in enumerate(self.levels) if 0 < lvl < 10]
        else:
            self.map = list(range(len(paras)))
        self.on_disk = False
        if db is None and cache is not None and text_hash and not only_headings:
            db = cache.build(text_hash, [[t, 0, KIND_BODY, 0, []] for t in self.texts])
        if db is not None:
            self.db = db
            self.on_disk = True
        else:
            self.db = IndexDB(":memory:")
            _store_doc(self.db, [[self.texts[i], 0, KIND_BODY, 0, []] for i in self.map])
        # המטמונים של המנוע ממופתחים לפי נתיב המפה – כל מפה מקבלת נתיב משלה
        self.db.path = f":doc:{uuid.uuid4().hex}"
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

    def __init__(self, keep=8, cache_dir=None):
        self.keep = keep
        self.docs = OrderedDict()          # מפתח → {"paras": [...], False: DocIndex, True: DocIndex}
        self.cache = DocCache(cache_dir) if cache_dir else None

    def _store(self, key, entry):
        self.docs[key] = entry
        self.docs.move_to_end(key)
        while len(self.docs) > self.keep:
            _, old = self.docs.popitem(last=False)
            in_use = {id(e[k].db) for e in self.docs.values() for k in (False, True) if k in e}
            for k in (False, True):
                if k in old and id(old[k].db) not in in_use:      # מפה משותפת (relevel) נסגרת רק כשאין בה שימוש
                    old[k].close()

    @staticmethod
    def _levels(levels, n):
        """רמות הכותרות מהבקשה: מחרוזת ספרות או רשימה, באורך n; None אם לא נשלחו או לא תואמות."""
        if levels is None:
            return [0] * n
        try:
            out = [int(c) for c in levels]
        except (TypeError, ValueError):
            return None
        return out if len(out) == n else None

    def _from_disk(self, req):
        """מסמך שלא נשלחו הפסקאות שלו, אבל המפה שלו כבר בדיסק (מפתיחה קודמת)."""
        if self.cache is None or not req.get("text"):
            return None
        opened = self.cache.open(req.get("text"))
        if opened is None:
            return None
        db, texts = opened
        levels = self._levels(req.get("levels"), len(texts))
        if levels is None:
            db.close()
            return None
        paras = [{"t": t, "h": lvl} for t, lvl in zip(texts, levels)]
        return {"paras": paras, "text": req.get("text"), False: DocIndex(paras, db=db)}

    def _index(self, key, paras, only_headings, req=None):
        entry = self.docs.get(key)
        if entry is None:
            if paras is None:
                entry = self._from_disk(req) if req else None
                if entry is None:
                    return None
            else:
                entry = {"paras": paras, "text": (req or {}).get("text")}
            self._store(key, entry)
        self.docs.move_to_end(key)
        if only_headings not in entry:
            entry[only_headings] = DocIndex(entry["paras"], only_headings, self.cache, entry.get("text"))
        return entry[only_headings]

    def index(self, req: dict) -> dict:
        t0 = time.perf_counter()
        key = str(req.get("doc") or "")
        full = self._index(key, req.get("paras"), False, req)
        if full is None:
            return {"ok": False, "need_paras": True}
        self._index(key, None, True)
        headings = sum(1 for lvl in full.levels if 0 < lvl < 10)
        return {"ok": True, "paras": len(full.texts), "headings": headings, "cached": bool(full.on_disk),
                "elapsed": round(time.perf_counter() - t0, 3)}

    def relevel(self, req: dict) -> dict:
        t0 = time.perf_counter()
        src = self.docs.get(str(req.get("from") or ""))
        levels = req.get("levels")
        if src is None or not isinstance(levels, list) or len(levels) != len(src["paras"]):
            return {"ok": False, "need_paras": True}
        key = str(req.get("doc") or "")
        paras = [{"t": p.get("t") or "", "h": int(lvl or 0)} for p, lvl in zip(src["paras"], levels)]
        entry = {"paras": paras, "text": src.get("text")}
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
        idx = self._index(key, req.get("paras"), only_headings, req)
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
    from .paths import data_dir
    try:
        cache_dir = os.path.join(data_dir(), "cache", "docs")
    except OSError:
        cache_dir = None
    service = DocSearchService(cache_dir=cache_dir)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        if line == '{"cmd": "quit"}' or line == '{"cmd":"quit"}':
            break
        stdout.write(json.dumps(handle(service, line), ensure_ascii=False) + "\n")
        stdout.flush()
    return 0
