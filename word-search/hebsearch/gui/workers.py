"""עבודות רקע: עדכון מפת החיפוש ואחריו (אם צריך) חיפוש."""

import os
import traceback
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal, Slot

from ..index import IndexDB, resolve_items
from ..search import Searcher, para_cache


@dataclass
class JobOutcome:
    files: int = 0
    indexed: int = 0
    problems: list = field(default_factory=list)   # [(נתיב, הודעה)]
    result: object = None
    error: str = ""
    cancelled: bool = False


class Job(QObject):
    progress = Signal(str, int, int)      # טקסט, בוצע, סה"כ
    done = Signal(object)                 # JobOutcome

    def __init__(self, db_path, items, query=None, opts=None):
        super().__init__()
        self.db_path, self.items, self.query, self.opts = db_path, items, query, opts
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def cancelled(self):
        return self._cancel

    @Slot()
    def run(self):
        out = JobOutcome()
        db = None
        try:
            db = IndexDB(self.db_path)
            self.progress.emit("סורק את הסל…", 0, 0)
            files = resolve_items(self.items)
            out.files = len(files)
            stale = db.stale_files(files)
            if stale:
                def prog(done, total, path):
                    self.progress.emit(f"בונה מפת חיפוש · {os.path.basename(path)}", done, total)
                self.progress.emit("בונה מפת חיפוש…", 0, len(stale))
                out.indexed = db.update(stale, progress=prog, cancelled=self.cancelled)
                para_cache.invalidate()
            rows = db.file_rows(files)
            file_ids = {r[0]: p for p, r in rows.items() if r[3] == "ok"}
            out.problems = [(p, r[4] or r[3]) for p, r in rows.items() if r[3] != "ok"]
            if self._cancel:
                out.cancelled = True
            elif self.query is not None:
                self.progress.emit("מחפש…", 0, 0)
                out.result = Searcher(db).search(self.query, file_ids, self.opts, cancelled=self.cancelled)
        except Exception:
            out.error = traceback.format_exc()
        finally:
            if db is not None:
                db.close()
        self.done.emit(out)
