""""המפה" – אינדקס הפוך שנשמר ב-SQLite.

    vocab     מילה מנורמלת → מזהה מספרי (אוצר המילים של כל המסמכים)
    postings  (מזהה מילה, מזהה קובץ) → כל המופעים: זוגות (פסקה, מיקום המילה בפסקה)
    texts     הטקסט המקורי של כל קובץ (דחוס), להצגת קטעים ולאימות מרחקים
    files     נתיב, זמן שינוי וגודל – כדי לעדכן רק קבצים שהשתנו

חיפוש לא סורק את המסמכים: התבנית רצה על אוצר המילים, המופעים של המילים
שהתאימו נשלפים מ-postings, ובדיקת המרחק והסדר בין המילים נעשית על המיקומים
עצמם – בלי לקרוא טקסט. את הטקסט קוראים רק כדי להציג את התוצאות שעל המסך.
"""

import json
import os
import sqlite3
import time
import zlib
from array import array
from concurrent.futures import ProcessPoolExecutor

from .extract import DOC_EXTS, DOCX_EXTS, PDF_EXTS, doc_support_available, extract_doc_com, extract_docx
from .normalize import normalize_text

INDEX_VERSION = "4"
SUPPORTED_EXTS = DOCX_EXTS | DOC_EXTS | PDF_EXTS

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS files(
    id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, mtime REAL, size INTEGER,
    status TEXT, message TEXT, n_paras INTEGER, word_ids BLOB);
CREATE TABLE IF NOT EXISTS texts(file_id INTEGER PRIMARY KEY, data BLOB);
CREATE TABLE IF NOT EXISTS vocab(id INTEGER PRIMARY KEY, word TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS postings(
    word_id INTEGER, file_id INTEGER, paras BLOB,
    PRIMARY KEY(word_id, file_id)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS baskets(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
    doc_count INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS basket_items(
    basket_id INTEGER, path TEXT, kind TEXT, PRIMARY KEY(basket_id, path));
"""
INDEX_TABLES = ("files", "texts", "vocab", "postings")


def is_supported(path: str) -> bool:
    name = os.path.basename(path)
    return not name.startswith("~$") and os.path.splitext(name)[1].lower() in SUPPORTED_EXTS


def _key(p):
    return os.path.normcase(os.path.abspath(p))


def is_excluded(path, excluded, root=None) -> bool:
    """האם המסמך הוחרג – בעצמו או דרך תת-תיקייה שלו (עד תיקיית הסל root, לא כולל)."""
    if not excluded:
        return False
    k = _key(path)
    stop = _key(root) if root else None
    while k != stop:
        if k in excluded:
            return True
        parent = os.path.dirname(k)
        if parent == k:
            return False
        k = parent
    return False


def resolve_basket(items):
    """פריטי סל → (רשומות, קבצים).

    items: [(נתיב, סוג)] כשסוג הוא folder / file / exclude (מסמך או תת-תיקייה שהוחרגו).
    רשומות: [(נתיב, סוג, [כל המסמכים שתחתיו])] – לתצוגת תוכן הסל.
    קבצים: המסמכים שייכללו בחיפוש, ממוינים וללא כפילויות וללא המוחרגים.
    """
    excluded = {_key(p) for p, k in items if k == "exclude"}
    entries, files, seen = [], [], set()
    for path, kind in items:
        if kind == "exclude":
            continue
        found = []
        if kind == "folder":
            for root, dirs, names in os.walk(path):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                found.extend(os.path.join(root, n) for n in sorted(names) if is_supported(n))
        elif is_supported(path) and os.path.isfile(path):
            found.append(os.path.abspath(path))
        entries.append((path, kind, found))
        for f in found:
            k = _key(f)
            # החרגה חלה רק על מה שבתוך תיקייה; מסמך שנוסף ישירות תמיד נכלל
            if k not in seen and not (kind == "folder" and is_excluded(f, excluded, path)):
                seen.add(k)
                files.append(f)
    return entries, files


def resolve_items(items):
    return resolve_basket(items)[1]


def word_postings(paras):
    """מילה → array[פסקה, מיקום, פסקה, מיקום, ...] ארוז כבתים."""
    words = {}
    for i, para in enumerate(paras):
        for pos, w in enumerate(normalize_text(para[0])):
            lst = words.get(w)
            if lst is None:
                words[w] = [i, pos]
            else:
                lst.append(i)
                lst.append(pos)
    return {w: array("I", lst).tobytes() for w, lst in words.items()}


def pack_paras(paras) -> bytes:
    return zlib.compress(json.dumps(paras, ensure_ascii=False).encode("utf-8"), 6) if paras else b""


def process_file(path: str) -> dict:
    """עבודה כבדה (קריאת המסמך + נרמול) – רצה בתהליך נפרד."""
    st = os.stat(path)
    res = {"path": path, "mtime": st.st_mtime, "size": st.st_size,
           "paras": b"", "n_paras": 0, "words": {}, "status": "ok", "message": ""}
    ext = os.path.splitext(path)[1].lower()
    if ext in DOCX_EXTS:
        extract = extract_docx
    elif ext in PDF_EXTS:
        try:
            from .pdftext import extract_pdf as extract
            import pymupdf  # noqa: F401
        except ImportError:
            res["status"], res["message"] = "unsupported", "לקריאת PDF יש להתקין את pymupdf"
            return res
    else:
        res["status"], res["message"] = "unsupported", "פורמט doc ישן – נדרש וורד מותקן בחלונות"
        return res
    try:
        paras = extract(path)
        res["words"] = word_postings(paras)
        res["paras"], res["n_paras"] = pack_paras(paras), len(paras)
    except ValueError as e:  # הודעה ידידותית (PDF סרוק, סיסמה)
        res["status"], res["message"] = "error", str(e)
    except Exception as e:  # קובץ פגום
        res["status"], res["message"] = "error", f"{type(e).__name__}: {e}"
    return res


class IndexDB:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path, timeout=30)
        c = self.conn
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-65536")
        c.execute("PRAGMA temp_store=MEMORY")
        c.executescript(SCHEMA)
        cols = {r[1] for r in c.execute("PRAGMA table_info(baskets)")}
        if "doc_count" not in cols:  # מסד נתונים מגרסה קודמת
            c.execute("ALTER TABLE baskets ADD COLUMN doc_count INTEGER DEFAULT 0")
        row = c.execute("SELECT value FROM meta WHERE key='index_version'").fetchone()
        if not row or row[0] != INDEX_VERSION:
            with c:
                for t in INDEX_TABLES:
                    c.execute(f"DELETE FROM {t}")
                c.execute("INSERT OR REPLACE INTO meta VALUES('index_version', ?)", (INDEX_VERSION,))
        self._vocab = None

    def close(self):
        self.conn.close()

    # ---------- סלים ----------
    def baskets(self):
        """[(מזהה, שם, מספר_מסמכים)]"""
        return self.conn.execute("SELECT id, name, doc_count FROM baskets ORDER BY id").fetchall()

    def set_basket_counts(self, counts):
        with self.conn:
            self.conn.executemany("UPDATE baskets SET doc_count=? WHERE id=?",
                                  [(c, bid) for bid, c in counts.items()])

    def set_excluded(self, basket_id: int, path: str, excluded: bool):
        """מחריג מסמך או תת-תיקייה מתוך תיקייה שבסל (או מחזיר אותם).
        החזרה של תיקייה מחזירה גם את כל מה שהוחרג בתוכה."""
        path = os.path.abspath(path)
        with self.conn:
            if excluded:
                self.conn.execute("INSERT OR IGNORE INTO basket_items VALUES(?,?,'exclude')", (basket_id, path))
            else:
                prefix = path.rstrip("\\/") + os.sep
                rows = self.conn.execute(
                    "SELECT path FROM basket_items WHERE basket_id=? AND kind='exclude'", (basket_id,)).fetchall()
                gone = [p for (p,) in rows
                        if os.path.normcase(p) == os.path.normcase(path)
                        or os.path.normcase(p).startswith(os.path.normcase(prefix))]
                self.conn.executemany("DELETE FROM basket_items WHERE basket_id=? AND path=? AND kind='exclude'",
                                      [(basket_id, p) for p in gone])

    def create_basket(self, name: str) -> int:
        with self.conn:
            return self.conn.execute("INSERT INTO baskets(name) VALUES(?)", (name,)).lastrowid

    def rename_basket(self, basket_id: int, name: str):
        with self.conn:
            self.conn.execute("UPDATE baskets SET name=? WHERE id=?", (name, basket_id))

    def delete_basket(self, basket_id: int):
        with self.conn:
            self.conn.execute("DELETE FROM basket_items WHERE basket_id=?", (basket_id,))
            self.conn.execute("DELETE FROM baskets WHERE id=?", (basket_id,))

    def basket_items(self, basket_id: int):
        return self.conn.execute(
            "SELECT path, kind FROM basket_items WHERE basket_id=? ORDER BY kind DESC, path",
            (basket_id,)).fetchall()

    def add_basket_items(self, basket_id: int, items):
        with self.conn:
            self.conn.executemany("INSERT OR REPLACE INTO basket_items VALUES(?,?,?)",
                                  [(basket_id, os.path.abspath(p), k) for p, k in items])

    def remove_basket_items(self, basket_id: int, paths):
        """הסרת פריטים מהסל (וגם ההחרגות שהיו בתוך תיקייה שהוסרה)."""
        with self.conn:
            self.conn.executemany("DELETE FROM basket_items WHERE basket_id=? AND path=?",
                                  [(basket_id, p) for p in paths])
            rows = self.conn.execute("SELECT path FROM basket_items WHERE basket_id=? AND kind='exclude'",
                                     (basket_id,)).fetchall()
            prefixes = [_key(p).rstrip("\\/") + os.sep for p in paths]
            self.conn.executemany(
                "DELETE FROM basket_items WHERE basket_id=? AND path=? AND kind='exclude'",
                [(basket_id, p) for (p,) in rows if any(_key(p).startswith(x) for x in prefixes)])

    # ---------- מצב קבצים ----------
    def file_rows(self, paths):
        """path → (id, mtime, size, status, message)"""
        out = {}
        q = "SELECT path, id, mtime, size, status, message FROM files WHERE path IN ({})"
        for i in range(0, len(paths), 500):
            chunk = paths[i:i + 500]
            for row in self.conn.execute(q.format(",".join("?" * len(chunk))), chunk):
                out[row[0]] = row[1:]
        return out

    def stale_files(self, paths):
        rows = self.file_rows(paths)
        stale = []
        for p in paths:
            r = rows.get(p)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if r is None or r[1] != st.st_mtime or r[2] != st.st_size:
                stale.append(p)
        return stale

    def file_ids(self, paths):
        rows = self.file_rows(paths)
        return {rows[p][0]: p for p in paths if p in rows and rows[p][3] == "ok"}

    def file_paras(self, file_id: int):
        row = self.conn.execute("SELECT data FROM texts WHERE file_id=?", (file_id,)).fetchone()
        return json.loads(zlib.decompress(row[0])) if row else []

    def stats(self):
        c = self.conn
        return {
            "files": c.execute("SELECT count(*) FROM files WHERE status='ok'").fetchone()[0],
            "words": c.execute("SELECT count(*) FROM vocab").fetchone()[0],
            "size_mb": os.path.getsize(self.path) / 1e6 if os.path.exists(self.path) else 0,
        }

    # ---------- אוצר מילים ----------
    def vocab_version(self):
        return self.conn.execute("SELECT coalesce(max(id), 0) FROM vocab").fetchone()[0]

    def load_vocab(self):
        return self.conn.execute("SELECT id, word FROM vocab ORDER BY id").fetchall()

    def _word_ids(self, words):
        if self._vocab is None:
            self._vocab = {w: i for i, w in self.conn.execute("SELECT id, word FROM vocab")}
            self._next_id = max(self._vocab.values(), default=0) + 1
        ids, new = [], []
        for w in words:
            wid = self._vocab.get(w)
            if wid is None:
                wid = self._vocab[w] = self._next_id
                self._next_id += 1
                new.append((wid, w))
            ids.append(wid)
        if new:
            self.conn.executemany("INSERT INTO vocab(id, word) VALUES(?,?)", new)
        return ids

    def postings_size(self, word_ids):
        """אומדן עלות לשליפת המילים: סך גודל רשימות המופעים (בלי לקרוא אותן)."""
        total = 0
        for i in range(0, len(word_ids), 500):
            chunk = word_ids[i:i + 500]
            q = f"SELECT sum(length(paras)) FROM postings WHERE word_id IN ({','.join('?' * len(chunk))})"
            total += self.conn.execute(q, chunk).fetchone()[0] or 0
        return total

    def postings(self, word_ids, file_ids):
        """מחזיר (מזהה_מילה, מזהה_קובץ, array[פסקה, מיקום, ...]) לקבצי הסל בלבד."""
        for i in range(0, len(word_ids), 500):
            chunk = word_ids[i:i + 500]
            q = f"SELECT word_id, file_id, paras FROM postings WHERE word_id IN ({','.join('?' * len(chunk))})"
            for wid, fid, blob in self.conn.execute(q, chunk):
                if fid in file_ids:
                    a = array("I")
                    a.frombytes(blob)
                    yield wid, fid, a

    # ---------- כתיבה ----------
    def _remove_file(self, fid, word_blob):
        if word_blob:
            old = array("I")
            old.frombytes(word_blob)
            self.conn.executemany("DELETE FROM postings WHERE word_id=? AND file_id=?",
                                  ((w, fid) for w in old))
        self.conn.execute("DELETE FROM texts WHERE file_id=?", (fid,))

    def store(self, res: dict):
        c = self.conn
        row = c.execute("SELECT id, word_ids FROM files WHERE path=?", (res["path"],)).fetchone()
        if row:
            fid = row[0]
            self._remove_file(fid, row[1])
        else:
            fid = c.execute("INSERT INTO files(path) VALUES(?)", (res["path"],)).lastrowid
        words = res["words"]
        wids = self._word_ids(list(words))
        rows = sorted(zip(wids, words.values()))
        c.executemany("INSERT INTO postings VALUES(?,?,?)", ((wid, fid, blob) for wid, blob in rows))
        if res["paras"]:
            c.execute("INSERT INTO texts VALUES(?,?)", (fid, res["paras"]))
        c.execute("UPDATE files SET mtime=?, size=?, status=?, message=?, n_paras=?, word_ids=? WHERE id=?",
                  (res["mtime"], res["size"], res["status"], res["message"], res["n_paras"],
                   array("I", (w for w, _ in rows)).tobytes(), fid))

    def purge_missing(self):
        gone = [(fid, blob) for fid, path, blob in
                self.conn.execute("SELECT id, path, word_ids FROM files")
                if not os.path.exists(path)]
        with self.conn:
            for fid, blob in gone:
                self._remove_file(fid, blob)
                self.conn.execute("DELETE FROM files WHERE id=?", (fid,))
        return len(gone)

    def update(self, paths, progress=None, cancelled=None, workers=None):
        """מאנדקס את הקבצים שנתנו (בדרך כלל רק אלו שהשתנו)."""
        total = len(paths)
        done, last_commit = 0, time.monotonic()
        doc_paths = [p for p in paths if os.path.splitext(p)[1].lower() in DOC_EXTS]
        docx_paths = [p for p in paths if os.path.splitext(p)[1].lower() not in DOC_EXTS]

        def handle(res):
            nonlocal done, last_commit
            self.store(res)
            done += 1
            if progress:
                progress(done, total, res["path"])
            if time.monotonic() - last_commit > 2:
                self.conn.commit()
                last_commit = time.monotonic()

        try:
            if len(docx_paths) > 8:
                n = workers or max(1, (os.cpu_count() or 2) - 1)
                with ProcessPoolExecutor(max_workers=n) as pool:
                    for res in pool.map(process_file, docx_paths, chunksize=4):
                        handle(res)
                        if cancelled and cancelled():
                            pool.shutdown(cancel_futures=True)
                            return done
            else:
                for p in docx_paths:
                    if cancelled and cancelled():
                        return done
                    handle(process_file(p))
            if doc_paths:
                self._update_doc_files(doc_paths, handle, cancelled)
        finally:
            self.conn.commit()
        return done

    def _update_doc_files(self, paths, handle, cancelled):
        word = None
        if doc_support_available():
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                word = win32com.client.DispatchEx("Word.Application")
                word.Visible = False
                word.DisplayAlerts = 0
            except Exception:
                word = None
        try:
            for p in paths:
                if cancelled and cancelled():
                    return
                res = process_file(p)
                if word is not None:
                    try:
                        paras = extract_doc_com(p, word)
                        res["words"] = word_postings(paras)
                        res["paras"], res["n_paras"] = pack_paras(paras), len(paras)
                        res["status"], res["message"] = "ok", ""
                    except Exception as e:
                        res["status"], res["message"] = "error", str(e)
                handle(res)
        finally:
            if word is not None:
                try:
                    word.Quit()
                except Exception:
                    pass
