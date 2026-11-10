"""רכיב העזר של התוסף ל-Word: חיפוש בפסקאות של מסמך פתוח, עם מיקום מדויק של המילים."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hebsearch import docsearch  # noqa: E402

PARAS = [
    {"t": "הלכות שבת", "h": 1},
    {"t": "ההולך בשבת ברשות הרבים צריך לשמור שלא יוציא דבר.", "h": 0},
    {"t": "מהלכות יום טוב", "h": 2},
    {"t": "וְהֲלָכָה כרבי יהודה שאסור להלך יותר מאלפיים אמה.", "h": 0},
    {"t": "איסור ייחוד – דיני איסור ייחוד", "h": 1},
    {"t": "", "h": 0},
    {"t": "כתב הרמב\"ם: אסור ייחוד עם", "h": 0},
]


class DocSearchTest(unittest.TestCase):
    def setUp(self):
        self.svc = docsearch.DocSearchService()

    def search(self, query, **kw):
        req = {"doc": "d", "paras": PARAS, "query": query}
        req.update(kw)
        return self.svc.search(req)

    def words(self, r):
        return [PARAS[h["para"]]["t"][a:b] for h in r["hits"] for a, b in h["ranges"]]

    def test_ranges_point_at_the_original_words(self):
        r = self.search("הלך", options={"forms": "all"})
        self.assertEqual(self.words(r), ["הלכות", "ההולך", "מהלכות", "וְהֲלָכָה", "להלך"])   # כולל ניקוד
        self.assertEqual(r["hits"][1]["heading"], "הלכות שבת")
        self.assertEqual(r["hits"][4]["heading"], "מהלכות יום טוב")

    def test_heading_path_of_each_hit(self):
        r = self.search("הלך", options={"forms": "all"})
        paths = [h["path"] for h in r["hits"]]
        self.assertEqual(paths[0], [])                              # "הלכות שבת" – כותרת עליונה
        self.assertEqual(paths[1], ["הלכות שבת"])
        self.assertEqual(paths[2], ["הלכות שבת"])                   # "מהלכות יום טוב" – כותרת 2 תחת כותרת 1
        self.assertEqual(paths[4], ["הלכות שבת", "מהלכות יום טוב"])
        r = self.search("ייחוד")
        self.assertEqual(r["hits"][-1]["path"], ["איסור ייחוד – דיני איסור ייחוד"])   # כותרת 1 חדשה סוגרת את הקודמות
        r = self.search("הלך", options={"forms": "all"}, headings_only=True)
        self.assertEqual([h["path"] for h in r["hits"]], [[], ["הלכות שבת"]])

    def test_snippet_is_only_from_the_hit_paragraph(self):
        short = [{"t": "גלות מצרים – הכח להוציא טוב 256", "h": 0}, {"t": "גלות בבל 688", "h": 0},
                 {"t": "ריבוי עם ישראל 690", "h": 0}]
        r = self.svc.search({"doc": "idx", "paras": short, "query": "בבל"})
        segs = r["hits"][0]["snippet"]
        self.assertEqual("".join(t for t, _ in segs), "גלות בבל 688")          # בלי השורות שלפני ואחרי
        self.assertNotIn(3, [k for _, k in segs])                               # בלי סימן ¶

    def test_options_are_the_same_as_the_program(self):
        self.assertEqual(self.search("הלך", options={"forms": "exact"})["total"], 0)
        self.assertEqual(self.words(self.search("שבת", options={"forms": "prefixes"})), ["שבת", "בשבת"])
        r = self.search("איסור ייחוד", options={"distance": "adjacent"})
        self.assertEqual(r["total"], 2)
        r = self.search("אסור עם", options={"distance": "near", "near": 1})
        self.assertEqual(r["total"], 1)

    def test_headings_only(self):
        r = self.search("הלך", options={"forms": "all"}, headings_only=True)
        self.assertEqual([h["para"] for h in r["hits"]], [0, 2])
        self.assertEqual(r["headings"], 3)
        self.assertEqual("".join(t for t, _ in r["hits"][1]["snippet"]), "מהלכות יום טוב")   # בלי כותרות שכנות
        self.assertEqual(self.search("רשות", headings_only=True)["total"], 0)

    def test_quoted_phrase_and_cache(self):
        r = self.search('"איסור ייחוד"')
        self.assertTrue(r["phrase"])
        self.assertEqual(r["total"], 2)
        again = self.svc.search({"doc": "d", "query": "שבת"})           # בלי פסקאות – מהמטמון
        self.assertTrue(again["ok"])
        self.assertEqual(self.svc.search({"doc": "new", "query": "שבת"}), {"ok": False, "need_paras": True})

    def test_index_ahead_then_search_without_resending(self):
        r = self.svc.index({"doc": "pre", "paras": PARAS})
        self.assertEqual((r["ok"], r["paras"], r["headings"]), (True, len(PARAS), 3))
        self.assertTrue(self.svc.has("pre"))
        hit = self.svc.search({"doc": "pre", "query": "הלך", "options": {"forms": "all"}, "headings_only": True})
        self.assertEqual(hit["total"], 2)                     # בלי לשלוח שוב את הפסקאות
        self.assertEqual(self.svc.index({"doc": "missing"}), {"ok": False, "need_paras": True})

    def test_relevel_reuses_the_index_with_new_heading_levels(self):
        flat = [{"t": p["t"], "h": 0} for p in PARAS]               # לפני שהתוסף קרא את הכותרות
        self.svc.index({"doc": "v1", "paras": flat})
        full_db = self.svc.docs["v1"][False].db
        r = self.svc.relevel({"from": "v1", "doc": "v2", "levels": [p["h"] for p in PARAS]})
        self.assertEqual((r["ok"], r["headings"]), (True, 3))
        self.assertIs(self.svc.docs["v2"][False].db, full_db)          # בלי לבנות מחדש
        hit = self.svc.search({"doc": "v2", "query": "הלך", "options": {"forms": "all"}})
        self.assertEqual(hit["hits"][4]["path"], ["הלכות שבת", "מהלכות יום טוב"])
        self.assertEqual(self.svc.search({"doc": "v2", "query": "הלך", "options": {"forms": "all"},
                                          "headings_only": True})["total"], 2)
        self.assertEqual(self.svc.search({"doc": "v1", "query": "הלך", "options": {"forms": "all"},
                                          "headings_only": True})["total"], 0)     # הגרסה הקודמת לא השתנתה
        self.assertEqual(self.svc.relevel({"from": "missing", "doc": "x", "levels": []}),
                         {"ok": False, "need_paras": True})
        self.assertEqual(self.svc.relevel({"from": "v2", "doc": "x", "levels": [1]}),
                         {"ok": False, "need_paras": True})                         # מספר פסקאות לא תואם

    def test_shared_index_survives_eviction_of_the_old_version(self):
        svc = docsearch.DocSearchService(keep=2)
        svc.index({"doc": "a1", "paras": PARAS})
        svc.relevel({"from": "a1", "doc": "a2", "levels": [0] * len(PARAS)})
        svc.index({"doc": "other", "paras": [{"t": "שלום", "h": 0}]})         # a1 יוצא מהמטמון
        self.assertNotIn("a1", svc.docs)
        self.assertEqual(svc.search({"doc": "a2", "query": "שבת"})["total"], 2)   # המפה המשותפת לא נסגרה

    def test_document_without_headings(self):
        svc = docsearch.DocSearchService()
        r = svc.search({"doc": "x", "paras": [{"t": "שלום עולם", "h": 0}], "query": "שלום", "headings_only": True})
        self.assertEqual((r["ok"], r["total"], r["headings"]), (True, 0, 0))

    def test_protocol_over_pipes(self):
        lines = "\n".join([json.dumps({"cmd": "ping"}),
                           json.dumps({"cmd": "search", "doc": "z", "paras": PARAS, "query": "שבת"},
                                      ensure_ascii=False),
                           "not json", json.dumps({"cmd": "quit"})]) + "\n"
        out = io.StringIO()
        docsearch.serve(io.StringIO(lines), out)
        replies = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertTrue(replies[0]["ok"])
        self.assertEqual(replies[1]["total"], 2)
        self.assertFalse(replies[2]["ok"])

    def test_helper_entry_point_runs_as_a_process(self):
        main = os.path.join(os.path.dirname(__file__), "..", "main.py")
        req = json.dumps({"cmd": "search", "doc": "p", "paras": PARAS, "query": "ייחוד"}, ensure_ascii=False)
        proc = subprocess.run([sys.executable, main, "--doc-helper"], input=req + "\n", capture_output=True,
                              text=True, encoding="utf-8", timeout=120)
        reply = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(reply["total"], 3)


class DiskCacheTest(unittest.TestCase):
    """מפת החיפוש של מסמך נשמרת בדיסק לפי טביעת האצבע של הטקסט: בפתיחה הבאה לא שולחים ולא בונים שוב."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = os.path.join(self.tmp.name, "docs")
        self.levels = "".join(str(p["h"]) for p in PARAS)

    def service(self, keep=8):
        svc = docsearch.DocSearchService(keep=keep, cache_dir=self.dir)
        self.addCleanup(lambda: [e[k].close() for e in svc.docs.values() for k in (False, True) if k in e])
        return svc

    def test_second_session_needs_no_paragraphs(self):
        first = self.service()
        self.assertEqual(first.index({"doc": "T/l", "text": "12:ab", "levels": self.levels}),
                         {"ok": False, "need_paras": True})                    # עוד לא בדיסק
        r = first.index({"doc": "T/l", "text": "12:ab", "paras": PARAS})
        self.assertTrue(r["ok"] and r["cached"])
        self.assertEqual(len(os.listdir(self.dir)), 1)
        expected = first.search({"doc": "T/l", "query": "הלך", "options": {"forms": "all"}})

        second = self.service()                                                # Word נפתח מחדש
        real = docsearch.word_postings

        def only_headings(rows):                # מפת הכותרות (קטנה) נבנית בזיכרון; המלאה – לא נבנית שוב
            self.assertLessEqual(len(rows), 3, "the full map was built again")
            return real(rows)

        with mock.patch.object(docsearch, "word_postings", side_effect=only_headings):
            r = second.index({"doc": "T/l", "text": "12:ab", "levels": self.levels})
            self.assertTrue(r["ok"] and r["cached"])
            self.assertEqual((r["paras"], r["headings"]), (len(PARAS), 3))
            got = second.search({"doc": "T/l", "query": "הלך", "options": {"forms": "all"}})
        for key in ("total", "hits", "forms"):
            self.assertEqual(got[key], expected[key])
        heads = second.search({"doc": "T/l", "query": "הלך", "options": {"forms": "all"}, "headings_only": True})
        self.assertEqual([h["para"] for h in heads["hits"]], [0, 2])

    def test_search_request_alone_can_use_the_disk(self):
        self.service().index({"doc": "k", "text": "7:cd", "paras": PARAS})
        r = self.service().search({"doc": "k2", "text": "7:cd", "levels": "0" * len(PARAS), "query": "ייחוד"})
        self.assertEqual((r["ok"], r["total"], r["headings"]), (True, 3, 0))
        self.assertEqual(r["hits"][0]["path"], [])                              # הרמות – מהבקשה, לא מהדיסק

    def test_wrong_paragraph_count_asks_for_paragraphs(self):
        self.service().index({"doc": "k", "text": "7:cd", "paras": PARAS})
        self.assertEqual(self.service().index({"doc": "k", "text": "7:cd", "levels": "00"}),
                         {"ok": False, "need_paras": True})

    def test_damaged_file_is_rebuilt(self):
        svc = self.service()
        svc.index({"doc": "k", "text": "7:cd", "paras": PARAS})
        path = os.path.join(self.dir, os.listdir(self.dir)[0])
        for e in svc.docs.values():
            e[False].close()
        svc.docs.clear()
        with open(path, "wb") as f:
            f.write(b"not a database")
        again = self.service()
        self.assertEqual(again.index({"doc": "k", "text": "7:cd", "levels": self.levels}),
                         {"ok": False, "need_paras": True})
        self.assertTrue(again.index({"doc": "k", "text": "7:cd", "paras": PARAS})["cached"])
        self.assertEqual(again.search({"doc": "k", "query": "שבת"})["total"], 2)

    def test_relevel_keeps_using_the_file(self):
        svc = self.service()
        svc.index({"doc": "a/nolevels", "text": "9:ef", "paras": [dict(p, h=0) for p in PARAS]})
        r = svc.relevel({"from": "a/nolevels", "doc": "a/l", "levels": [int(c) for c in self.levels]})
        self.assertTrue(r["ok"])
        self.assertEqual(len(os.listdir(self.dir)), 1)
        self.assertIs(svc.docs["a/l"][False].db, svc.docs["a/nolevels"][False].db)
        self.assertEqual(svc.search({"doc": "a/l", "query": "הלך", "options": {"forms": "all"},
                                     "headings_only": True})["total"], 2)

    def test_old_files_are_removed(self):
        svc = self.service(keep=1)          # מסמך שיצא מהזיכרון נסגר – ב-Windows קובץ פתוח לא נמחק
        with mock.patch.object(docsearch, "CACHE_KEEP_FILES", 2):
            for i in range(4):
                svc.index({"doc": f"d{i}", "text": f"1:{i:02x}", "paras": [{"t": f"מסמך {i}", "h": 0}]})
                os.utime(os.path.join(self.dir, sorted(os.listdir(self.dir))[-1]), (1000 + i, 1000 + i))
        self.assertLessEqual(len(os.listdir(self.dir)), 3)                      # 2 + זה שנבנה עכשיו

    def test_without_text_hash_nothing_is_written(self):
        svc = self.service()
        self.assertEqual(svc.search({"doc": "m", "paras": PARAS, "query": "שבת"})["total"], 2)
        self.assertFalse(os.path.exists(self.dir) and os.listdir(self.dir))


if __name__ == "__main__":
    unittest.main()
