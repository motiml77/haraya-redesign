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
    {"cmd": "patch", "doc": "<מפתח>", "text": "<טביעת אצבע>", "base": "<טביעת האצבע של גרסה קודמת>",
     "ops": [[התחלה, כמה], "טקסט של פסקה חדשה", ...], "levels": "0010…"}
        אחרי עריכה: רק הפסקאות שהשתנו נשלחות. [התחלה, כמה] = פסקאות רצופות מהגרסה הקודמת (שבזיכרון או
        בדיסק), ומחרוזת = פסקה חדשה. מפת החיפוש של המסמך לא נבנית מחדש: מחפשים במפה של הגרסה המלאה
        האחרונה (בלי הפסקאות שנמחקו או שונו) ובמפה קטנה של הפסקאות החדשות בלבד (PatchedIndex) – העלות
        היא לפי גודל השינוי ולא לפי גודל המסמך. רק כשהשינויים מצטברים להרבה – בונים מפה מלאה חדשה.
        → כמו index; need_paras אם הגרסה הקודמת לא בזיכרון ולא בדיסק
    {"cmd": "persist", "doc": "<מפתח>"}     שמירת המפה של הגרסה הזו בדיסק (התוסף שולח כשמסמך נסגר)
    {"cmd": "docx_headings", "path": "<קובץ>"}
        → {"ok": true, "headings": [[טקסט, רמה, מקום משוער], ...], "paras": n} – הכותרות מתוך קובץ ה-docx
    "progress": true בבקשה → לפני התשובה נשלחות שורות {"progress": 0..1} (בבניית מפה)
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
import sqlite3
import sys
import time
import uuid
import zlib
from array import array
from collections import Counter, OrderedDict

from .extract import KIND_BODY
from .index import INDEX_VERSION, IndexDB, pack_paras
from .normalize import normalize_text, restore_finals, tokenize
from .search import Searcher, options_from_choices, parse_query

DOC_PATH = "word://active-document"


CACHE_MAX_AGE = 3 * 24 * 3600        # מפה של מסמך שלא נפתח 3 ימים נמחקת (ונבנית שוב כשהוא נפתח)
CACHE_KEEP_BYTES = 2 * 1024 ** 3      # ובכל מקרה – לא יותר מזה בסך הכול (הישנות ביותר נמחקות קודם)
PATCH_LIMIT = 400                     # עד כמה פסקאות שהשתנו מחפשים במפה נפרדת (או 4% מהמסמך, הגדול מביניהם)
NORM_TABLE = "doc_norms"
PROGRESS_INTERVAL = 0.25              # שניות בין שורות התקדמות              # המילים המנורמלות של כל פסקה (לעדכון חלקי אחרי עריכה)


def normalize_paras(texts, reuse=None, progress=None):
    """המילים המנורמלות של כל פסקה, מחוברות ב-"\n" (כמו ב-word_postings). reuse: אינדקס → מחרוזת מוכנה."""
    out = []
    n = len(texts)
    for i, t in enumerate(texts):
        r = reuse.get(i) if reuse else None
        out.append(r if r is not None else "\n".join(normalize_text(t)))
        if progress is not None and i % 2000 == 0:
            progress(i / max(1, n))
    return out


def postings_from_norms(norms):
    """כמו word_postings – מהמילים המנורמלות שכבר חושבו."""
    words = {}
    for i, joined in enumerate(norms):
        if not joined:
            continue
        for pos, w in enumerate(joined.split("\n")):
            lst = words.get(w)
            if lst is None:
                words[w] = [i, pos]
            else:
                lst.append(i)
                lst.append(pos)
    return {w: array("I", lst).tobytes() for w, lst in words.items()}


def _store_doc(db, texts, norms=None):
    """בונה את מפת החיפוש של המסמך ב-db (וגם שומרת בו את המילים המנורמלות)."""
    if norms is None:
        norms = normalize_paras(texts)
    rows = [[t, 0, KIND_BODY, 0, []] for t in texts]
    # דחיסה קלה: בדחיסה הרגילה (רמה 6) הדחיסה לבדה לקחה כמעט חצי מזמן בניית המפה של מסמך
    db.store({"path": DOC_PATH, "mtime": 0, "size": 0, "paras": pack_paras(rows, 1), "n_paras": len(rows),
              "words": postings_from_norms(norms), "status": "ok", "message": ""})
    db.conn.execute(f"CREATE TABLE IF NOT EXISTS {NORM_TABLE}(data BLOB)")
    db.conn.execute(f"DELETE FROM {NORM_TABLE}")
    db.conn.execute(f"INSERT INTO {NORM_TABLE} VALUES(?)", (zlib.compress("\x1e".join(norms).encode("utf-8"), 1),))
    db.conn.commit()


def load_norms(db, count):
    """המילים המנורמלות שנשמרו במפה, או None (מפה ישנה בלי הטבלה, או מספר פסקאות לא תואם)."""
    try:
        row = db.conn.execute(f"SELECT data FROM {NORM_TABLE}").fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    norms = zlib.decompress(row[0]).decode("utf-8").split("\x1e") if count else []
    return norms if len(norms) == count else None


class DocCache:
    """מפות החיפוש המלאות של מסמכים, בדיסק – לפי טביעת האצבע של הטקסט (ולפי גרסת המפה של המנוע)."""

    def __init__(self, folder):
        self.folder = folder

    def file(self, text_hash):
        name = re.sub(r"[^0-9A-Za-z]+", "-", str(text_hash or "")).strip("-")
        return os.path.join(self.folder, f"doc-v{INDEX_VERSION}-{name}.sqlite3") if name else None

    def has(self, text_hash):
        path = self.file(text_hash)
        return bool(path) and os.path.exists(path)

    def touch(self, text_hash):
        try:
            os.utime(self.file(text_hash), None)
        except (OSError, TypeError):
            pass

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
            os.utime(path, None)                     # "נעשה בו שימוש" – לא יימחק בשלושת הימים הקרובים
            return db, texts
        except Exception:                            # קובץ פגום או חלקי – בונים מחדש
            if db is not None:
                db.close()
            try:
                os.remove(path)
            except OSError:
                pass
            return None

    def _finish(self, tmp, path, count):
        """קובץ זמני מוכן → מחליף בבת אחת ופותח לקריאה (None אם לא הצליח)."""
        try:
            os.replace(tmp, path)
        except OSError:                              # תהליך אחר כבר שמר (ופתח) את אותו מסמך
            if not os.path.exists(path):
                raise
        self.cleanup(keep=path)
        db = IndexDB(path, ensure_schema=False)
        row = db.conn.execute("SELECT n_paras FROM files WHERE path=?", (DOC_PATH,)).fetchone()
        if not row or row[0] != count:              # קובץ של מסמך אחר שלא הצלחנו להחליף – עובדים בזיכרון
            db.close()
            return None
        return db

    def _cleanup_tmp(self, tmp):
        for extra in (tmp, tmp + "-wal", tmp + "-shm", tmp + "-journal"):
            try:
                os.remove(extra)
            except OSError:
                pass

    def build(self, text_hash, texts, norms=None):
        """בונה את המפה לקובץ זמני ומחליף בבת אחת; מחזיר מפה פתוחה לקריאה, או None אם אי אפשר לשמור."""
        path = self.file(text_hash)
        if not path:
            return None
        tmp = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
        try:
            os.makedirs(self.folder, exist_ok=True)
            db = IndexDB(tmp)
            try:
                _store_doc(db, texts, norms)
                db.conn.execute("PRAGMA journal_mode=DELETE")      # קובץ אחד, בלי קובצי ‎-wal
            finally:
                db.close()
            return self._finish(tmp, path, len(texts))
        except Exception:
            return None
        finally:
            self._cleanup_tmp(tmp)

    def save(self, text_hash, mem_db, count):
        """שומר בדיסק מפה שנבנתה בזיכרון (אחרי עריכה). True אם נשמרה (או שכבר הייתה)."""
        path = self.file(text_hash)
        if not path:
            return False
        if os.path.exists(path):
            self.touch(text_hash)
            return True
        tmp = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
        try:
            os.makedirs(self.folder, exist_ok=True)
            dest = sqlite3.connect(tmp)
            try:
                mem_db.conn.backup(dest)
                dest.execute("PRAGMA journal_mode=DELETE")
            finally:
                dest.close()
            db = self._finish(tmp, path, count)
            if db is not None:
                db.close()
            return db is not None
        except Exception:
            return False
        finally:
            self._cleanup_tmp(tmp)

    def cleanup(self, keep=None, now=None):
        """מוחק מפות של מסמכים שלא נפתחו 3 ימים, מפות מגרסה ישנה של המנוע, וקבצים זמניים שנשארו."""
        now = time.time() if now is None else now
        try:
            files = []
            for name in os.listdir(self.folder):
                full = os.path.join(self.folder, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                if name.endswith(".tmp"):
                    if now - st.st_mtime > 3600:
                        os.remove(full)
                elif name.startswith("doc-v") and name.endswith(".sqlite3"):
                    files.append((st.st_mtime, st.st_size, full))
            files.sort(reverse=True)
            total = 0
            for mtime, size, full in files:
                total += size
                current = f"doc-v{INDEX_VERSION}-" in os.path.basename(full)
                if full != keep and (not current or now - mtime > CACHE_MAX_AGE or total > CACHE_KEEP_BYTES):
                    try:
                        os.remove(full)              # קובץ שפתוח עכשיו (ב-Windows) פשוט נשאר
                    except OSError:
                        pass
        except OSError:
            pass


class DocIndex:
    """מפת חיפוש לפסקאות של מסמך אחד (או רק לכותרות שלו). מפת הכותרות תמיד בזיכרון (קטנה);
    המפה המלאה – בזיכרון, או בקובץ מטמון בדיסק (db: מפה שכבר נבנתה, בזיכרון או בדיסק)."""

    def __init__(self, paras, only_headings=False, db=None, norms=None, on_disk=False):
        self.all_paras = paras
        self.levels = [int(p.get("h") or 0) for p in paras]
        self.texts = [str(p.get("t") or "") for p in paras]
        if only_headings:
            self.map = [i for i, lvl in enumerate(self.levels) if 0 < lvl < 10]
        else:
            self.map = list(range(len(paras)))
        self.on_disk = on_disk
        if db is not None:
            self.db = db
        else:
            self.db = IndexDB(":memory:")
            texts = [self.texts[i] for i in self.map]
            _store_doc(self.db, texts, [norms[i] for i in self.map] if norms is not None else None)
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
            if 0 < level < 10:
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

    def dbs(self):
        return [self.db]

    def run(self, query, opts):
        """→ ([(פסקה במסמך, תוצאה, מנוע, הדגשה)], צורות, ביטוי?, מספר מילים, הודעה)."""
        if self.fid is None:
            return [], Counter(), False, 0, ""
        res = self.searcher.search(query, self.file_ids, opts)
        found = [(self.map[h.para_idx], h, self.searcher, res.highlight) for h in res.hits]
        return found, res.forms, bool(res.phrase), res.n_terms, res.message or ""

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass


class PatchedIndex:
    """גרסה ערוכה של מסמך, בלי לבנות את מפת החיפוש מחדש.

    מחפשים בשתי מפות: המפה של הגרסה המלאה האחרונה (base) – ממנה נלקחות רק תוצאות בפסקאות שעדיין
    קיימות, עם המספר החדש שלהן; ומפה קטנה (delta) של הפסקאות שנוספו או שונו מאז. כל פסקה נבדקת בנפרד,
    ולכן התוצאה זהה לחיפוש במפה מלאה של הגרסה החדשה. origin[i] = מספר הפסקה בגרסת הבסיס, או ‎-1.
    """
    on_disk = False
    fid = 1

    def __init__(self, paras, base, origin, norms):
        self.all_paras = paras
        self.levels = [int(p.get("h") or 0) for p in paras]
        self.texts = [str(p.get("t") or "") for p in paras]
        self.base = base
        self.origin = origin
        self.to_new = [-1] * len(base.texts)
        fresh = []
        for i, o in enumerate(origin):
            if o >= 0:
                self.to_new[o] = i
            else:
                fresh.append(i)
        self.fresh = fresh
        self.delta = None
        if fresh:
            self.delta = DocIndex([paras[i] for i in fresh], norms=[norms[i] for i in fresh] if norms is not None else None)
        self.paths = DocIndex._heading_paths(self)

    def with_levels(self, paras):
        clone = object.__new__(PatchedIndex)
        clone.__dict__.update(self.__dict__)
        clone.all_paras = paras
        clone.levels = [int(p.get("h") or 0) for p in paras]
        clone.paths = DocIndex._heading_paths(clone)
        return clone

    heading_above = DocIndex.heading_above

    def dbs(self):
        return [self.base.db] + ([self.delta.db] if self.delta is not None else [])

    def run(self, query, opts):
        found, forms, phrase, n_terms, messages = [], Counter(), False, 0, []
        for part, mapping in ((self.base, self.to_new), (self.delta, self.fresh)):
            if part is None or part.fid is None:
                continue
            res = part.searcher.search(query, part.file_ids, opts)
            phrase = phrase or bool(res.phrase)
            n_terms = max(n_terms, res.n_terms)
            messages.append(res.message or "")
            for h in res.hits:
                para = mapping[part.map[h.para_idx]]
                if para < 0:
                    continue                    # הפסקה נמחקה או שונתה מאז גרסת הבסיס
                found.append((para, h, part.searcher, res.highlight))
                for w in h.words:
                    forms[restore_finals(w)] += 1
        message = "" if found else next((m for m in messages if m), "")
        return found, forms, phrase, n_terms, message

    def close(self):
        for db in self.dbs():
            try:
                db.close()
            except Exception:
                pass


class DocSearchService:
    """מטמון של כמה מסמכים אחרונים (מפתח = מזהה המסמך + גרסת הטקסט), וחיפוש בהם."""

    def __init__(self, keep=8, cache_dir=None):
        self.keep = keep
        # מפתח → {"paras": [...], "text": טביעת אצבע, "norms": [...] או None, False: DocIndex, True: DocIndex}
        self.docs = OrderedDict()
        self.cache = DocCache(cache_dir) if cache_dir else None
        self.report = None                 # התקדמות (0..1) של הבקשה הנוכחית, אם התוסף ביקש

    def _progress(self, frac):
        if self.report is not None:
            self.report(frac)

    def _close_unused(self, old):
        in_use = {id(db) for e in self.docs.values() for k in (False, True) if k in e for db in e[k].dbs()}
        for k in (False, True):
            if k in old:
                for db in old[k].dbs():
                    if id(db) not in in_use:          # מפה משותפת (relevel / בסיס של גרסה ערוכה) נסגרת רק כשאין בה שימוש
                        try:
                            db.close()
                        except Exception:
                            pass

    def _store(self, key, entry):
        self.docs[key] = entry
        self.docs.move_to_end(key)
        while len(self.docs) > self.keep:
            _, old = self.docs.popitem(last=False)
            self._close_unused(old)

    def _drop_text(self, text, keep_key):
        """אחרי עדכון חלקי: הגרסאות הקודמות של המסמך לא נחוצות יותר – משחררים את הזיכרון שלהן."""
        for key in [k for k, e in self.docs.items() if k != keep_key and e.get("text") == text]:
            self._close_unused(self.docs.pop(key))

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

    def _in_memory(self, text):
        """רשומה בזיכרון עם הטקסט הזה (כל גרסה של רמות הכותרות)."""
        if not text:
            return None
        for e in reversed(self.docs.values()):
            if e.get("text") == text and False in e:
                return e
        return None

    def _with_levels(self, src, levels):
        paras = [{"t": p.get("t") or "", "h": int(lvl or 0)} for p, lvl in zip(src["paras"], levels)]
        entry = {"paras": paras, "text": src.get("text"), "norms": src.get("norms")}
        entry[False] = src[False].with_levels(paras)
        return entry

    def _from_disk(self, text, levels):
        """מסמך שלא נשלחו הפסקאות שלו, אבל המפה שלו כבר בדיסק (מפתיחה קודמת)."""
        if self.cache is None or not text:
            return None
        opened = self.cache.open(text)
        if opened is None:
            return None
        db, texts = opened
        levels = self._levels(levels, len(texts))
        if levels is None:
            db.close()
            return None
        paras = [{"t": t, "h": lvl} for t, lvl in zip(texts, levels)]
        return {"paras": paras, "text": text, "norms": None, False: DocIndex(paras, db=db, on_disk=True)}

    def _known(self, text, levels):
        """הטקסט הזה כבר מוכר – בזיכרון (גרסה עם רמות אחרות) או בדיסק."""
        src = self._in_memory(text)
        if src is not None:
            levels = self._levels(levels, len(src["paras"]))
            if levels is not None:
                return self._with_levels(src, levels)
        return self._from_disk(text, levels)

    def _build(self, paras, text):
        """בונה מפה מלאה מפסקאות שנשלחו – בדיסק אם אפשר, אחרת בזיכרון."""
        texts = [str(p.get("t") or "") for p in paras]
        norms = normalize_paras(texts, progress=lambda f: self._progress(0.85 * f))
        db = self.cache.build(text, texts, norms) if self.cache is not None and text else None
        self._progress(0.97)
        entry = {"paras": paras, "text": text, "norms": norms}
        entry[False] = DocIndex(paras, db=db, norms=norms, on_disk=db is not None)
        return entry

    def _index(self, key, paras, only_headings, req=None):
        entry = self.docs.get(key)
        if entry is None:
            req = req or {}
            text = req.get("text")
            if paras is None:
                entry = self._known(text, req.get("levels"))
                if entry is None:
                    return None
            else:
                entry = self._build(paras, text)
            self._store(key, entry)
        self.docs.move_to_end(key)
        if only_headings not in entry:
            if only_headings:
                entry[True] = DocIndex(entry["paras"], True, norms=entry.get("norms"))
            else:
                entry[False] = DocIndex(entry["paras"], False, norms=entry.get("norms"))
        return entry[only_headings]

    def _result(self, full, t0, **extra):
        headings = sum(1 for lvl in full.levels if 0 < lvl < 10)
        out = {"ok": True, "paras": len(full.texts), "headings": headings, "cached": bool(full.on_disk),
               "elapsed": round(time.perf_counter() - t0, 3)}
        out.update(extra)
        return out

    def index(self, req: dict) -> dict:
        t0 = time.perf_counter()
        key = str(req.get("doc") or "")
        full = self._index(key, req.get("paras"), False, req)
        if full is None:
            return {"ok": False, "need_paras": True}
        self._index(key, None, True)
        return self._result(full, t0)

    def patch(self, req: dict) -> dict:
        """גרסה חדשה של מסמך מגרסה קודמת + הפסקאות שהשתנו בלבד."""
        t0 = time.perf_counter()
        key = str(req.get("doc") or "")
        text = req.get("text")
        if key in self.docs:
            return self._result(self._index(key, None, False), t0, reused=-1)
        known = self._known(text, req.get("levels"))
        if known is not None:
            self._store(key, known)
            self._index(key, None, True)
            return self._result(known[False], t0, reused=-1)

        base = req.get("base")
        src = self._in_memory(base)
        texts = norms = full = origin = None
        if src is not None:
            texts = src[False].texts
            norms = src.get("norms")
            if isinstance(src[False], PatchedIndex):
                full, origin = src[False].base, src[False].origin
            else:
                full = src[False]
                if norms is None:
                    norms = src["norms"] = load_norms(full.db, len(texts))
        elif self.cache is not None and base:
            opened = self.cache.open(base)
            if opened is not None:
                db, texts = opened
                norms = load_norms(db, len(texts))
                full = DocIndex([{"t": t, "h": 0} for t in texts], db=db, on_disk=True)
        if texts is None:
            return {"ok": False, "need_paras": True}

        new_texts, new_origin, reuse = [], [], {}
        try:
            for op in req.get("ops") or []:
                if isinstance(op, str):
                    new_texts.append(op)
                    new_origin.append(-1)
                    continue
                start, count = int(op[0]), int(op[1])
                if start < 0 or count < 0 or start + count > len(texts):
                    return {"ok": False, "need_paras": True}
                if norms is not None:
                    for k in range(count):
                        reuse[len(new_texts) + k] = norms[start + k]
                new_texts.extend(texts[start:start + count])
                new_origin.extend(origin[start:start + count] if origin is not None else range(start, start + count))
        except (TypeError, ValueError, IndexError):
            return {"ok": False, "need_paras": True}
        levels = self._levels(req.get("levels"), len(new_texts))
        if levels is None:
            return {"ok": False, "need_paras": True}

        new_norms = normalize_paras(new_texts, reuse, progress=lambda f: self._progress(0.8 * f))
        paras = [{"t": t, "h": lvl} for t, lvl in zip(new_texts, levels)]
        entry = {"paras": paras, "text": text, "norms": new_norms}
        changed = sum(1 for o in new_origin if o < 0)
        rebuilt = changed > max(PATCH_LIMIT, len(new_texts) // 25)
        if rebuilt:
            entry[False] = DocIndex(paras, norms=new_norms)        # השינויים הצטברו – מפה מלאה חדשה (בזיכרון)
        else:
            entry[False] = PatchedIndex(paras, full, new_origin, new_norms)
        # מפת הכותרות: אם הכותרות עצמן לא השתנו (רק המקום שלהן) – אותה מפה, עם המקומות החדשים
        old_heads = src.get(True) if src is not None else None
        if old_heads is not None:
            hmap = [i for i, lvl in enumerate(levels) if 0 < lvl < 10]
            if [old_heads.texts[j] for j in old_heads.map] == [new_texts[i] for i in hmap]:
                heads = object.__new__(DocIndex)
                heads.__dict__.update(old_heads.__dict__)
                heads.all_paras, heads.levels, heads.texts, heads.map = paras, levels, new_texts, hmap
                heads.paths = entry[False].paths
                entry[True] = heads
        self._store(key, entry)
        self._index(key, None, True)
        if base and base != text:
            self._drop_text(base, key)
        return self._result(entry[False], t0, reused=len(reuse), normalized=len(new_texts) - len(reuse),
                            changed=changed, rebuilt=rebuilt)

    def persist(self, req: dict) -> dict:
        """שומר בדיסק את המפה של הגרסה הזו (כדי שבפתיחה הבאה לא תיבנה שוב)."""
        entry = self.docs.get(str(req.get("doc") or "")) or self._in_memory(req.get("text"))
        if entry is None or False not in entry or not entry.get("text") or self.cache is None:
            return {"ok": False, "error": "unknown document"}
        full = entry[False]
        if full.on_disk or self.cache.has(entry["text"]):
            self.cache.touch(entry["text"])
            return {"ok": True, "saved": False}
        if isinstance(full, PatchedIndex):
            # גרסה ערוכה: עכשיו (כשהמסמך נסגר) בונים לה מפה מלאה אחת, ישר לדיסק
            db = self.cache.build(entry["text"], full.texts, entry.get("norms"))
            if db is not None:
                db.close()
            return {"ok": db is not None, "saved": True}
        if entry.get("norms") is not None and load_norms(full.db, len(full.texts)) is None:
            _store_doc(full.db, full.texts, entry["norms"])    # (לא אמור לקרות – המילים נשמרות בבנייה)
        return {"ok": self.cache.save(entry["text"], full.db, len(full.texts)), "saved": True}

    def docx_headings(self, req: dict) -> dict:
        t0 = time.perf_counter()
        from .docheadings import docx_headings
        out = docx_headings(str(req.get("path") or ""))
        out.update(ok=True, elapsed=round(time.perf_counter() - t0, 3))
        return out

    def relevel(self, req: dict) -> dict:
        t0 = time.perf_counter()
        src = self.docs.get(str(req.get("from") or ""))
        levels = req.get("levels")
        if src is None or not isinstance(levels, list) or len(levels) != len(src["paras"]) or False not in src:
            return {"ok": False, "need_paras": True}
        key = str(req.get("doc") or "")
        self._store(key, self._with_levels(src, levels))
        full = self._index(key, None, False)
        self._index(key, None, True)
        return self._result(full, t0)

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
        found, forms, phrase, res_terms, message = idx.run(query, opts)
        limit = max(1, int(req.get("limit") or 500))
        # בתוך מסמך אחד – לפי סדר הופעה במסמך כמו בחיפוש של Word, אבל ההתאמות המלאות קודם
        found.sort(key=lambda x: (-x[1].covered, x[0], x[1].span[0] if x[1].span else 0))
        out = []
        for para, h, searcher, highlight in found[:limit]:
            searcher.materialize(h, highlight)
            text = idx.texts[para]
            toks = tokenize(text)
            ranges = [[toks[p][0], toks[p][1]] for p in sorted(h.span) if p < len(toks)]
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
        return {"ok": True, "total": len(found), "shown": len(out), "hits": out,
                "forms": [[f, c] for f, c in forms.most_common(30)], "phrase": phrase,
                "n_terms": res_terms, "elapsed": round(time.perf_counter() - t0, 3),
                "message": message, "headings": headings}


def handle(service: DocSearchService, line: str, emit=None) -> dict:
    """emit(dict) – לשורות התקדמות לפני התשובה (רק אם הבקשה ביקשה "progress")."""
    try:
        req = json.loads(line)
    except ValueError as e:
        return {"ok": False, "error": f"bad json: {e}"}
    cmd = req.get("cmd")
    service.report = None
    if emit is not None and req.get("progress"):
        last = [0.0, -1.0]

        def report(frac):
            now = time.perf_counter()
            if now - last[0] >= PROGRESS_INTERVAL and frac - last[1] >= 0.01:
                last[0], last[1] = now, frac
                emit({"progress": round(min(max(frac, 0.0), 1.0), 3)})

        service.report = report
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
        if cmd == "patch":
            return service.patch(req)
        if cmd == "persist":
            return service.persist(req)
        if cmd == "docx_headings":
            return service.docx_headings(req)
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
    if service.cache is not None:
        service.cache.cleanup()            # מפות של מסמכים שלא נפתחו 3 ימים

    def emit(obj):
        stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        stdout.flush()

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        if line == '{"cmd": "quit"}' or line == '{"cmd":"quit"}':
            break
        emit(handle(service, line, emit))
    return 0
