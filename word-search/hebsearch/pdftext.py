"""חילוץ טקסט עברי מ-PDF.

בקבצי PDF הטקסט שמור כאוסף של תווים במיקומים על הדף, ולא תמיד בסדר
הקריאה: יש מחוללים ששומרים עברית בסדר חזותי (הפוך), יש ששוברים כל מילה
לקטע נפרד, ומספרים בתוך שורה עברית יוצאים לרוב במקום הלא נכון.

לכן לא סומכים על סדר התווים בקובץ אלא על המיקום שלהם:
  1. כל תו (עם הניקוד שצמוד אליו) נאסף עם מיקומו.
  2. התווים מקובצים לשורות לפי קו הבסיס וממוינים משמאל לימין – זה הסדר
     החזותי האמיתי, בלי קשר לאיך שהקובץ נכתב.
  3. שורה עברית הופכת לסדר לוגי: היפוך, ואז החזרת רצפי ספרות/לועזית
     לכיוונם המקורי והחלפת סוגריים.
יחידת החיפוש ב-PDF היא עמוד שלם (חלוקת הבלוקים של PDF היא עניין של
עימוד ולא של תוכן – צירוף מילים נשבר בה בקלות). לכל שורה נשמר המיקום
שלה בטקסט העמוד ומיקומה האנכי על הדף, כך שלכל תוצאה מוצגים עמוד ושורה,
ולחיצה עליה מגיעה בדיוק לגובה השורה בעמוד.
"""

import re
import unicodedata

from .extract import KIND_BODY

_HEB = re.compile("[א-תיִ-ﭏ]")
_LAT = re.compile("[A-Za-zÀ-ɏ]")
_LTR_STRONG = re.compile("[0-9A-Za-zÀ-ɏ]")
_LTR_INNER = set(".,:/%-+'")
_MIRROR = str.maketrans("()[]{}<>", ")(][}{><")
# רווחים מיוחדים (רווח קשיח וכו') – יש גופנים/מחוללים שמדווחים כך על כל רווח
_SPACES = set("\u00a0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000")


def _is_mark(ch):
    return unicodedata.combining(ch) or "֑" <= ch <= "ׇ" and ch not in "־׀׃׆"


class _Cluster:
    __slots__ = ("text", "x0", "x1", "y", "size")

    def __init__(self, text, x0, x1, y, size):
        self.text, self.x0, self.x1, self.y, self.size = text, x0, x1, y, size


def _clusters(block):
    out = []
    for line in block.get("lines", ()):
        for span in line.get("spans", ()):
            size = span.get("size", 10) or 10
            for ch in span.get("chars", ()):
                c = ch["c"]
                if not c:
                    continue
                if c in _SPACES:
                    c = " "
                if _is_mark(c) and out:
                    out[-1].text += c
                    continue
                x0, _, x1, _ = ch["bbox"]
                out.append(_Cluster(c, x0, x1, ch["origin"][1], size))
    return out


def _rows(clusters):
    """קיבוץ לשורות לפי קו הבסיס; כל שורה ממוינת משמאל לימין."""
    rows = []
    for cl in sorted(clusters, key=lambda c: c.y):
        if rows and abs(rows[-1][0].y - cl.y) <= 0.45 * max(cl.size, rows[-1][0].size):
            rows[-1].append(cl)
        else:
            rows.append([cl])
    return [sorted(r, key=lambda c: (c.x0 + c.x1) / 2) for r in rows]


def _visual_units(row):
    """רשימת יחידות בסדר חזותי, עם רווחים היכן שיש פער בין תווים."""
    units = []
    prev = None
    for cl in row:
        if prev is not None and cl.x0 - prev.x1 > 0.22 * cl.size:
            if units and units[-1] != " " and cl.text != " ":
                units.append(" ")
        if cl.text == " " and units and units[-1] == " ":
            continue
        units.append(cl.text)
        prev = cl
    return units


def _is_ltr_unit(u):
    return bool(_LTR_STRONG.match(u))


def visual_to_logical(units, rtl):
    """הופך יחידות בסדר חזותי לסדר קריאה."""
    if not rtl:
        units = list(units)
        out, i = [], 0
        while i < len(units):
            if _HEB.match(units[i]):
                j = i
                while j < len(units) and (_HEB.match(units[j]) or units[j] == " " and j + 1 < len(units)
                                          and _HEB.match(units[j + 1])):
                    j += 1
                out.extend(reversed(units[i:j]))
                i = j
            else:
                out.append(units[i])
                i += 1
        return "".join(out)
    rev = list(reversed(units))
    out, i = [], 0
    while i < len(rev):
        if _is_ltr_unit(rev[i]):
            j = i + 1
            while j < len(rev) and (_is_ltr_unit(rev[j]) or (rev[j] in _LTR_INNER and j + 1 < len(rev)
                                                           and _is_ltr_unit(rev[j + 1]))):
                j += 1
            out.extend(reversed(rev[i:j]))
            i = j
        else:
            out.append(rev[i].translate(_MIRROR))
            i += 1
    return "".join(out)


def _row_text(row):
    units = _visual_units(row)
    joined = "".join(units)
    rtl = len(_HEB.findall(joined)) >= len(_LAT.findall(joined))
    return visual_to_logical(units, rtl).strip()


def extract_pdf(path):
    import pymupdf

    flags = pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP | pymupdf.TEXT_PRESERVE_LIGATURES
    paras = []
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("הקובץ מוגן בסיסמה")
        for pno, page in enumerate(doc, 1):
            blocks = []
            for b in page.get_text("rawdict", flags=flags)["blocks"]:
                if b.get("type") != 0:
                    continue
                rows = _rows(_clusters(b))
                if not rows:
                    continue
                last = blocks[-1] if blocks else None
                # מחוללים ששוברים שורה לכמה בלוקים (מילה-מילה): מאחדים לשורה אחת
                if (last and len(rows) == 1 and abs(last[-1][0].y - rows[0][0].y) <= 0.45 * rows[0][0].size
                        and _gap(last[-1], rows[0]) < 3 * rows[0][0].size):
                    last[-1] = sorted(last[-1] + rows[0], key=lambda c: (c.x0 + c.x1) / 2)
                else:
                    blocks.append(rows)
            lines, tops = [], []
            for rows in blocks:
                for r in rows:
                    t = _row_text(r)
                    if t:
                        lines.append(t)
                        tops.append(round(min(c.y - c.size for c in r), 1))   # ראש השורה, בנקודות
            if not lines:
                continue
            offsets, pos = [], 0
            for ln in lines:
                offsets.append(pos)
                pos += len(ln) + 1
            paras.append(["\n".join(lines), pno, KIND_BODY, 0, [], 1, offsets, tops])
    if not paras:
        raise ValueError("אין בקובץ טקסט (ייתכן שזה מסמך סרוק)")
    return paras


def _gap(row_a, row_b):
    a0, a1 = min(c.x0 for c in row_a), max(c.x1 for c in row_a)
    b0, b1 = min(c.x0 for c in row_b), max(c.x1 for c in row_b)
    return max(b0 - a1, a0 - b1, 0)
