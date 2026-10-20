"""עבודות רקע: פענוח הסלים, עדכון מפת החיפוש, ואחריו (אם צריך) חיפוש."""

import os
import traceback
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal, Slot

from ..index import IndexDB, resolve_basket
from ..search import Searcher, para_cache


@dataclass
class JobOutcome:
    baskets: dict = field(default_factory=dict)    # מזהה_סל → (רשומות, קבצים)
    status: dict = field(default_factory=dict)     # נתיב → (מצב, הודעה, מספר_פסקאות)
    searched: list = field(default_factory=list)   # מזהי הסלים שבהם חיפשנו
    indexed: int = 0
    result: object = None
    error: str = ""
    cancelled: bool = False


class Job(QObject):
    progress = Signal(str, int, int)      # טקסט, בוצע, סה"כ
    done = Signal(object)                 # JobOutcome

    def __init__(self, db_path, baskets, search_ids=(), query=None, opts=None):
        """baskets: מזהה_סל → פריטים; search_ids: הסלים שבהם מחפשים."""
        super().__init__()
        self.db_path, self.baskets = db_path, baskets
        self.search_ids, self.query, self.opts = list(search_ids), query, opts
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def cancelled(self):
        return self._cancel

    @Slot()
    def run(self):
        out = JobOutcome(searched=self.search_ids)
        db = None
        try:
            db = IndexDB(self.db_path)
            self.progress.emit("סורק את הסלים…", 0, 0)
            all_files, seen = [], set()
            for bid, items in self.baskets.items():
                entries, files = resolve_basket(items)
                out.baskets[bid] = (entries, files)
                for f in (f for _, _, found in entries for f in found):
                    if f not in seen:
                        seen.add(f)
                        all_files.append(f)
            db.set_basket_counts({bid: len(files) for bid, (_, files) in out.baskets.items()})

            stale = db.stale_files(all_files)
            if stale:
                def prog(done, total, path):
                    self.progress.emit(f"בונה מפת חיפוש · {os.path.basename(path)}", done, total)
                self.progress.emit("בונה מפת חיפוש…", 0, len(stale))
                out.indexed = db.update(stale, progress=prog, cancelled=self.cancelled)
                para_cache.invalidate()

            rows = db.file_rows(all_files)
            out.status = {p: (r[3], r[4], r[0]) for p, r in rows.items()}
            if self._cancel:
                out.cancelled = True
            elif self.query is not None:
                self.progress.emit("מחפש…", 0, 0)
                wanted = {f for bid in self.search_ids if bid in out.baskets for f in out.baskets[bid][1]}
                file_ids = {r[0]: p for p, r in rows.items() if p in wanted and r[3] == "ok"}
                out.result = Searcher(db).search(self.query, file_ids, self.opts, cancelled=self.cancelled)
        except Exception:
            out.error = traceback.format_exc()
        finally:
            if db is not None:
                db.close()
        self.done.emit(out)
