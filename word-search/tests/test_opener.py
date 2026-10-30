"""בדיקת אלגוריתם הניווט בוורד מול אובייקט מדומה שמתנהג כמו Range/Find של וורד."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hebsearch.opener import _locate_in_word  # noqa: E402


class FakeFind:
    def __init__(self, rng):
        self.rng = rng
        self.MatchDiacritics = True

    def ClearFormatting(self):
        pass

    def Execute(self, text, *args):
        text = text.replace("^t", "\t").replace("^l", "\n").replace("^^", "^")
        doc = self.rng.doc
        end = self.rng.end if self.rng.end > self.rng.start else len(doc.text)  # טווח מכווץ: עד סוף המסמך
        i = doc.text.find(text, self.rng.start, end)
        if i < 0:
            return False
        self.rng.start, self.rng.end = i, i + len(text)
        return True


class FakeRange:
    def __init__(self, doc, start, end):
        self.doc, self.start, self.end = doc, start, end
        self.Find = FakeFind(self)

    @property
    def Start(self):
        return self.start

    @property
    def End(self):
        return self.end

    def Collapse(self, direction):
        self.start = self.end


class FakeDoc:
    def __init__(self, text):
        self.text = text

    @property
    def Content(self):
        return FakeRange(self, 0, len(self.text))

    def Range(self, start, end):
        return FakeRange(self, start, end)


class WordNavigationTest(unittest.TestCase):
    TEXT = "שלום עולם.\rשלום לכם.\rוהנה שלום עולם שוב.\r"

    def test_nth_occurrence(self):
        doc = FakeDoc(self.TEXT)
        rng, found = _locate_in_word(doc, [("שלום עולם", 1)], 0, 0, None)
        self.assertEqual((found, rng.Start), ("שלום עולם", self.TEXT.rindex("שלום עולם")))

    def test_falls_back_to_shorter_needle(self):
        doc = FakeDoc(self.TEXT)
        rng, found = _locate_in_word(doc, [("שלום חברים", 0), ("שלום", 2)], 0, 0, None)
        self.assertEqual((found, rng.Start), ("שלום", self.TEXT.rindex("שלום")))

    def test_ratio_fallback_when_count_is_off(self):
        # וורד רואה טקסט נוסף (למשל שינוי במעקב) – הספירה לא מתאימה, המיקום היחסי מציל
        text = "א " * 2000 + "מילה " + "ב " * 2000 + "מילה " + "ג " * 2000
        doc = FakeDoc(text)
        second = text.rindex("מילה")
        rng, found = _locate_in_word(doc, [("מילה", 5)], 0, 0, second / len(text))
        self.assertEqual(rng.Start, second)

    def test_not_found(self):
        self.assertEqual(_locate_in_word(FakeDoc(self.TEXT), [("אין", 0)], 0, 0, 0.5), (None, None))


if __name__ == "__main__":
    unittest.main()
