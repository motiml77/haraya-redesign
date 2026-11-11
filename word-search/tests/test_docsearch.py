"""רכיב העזר של התוסף ל-Word: חיפוש בפסקאות של מסמך פתוח, עם מיקום מדויק של המילים."""

import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hebsearch import docsearch  # noqa: E402
from hebsearch.docheadings import docx_headings  # noqa: E402
from hebsearch.extract import KIND_BODY  # noqa: E402
from hebsearch.index import word_postings  # noqa: E402

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
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"HEBSEARCH_DATA": d}):
            docsearch.serve(io.StringIO(lines), out)
        replies = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertTrue(replies[0]["ok"])
        self.assertEqual(replies[1]["total"], 2)
        self.assertFalse(replies[2]["ok"])

    def test_helper_entry_point_runs_as_a_process(self):
        main = os.path.join(os.path.dirname(__file__), "..", "main.py")
        req = json.dumps({"cmd": "search", "doc": "p", "paras": PARAS, "query": "ייחוד"}, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run([sys.executable, main, "--doc-helper"], input=req + "\n", capture_output=True,
                                  text=True, encoding="utf-8", timeout=120, env=dict(os.environ, HEBSEARCH_DATA=d))
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
        real = docsearch.normalize_paras

        def only_headings(texts, *a, **kw):     # מפת הכותרות (קטנה) נבנית בזיכרון; המלאה – לא נבנית שוב
            self.assertLessEqual(len(texts), 3, "the full map was built again")
            return real(texts, *a, **kw)

        with mock.patch.object(docsearch, "normalize_paras", side_effect=only_headings):
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

    def test_documents_not_opened_for_three_days_are_removed(self):
        svc = self.service(keep=1)          # מסמך שיצא מהזיכרון נסגר – ב-Windows קובץ פתוח לא נמחק
        for i in range(3):
            svc.index({"doc": f"d{i}", "text": f"1:{i:02x}", "paras": [{"t": f"מסמך {i}", "h": 0}]})
        files = {name: os.path.join(self.dir, name) for name in os.listdir(self.dir)}
        self.assertEqual(len(files), 3)
        day = 24 * 3600
        now = time.time()
        old, recent, current = sorted(files.values())
        os.utime(old, (now - 3 * day - 60, now - 3 * day - 60))           # לא נפתח 3 ימים ודקה
        os.utime(recent, (now - 2 * day, now - 2 * day))
        svc.cache.cleanup(now=now)
        self.assertEqual(sorted(os.listdir(self.dir)), sorted(os.path.basename(p) for p in (recent, current)))
        # פתיחה מחדש של מסמך = שימוש: הספירה של שלושת הימים מתחילה מחדש
        text = next(t for t in ("1:00", "1:01", "1:02") if svc.cache.file(t) == recent)
        again = self.service()
        self.assertTrue(again.index({"doc": "x", "text": text, "levels": "0"})["cached"])
        self.assertGreater(os.path.getmtime(recent), now - 60)

    def test_without_text_hash_nothing_is_written(self):
        svc = self.service()
        self.assertEqual(svc.search({"doc": "m", "paras": PARAS, "query": "שבת"})["total"], 2)
        self.assertFalse(os.path.exists(self.dir) and os.listdir(self.dir))


def big_doc(n=400, seed=7):
    import random
    rnd = random.Random(seed)
    words = ["הלכה", "שבת", "ההולך", "בְּשַׁבָּת", "רש\"י", "Word", "2016", "מוקצה", "ביום", "טוב", "קלתה", "אבן",
             "העזר", "סימן", "קט\"ו", "פרק", "סיכום", "דיני", "איסור", "ייחוד"]
    return [{"t": " ".join(rnd.choice(words) for _ in range(rnd.randint(0, 25))), "h": 1 if i % 37 == 0 else 0}
            for i in range(n)]


class PatchTest(unittest.TestCase):
    """אחרי עריכה נשלחות רק הפסקאות שהשתנו, והמילים של השאר לא מנורמלות שוב – והתוצאה זהה לבנייה מלאה."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = os.path.join(self.tmp.name, "docs")

    def service(self, cache=True):
        svc = docsearch.DocSearchService(cache_dir=self.dir if cache else None)
        self.addCleanup(lambda: [e[k].close() for e in svc.docs.values() for k in (False, True) if k in e])
        return svc

    @staticmethod
    def levels(paras):
        return "".join(str(p["h"]) for p in paras)

    def edited(self, v1):
        """עריכה: פסקה אחת שונתה, אחת נוספה, אחת נמחקה – ומה התוסף ישלח."""
        v2 = [dict(p) for p in v1]
        v2[10] = {"t": "פסקה ששונתה עם המילה זברה", "h": 0}
        v2.insert(50, {"t": "פסקה חדשה לגמרי עם זברה", "h": 2})
        del v2[200]
        ops = [[0, 10], v2[10]["t"], [11, 39], v2[50]["t"], [50, 149], [200, len(v1) - 200]]
        return v2, ops

    def compare(self, a, b, key_a, key_b):
        for q, kw in (("זברה", {}), ("הלך", {"options": {"forms": "all"}}), ("שבת", {"headings_only": True}),
                      ("דיני איסור", {"options": {"distance": "near", "near": 3}})):
            ra = a.search(dict({"doc": key_a, "query": q}, **kw))
            rb = b.search(dict({"doc": key_b, "query": q}, **kw))
            self.assertEqual((ra["total"], ra["hits"], ra["forms"]), (rb["total"], rb["hits"], rb["forms"]), q)

    def test_postings_from_saved_words_equal_a_full_build(self):
        rows = [[p["t"], 0, KIND_BODY, 0, []] for p in big_doc()]
        norms = docsearch.normalize_paras([r[0] for r in rows])
        self.assertEqual(docsearch.postings_from_norms(norms), word_postings(rows))

    def test_patch_gives_the_same_results_as_a_full_build(self):
        v1 = big_doc()
        v2, ops = self.edited(v1)
        svc = self.service(cache=False)
        svc.index({"doc": "v1", "text": "1:a", "paras": v1})
        r = svc.patch({"doc": "v2", "text": "1:b", "base": "1:a", "ops": ops, "levels": self.levels(v2)})
        self.assertTrue(r["ok"])
        self.assertEqual((r["paras"], r["normalized"], r["reused"]), (len(v2), 2, len(v2) - 2))
        self.assertNotIn("v1", svc.docs)                                   # הגרסה הקודמת שוחררה מהזיכרון
        fresh = self.service(cache=False)
        fresh.index({"doc": "f", "paras": v2})
        self.compare(svc, fresh, "v2", "f")
        # עריכה נוספת על הגרסה שנבנתה בעדכון חלקי
        v3 = [dict(p) for p in v2]
        v3[0] = {"t": "כותרת חדשה", "h": 1}
        r = svc.patch({"doc": "v3", "text": "1:c", "base": "1:b", "ops": ["כותרת חדשה", [1, len(v2) - 1]],
                       "levels": self.levels(v3)})
        self.assertEqual(r["normalized"], 1)
        fresh.index({"doc": "f3", "paras": v3})
        self.compare(svc, fresh, "v3", "f3")

    def test_patch_from_the_disk_in_a_new_session(self):
        v1 = big_doc()
        self.service().index({"doc": "v1", "text": "1:a", "paras": v1})          # נפתח בפעם קודמת
        v2, ops = self.edited(v1)
        svc = self.service()                                                     # Word נפתח מחדש
        real = docsearch.normalize_paras
        counted = []

        def count(texts, reuse=None, progress=None):
            counted.append(len(texts) - len(reuse or {}))
            return real(texts, reuse, progress)

        with mock.patch.object(docsearch, "normalize_paras", side_effect=count):
            r = svc.patch({"doc": "v2", "text": "1:b", "base": "1:a", "ops": ops, "levels": self.levels(v2)})
        self.assertTrue(r["ok"])
        self.assertEqual(counted[0], 2)                                          # רק שתי הפסקאות החדשות
        fresh = self.service(cache=False)
        fresh.index({"doc": "f", "paras": v2})
        self.compare(svc, fresh, "v2", "f")

    def test_unknown_base_or_bad_ops_ask_for_paragraphs(self):
        svc = self.service()
        need = {"ok": False, "need_paras": True}
        self.assertEqual(svc.patch({"doc": "x", "text": "2:b", "base": "2:a", "ops": [], "levels": ""}), need)
        svc.index({"doc": "a", "text": "2:a", "paras": PARAS})
        self.assertEqual(svc.patch({"doc": "x", "text": "2:b", "base": "2:a", "ops": [[0, 99]], "levels": "0"}), need)
        self.assertEqual(svc.patch({"doc": "x", "text": "2:b", "base": "2:a", "ops": [[0, 2]], "levels": "0"}), need)

    def test_persist_on_close_makes_the_next_session_instant(self):
        v1 = big_doc()
        v2, ops = self.edited(v1)
        svc = self.service()
        svc.index({"doc": "v1", "text": "1:a", "paras": v1})
        svc.patch({"doc": "v2", "text": "1:b", "base": "1:a", "ops": ops, "levels": self.levels(v2)})
        self.assertFalse(svc.cache.has("1:b"))                                   # בזמן העבודה – רק בזיכרון
        self.assertEqual(svc.persist({"doc": "v2"}), {"ok": True, "saved": True})
        self.assertTrue(svc.cache.has("1:b"))
        again = self.service()
        r = again.index({"doc": "v2", "text": "1:b", "levels": self.levels(v2)})
        self.assertTrue(r["ok"] and r["cached"])
        fresh = self.service(cache=False)
        fresh.index({"doc": "f", "paras": v2})
        self.compare(again, fresh, "v2", "f")
        # ומשם אפשר להמשיך בעדכון חלקי (המילים המנורמלות נשמרו גם הן)
        r = again.patch({"doc": "v3", "text": "1:c", "base": "1:b", "ops": ["חדש", [1, len(v2) - 1]],
                         "levels": "0" + self.levels(v2)[1:]})
        self.assertEqual(r["normalized"], 1)

    def test_progress_lines_before_the_reply(self):
        lines = "\n".join([json.dumps({"cmd": "index", "doc": "p", "paras": big_doc(9000), "progress": True},
                                      ensure_ascii=False), json.dumps({"cmd": "quit"})]) + "\n"
        out = io.StringIO()
        with mock.patch.object(docsearch, "PROGRESS_INTERVAL", 0.0), \
                mock.patch.dict(os.environ, {"HEBSEARCH_DATA": self.tmp.name}):
            docsearch.serve(io.StringIO(lines), out)
        replies = [json.loads(x) for x in out.getvalue().splitlines()]
        steps = [r["progress"] for r in replies if "progress" in r]
        self.assertGreaterEqual(len(steps), 3)
        self.assertEqual(steps, sorted(steps))
        self.assertTrue(replies[-1]["ok"])


def make_docx(path, body, styles):
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="r1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/relationships"><Relationship Id="r2" Type="http://schemas.'
                   'openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {w}><w:body>{body}</w:body></w:document>')
        z.writestr("word/styles.xml", f'<?xml version="1.0"?><w:styles {w}>{styles}</w:styles>')


def para(text, style=None, outline=None, extra=""):
    ppr = ""
    if style or outline is not None:
        ppr = "<w:pPr>" + (f'<w:pStyle w:val="{style}"/>' if style else "") + \
              (f'<w:outlineLvl w:val="{outline}"/>' if outline is not None else "") + "</w:pPr>"
    return f"<w:p>{ppr}<w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r>{extra}</w:p>"


class DocxHeadingsTest(unittest.TestCase):
    """הכותרות מקובץ ה-docx (בלי Word): לפי הסגנון והירושה שלו, רמת חלוקה ישירה, ובטבלאות."""

    def test_levels_texts_and_positions(self):
        styles = (
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="1"><w:name w:val="heading 1"/></w:style>'           # בלי outlineLvl
            '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
            '<w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="MyTitle"><w:name w:val="כותרת שלי"/>'
            '<w:basedOn w:val="Heading2"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/>'
            '<w:pPr><w:outlineLvl w:val="2"/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Plain"><w:name w:val="Plain"/>'
            '<w:basedOn w:val="Quote"/><w:pPr><w:outlineLvl w:val="9"/></w:pPr></w:style>')
        field = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r>'
                 '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>7</w:t></w:r>'
                 '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
        textbox = ('<w:r><w:pict><w:txbxContent>' + para("טקסט בתיבה", "1") + '</w:txbxContent></w:pict></w:r>')
        cell = lambda inner: f"<w:tc>{inner}</w:tc>"                                      # noqa: E731
        body = (para("פרק ראשון", "1")                                    # 0  כותרת 1 (שם הסגנון)
                + para("גוף")                                              # 1
                + para("סעיף א", "Heading2")                               # 2  כותרת 2
                + para("כותרת אישית", "MyTitle")                           # 3  יורשת רמה 2
                + para("ציטוט עם רמה", "Quote")                            # 4  רמה 3 מהסגנון
                + para("רגיל", "Plain")                                    # 5  רמה 9 = גוף (דורסת את הירושה)
                + para("ישירה", None, outline=0)                           # 6  רמה 1 ישירה
                + para("סעיף", "Heading2", outline=9)                      # 7  ישירה "גוף" דורסת את הסגנון
                + f"<w:tbl><w:tr>{cell(para('תא 1'))}{cell(para('כותרת בתא', '1') + para('שנייה בתא'))}</w:tr>"
                f"<w:tr>{cell(para('תא 3'))}{cell(para('תא 4'))}</w:tr></w:tbl>"   # 8, 9, 10, [11]; 12, 13, [14]
                + para("עמוד ", "Heading2", extra=field)                   # 15 – תוצאת השדה בלי הקוד
                + para("עם תיבה", "1", extra=textbox)                      # 16 – בלי הטקסט שבתיבה
                + para("", "1")                                            # 17 – כותרת ריקה לא נספרת
                + para("אחרונה"))                                          # 18
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "doc.docx")
            make_docx(path, body, styles)
            out = docx_headings(path)
            svc = docsearch.DocSearchService()
            self.assertEqual(svc.docx_headings({"path": path})["headings"], out["headings"])
        self.assertEqual(out["paras"], 19)
        self.assertEqual(out["headings"], [
            ["פרק ראשון", 1, 0], ["סעיף א", 2, 2], ["כותרת אישית", 2, 3], ["ציטוט עם רמה", 3, 4],
            ["ישירה", 1, 6], ["כותרת בתא", 1, 9], ["עמוד 7", 2, 15], ["עם תיבה", 1, 16]])

    def test_not_a_docx(self):
        r = docsearch.handle(docsearch.DocSearchService(), json.dumps({"cmd": "docx_headings", "path": "x.doc"}))
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
