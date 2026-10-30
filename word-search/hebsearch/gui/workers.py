"""עבודות רקע על QThreadPool – כל עבודה כבדה רצה מחוץ לתהליכון הממשק, ולכן החלון לא נתקע.

  ScanJob     סריקת תיקיות הסלים + בניית/עדכון מפת החיפוש (רק מסמכים חדשים או ששונו)
  SearchJob   החיפוש עצמו (עם אחוזים וביטול) והכנת העמוד הראשון של הקטעים
  SnippetJob  הכנת קטעי תצוגה לעמוד הבא של תוצאות בזמן גלילה

כל עבודה מדווחת התקדמות (שבר 0..1 וטקסט) בתדירות מוגבלת – כדי שהממשק לא יוצף באירועים.
"""

from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from ..index import IndexDB, resolve_basket
from ..search import Searcher

PAGE = 30          # כמה תוצאות נטענות בכל עמוד (ובגלילה)

_pool = None


def pool() -> QThreadPool:
    global _pool
    if _pool is None:
        _pool = QThreadPool()
        _pool.setMaxThreadCount(4)
    return _pool


class JobSignals(QObject):
    progress = Signal(float, str)
    finished = Signal(object)          # JobOutcome


@dataclass
class JobOutcome:
    kind: str
    result: object = None
    error: str = ""
    cancelled: bool = False
    tag: object = None
    elapsed: float = 0.0


class Job(QRunnable):
    kind = "job"

    def __init__(self, tag=None):
        super().__init__()
        self.setAutoDelete(False)          # הממשק מחזיק התייחסות עד שהעבודה מסתיימת
        self.signals = JobSignals()
        self.tag = tag
        self._cancel = False
        self._last_emit = 0.0
        self._last_frac = -2.0
        self.is_done = False

    def cancel(self):
        self._cancel = True

    def cancelled(self) -> bool:
        return self._cancel

    def report(self, frac: float, text: str = "", force: bool = False):
        now = time.perf_counter()
        if not force and now - self._last_emit < 0.06 and abs(frac - self._last_frac) < 0.01:
            return
        self._last_emit, self._last_frac = now, frac
        self.signals.progress.emit(float(frac), text)

    def run(self):
        t0 = time.perf_counter()
        out = JobOutcome(self.kind, tag=self.tag)
        try:
            out.result = self.work()
        except Exception:
            out.error = traceback.format_exc()
        out.cancelled = self._cancel
        out.elapsed = time.perf_counter() - t0
        self.is_done = True
        self.signals.finished.emit(out)

    def work(self):          # pragma: no cover
        raise NotImplementedError

    def start(self):
        pool().start(self)


# ---------------------------------------------------------------- סריקה ואינדוקס
@dataclass
class ScanResult:
    entries: dict = field(default_factory=dict)     # מזהה_סל → [(נתיב, סוג, [מסמכים שתחתיו])]
    files: dict = field(default_factory=dict)       # מזהה_סל → [המסמכים שנכללים בחיפוש]
    status: dict = field(default_factory=dict)      # נתיב → (מצב, הודעה, מזהה_קובץ)
    indexed: int = 0
    stale: int = 0


class ScanJob(Job):
    kind = "scan"

    def __init__(self, db_path, baskets: dict, cache: dict, tag=None):
        """baskets: מזהה_סל → פריטי הסל; cache: מילון סריקות תיקיות (מתעדכן)."""
        super().__init__(tag)
        self.db_path, self.baskets, self.cache = db_path, baskets, cache

    def work(self):
        db = IndexDB(self.db_path)
        try:
            out = ScanResult()
            self.report(-1, "סורק את תיקיות הסלים…", force=True)
            all_files, seen = [], set()
            for bid, items in self.baskets.items():
                if self.cancelled():
                    return out
                entries, files = resolve_basket(items, cache=self.cache)
                out.entries[bid] = entries
                out.files[bid] = files
                for f in files:
                    if f not in seen:
                        seen.add(f)
                        all_files.append(f)
            db.set_basket_counts({bid: len(files) for bid, files in out.files.items()})
            self.report(-1, "בודק אילו מסמכים השתנו…", force=True)
            stale = db.stale_files(all_files)
            out.stale = len(stale)
            if stale:
                total = len(stale)

                def prog(done, _total, path):
                    self.report(done / total, f"בונה את מפת החיפוש\n{done:,} מתוך {total:,} מסמכים · "
                                              f"{os.path.basename(path)}")

                self.report(0.0, f"בונה את מפת החיפוש\n0 מתוך {total:,} מסמכים", force=True)
                out.indexed = db.update(stale, progress=prog, cancelled=self.cancelled)
            rows = db.file_rows(all_files)
            out.status = {p: (r[3], r[4], r[0]) for p, r in rows.items()}
            return out
        finally:
            db.close()


# ---------------------------------------------------------------- חיפוש
@dataclass
class SearchPayload:
    result: object
    pending: int = 0           # מסמכים בסל שעדיין לא נקראו (המפה בעדכון)
    tag: object = None


class SearchJob(Job):
    kind = "search"

    def __init__(self, db_path, query, opts, paths, status: dict, tag=None):
        super().__init__(tag)
        self.db_path, self.query, self.opts = db_path, query, opts
        self.paths, self.status = paths, status

    def work(self):
        db = IndexDB(self.db_path, ensure_schema=False)
        try:
            file_ids, pending = {}, 0
            for p in self.paths:
                st = self.status.get(p)
                if st is None:
                    pending += 1
                elif st[0] == "ok":
                    file_ids[st[2]] = p
            searcher = Searcher(db, self.opts.context_words)
            self.report(0.0, "מתחיל לחפש", force=True)
            res = searcher.search(self.query, file_ids, self.opts, cancelled=self.cancelled,
                                  progress=lambda f, t: self.report(0.92 * f, t))
            if res.cancelled or self.cancelled():
                return SearchPayload(res, pending, self.tag)
            first = res.hits[:PAGE]
            for i, h in enumerate(first):
                if self.cancelled():
                    break
                searcher.materialize(h, res.highlight)
                self.report(0.92 + 0.08 * (i + 1) / len(first), "מכין את התצוגה")
            return SearchPayload(res, pending, self.tag)
        finally:
            db.close()


class SnippetJob(Job):
    kind = "snippets"

    def __init__(self, db_path, hits, highlight, context_words, tag=None):
        super().__init__(tag)
        self.db_path, self.hits, self.highlight, self.context_words = db_path, hits, highlight, context_words

    def work(self):
        db = IndexDB(self.db_path, ensure_schema=False)
        try:
            searcher = Searcher(db, self.context_words)
            for h in self.hits:
                if self.cancelled():
                    break
                searcher.materialize(h, self.highlight)
            return self.hits
        finally:
            db.close()
