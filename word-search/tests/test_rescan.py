"""בדיקה חוזרת של האוספים (בחזרה לחלון): זולה, ולא קוראת שוב ושוב מסמך שנערך עכשיו ב-Word.

  * רשימת התיקיות נותנת גם את הגודל וזמן השינוי – מסמך שלא השתנה לא נבדק בנפרד;
  * מסמך שהשתנה אבל פתוח לעריכה (קובץ הבעלים ‎~$…‎ של Word לידו) ויש לו כבר גרסה במפה – נדחה,
    ונקרא רק לפני חיפוש (RefreshJob), ורק אם השתנה.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hebsearch import index as ix  # noqa: E402
from hebsearch.index import IndexDB, open_for_editing, resolve_basket  # noqa: E402
from hebsearch.gui.workers import RefreshJob, ScanJob  # noqa: E402

from docx_builder import build_docx  # noqa: E402


def old_walk(path):
    """ההתנהגות הקודמת (os.walk) – לבדוק שהסדר והסינון לא השתנו."""
    found = []
    for root, dirs, names in os.walk(path):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        found.extend(os.path.join(root, n) for n in sorted(names) if ix.is_supported(n))
    return found


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "אוסף")
        os.makedirs(os.path.join(self.dir, "ב", "פנימי"))
        os.makedirs(os.path.join(self.dir, "א"))
        os.makedirs(os.path.join(self.dir, ".נסתר"))
        self.doc = os.path.join(self.dir, "מסמך ארוך.docx")
        build_docx(self.doc, ["שלום עולם", "פסקה שנייה"])
        build_docx(os.path.join(self.dir, "א", "קצר.docx"), ["אחת"])
        build_docx(os.path.join(self.dir, "ב", "פנימי", "עמוק.docx"), ["שתיים"])
        build_docx(os.path.join(self.dir, "ב", "שני.docx"), ["שלוש"])
        build_docx(os.path.join(self.dir, ".נסתר", "לא.docx"), ["לא"])
        with open(os.path.join(self.dir, "הערות.txt"), "w") as f:
            f.write("x")
        self.db = IndexDB(os.path.join(self.tmp.name, "i.sqlite3"))
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.db.close)
        self.items = [(self.dir, "folder")]

    def index_all(self):
        files = resolve_basket(self.items)[1]
        self.db.update(self.db.stale_files(files))
        return files

    def edit_in_word(self, text):
        """כמו עריכה ושמירה ב-Word: קובץ הבעלים המוסתר לידו, והמסמך עצמו השתנה."""
        build_docx(self.doc, text)
        folder, name = os.path.split(self.doc)
        owner = os.path.join(folder, "~$" + name[2:])
        open(owner, "w").close()
        return owner


class WalkTest(Base):
    def test_same_files_and_order_as_before(self):
        self.assertEqual(ix._walk_folder(self.dir), old_walk(self.dir))
        self.assertEqual(len(ix._walk_folder(self.dir)), 4)

    def test_listing_gives_size_and_time(self):
        stats = {}
        files = ix._walk_folder(self.dir, stats)
        self.assertEqual(sorted(stats), sorted(files))
        for p in files:
            st = os.stat(p)
            self.assertEqual(stats[p], (st.st_mtime, st.st_size))

    def test_unchanged_documents_are_not_checked_one_by_one(self):
        files = self.index_all()
        stats = {}
        resolve_basket(self.items, stats=stats)
        with mock.patch.object(os, "stat", side_effect=AssertionError("stat per file")):
            self.assertEqual(self.db.stale_files(files, known=stats), [])

    def test_changed_document_is_found_from_the_listing(self):
        files = self.index_all()
        build_docx(self.doc, ["טקסט חדש לגמרי", "ועוד פסקה ארוכה יותר מקודם"])
        stats = {}
        resolve_basket(self.items, stats=stats)
        self.assertEqual(self.db.stale_files(files, known=stats), [self.doc])

    def test_outdated_listing_is_confirmed_with_the_file_itself(self):
        files = self.index_all()
        known = {p: (1.0, 1) for p in files}               # רשימה ישנה/שגויה – לא קוראים בגללה
        self.assertEqual(self.db.stale_files(files, known=known), [])


class OpenInWordTest(Base):
    def test_owner_files(self):
        self.assertFalse(open_for_editing(self.doc))
        folder, name = os.path.split(self.doc)
        for owner in ("~$" + name[2:], "~$" + name[1:], "~$" + name, ".~lock." + name + "#"):
            path = os.path.join(folder, owner)
            open(path, "w").close()
            self.assertTrue(open_for_editing(self.doc), owner)
            os.remove(path)
        self.assertFalse(open_for_editing(self.doc))

    def test_owner_file_is_not_a_document(self):
        self.edit_in_word(["א"])
        self.assertEqual(len(ix._walk_folder(self.dir)), 4)

    def test_background_scan_defers_the_document_being_edited(self):
        self.index_all()
        self.edit_in_word(["נוסח חדש שנכתב עכשיו ב-Word", "ועוד"])
        out = ScanJob(self.db.path, {1: self.items}, {}).work()
        self.assertEqual(out.deferred, [self.doc])
        self.assertEqual(out.indexed, 0)
        self.assertIn(self.doc, out.status)                 # בינתיים – הגרסה הקודמת במפה
        # "עדכון" ביד – קוראים גם אותו
        out = ScanJob(self.db.path, {1: self.items}, {}, defer_open=False).work()
        self.assertEqual(out.deferred, [])
        self.assertEqual(out.indexed, 1)

    def test_new_document_is_read_even_if_open(self):
        owner = self.edit_in_word(["מסמך חדש"])
        out = ScanJob(self.db.path, {1: self.items}, {}).work()
        self.assertEqual(out.deferred, [])
        self.assertEqual(out.indexed, 4)
        os.remove(owner)

    def test_closed_document_is_read_by_the_next_scan(self):
        self.index_all()
        owner = self.edit_in_word(["גרסה חדשה"])
        self.assertEqual(ScanJob(self.db.path, {1: self.items}, {}).work().deferred, [self.doc])
        os.remove(owner)                                    # נסגר ב-Word
        out = ScanJob(self.db.path, {1: self.items}, {}).work()
        self.assertEqual((out.deferred, out.indexed), ([], 1))

    def test_refresh_before_search_reads_only_if_changed(self):
        self.index_all()
        self.edit_in_word(["גרסה חדשה עם המילה זברה"])
        out = RefreshJob(self.db.path, [self.doc]).work()
        self.assertEqual(out.indexed, 1)
        self.assertEqual(out.status[self.doc][0], "ok")
        self.assertEqual(RefreshJob(self.db.path, [self.doc]).work().indexed, 0)
        self.assertEqual(self.db.stale_files([self.doc]), [])


if __name__ == "__main__":
    unittest.main()
