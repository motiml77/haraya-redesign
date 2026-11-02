"""רכיב העזר של התוסף ל-Word: חיפוש בפסקאות של מסמך פתוח, עם מיקום מדויק של המילים."""

import io
import json
import os
import subprocess
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
