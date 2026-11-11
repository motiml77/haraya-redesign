"""הכותרות של מסמך Word – ישירות מקובץ ה-docx, בלי Word (בשביל התוסף ל-Word).

חלונית הניווט של Word לא "מחפשת" כותרות: רמת החלוקה היא תכונה של הפסקה, שנשמרת בנפרד מהטקסט. גם
כאן קוראים אותה מהקובץ, בתהליך נפרד, כך ש-Word לא עושה שום עבודה:
  * רמת החלוקה של פסקה: w:outlineLvl בפסקה עצמה, ואם אין – של הסגנון שלה (כולל סגנונות שהוא מבוסס
    עליהם). הסגנונות המובנים "heading 1" עד "heading 9" הם תמיד ברמה 1–9, כמו ב-Word.
  * הטקסט של כל כותרת – כפי שהוא מופיע ב-Word (תוצאת שדות בלי קוד השדה, בלי תיבות טקסט בתוך הפסקה).
  * המקום המשוער של הכותרת ברשימת הפסקאות של Word (Range.Text): כל פסקה בגוף המסמך, כולל פסקאות בתוך
    טבלאות, ועוד פסקה ריקה אחת בסוף כל שורה בטבלה (סימן סוף השורה).
התוסף מתאים כל כותרת לפסקה שלה לפי הטקסט והמקום המשוער; מה שלא התאים – נבדק ב-Word.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

from .extract import DOCX_EXTS, _MC_FALLBACK, _rels

_HEADING_NAME = re.compile(r"^heading\s*([1-9])$", re.IGNORECASE)


class _Styles:
    """רמת החלוקה של כל סגנון פסקה (אחרי ירושה מ-basedOn)."""

    def __init__(self, root, w):
        self.w = w
        self.direct, self.based, self.default = {}, {}, None
        if root is None:
            return
        for st in root.iter(w + "style"):
            if st.get(w + "type") not in (None, "paragraph"):
                continue
            sid = st.get(w + "styleId")
            if not sid:
                continue
            if st.get(w + "default") in ("1", "true", "on"):
                self.default = sid
            name = st.find(w + "name")
            m = _HEADING_NAME.match((name.get(w + "val") or "") if name is not None else "")
            level = None
            ppr = st.find(w + "pPr")
            if ppr is not None:
                ol = ppr.find(w + "outlineLvl")
                if ol is not None:
                    level = _level(ol.get(w + "val"))
            if m:
                level = int(m.group(1))             # הסגנונות המובנים "כותרת N" – תמיד ברמה N
            self.direct[sid] = level
            based = st.find(w + "basedOn")
            if based is not None and based.get(w + "val"):
                self.based[sid] = based.get(w + "val")
        self._cache = {}

    def level(self, sid):
        """1–9, או 0 לגוף הטקסט."""
        if not sid:
            sid = self.default
        if not sid:
            return 0
        if sid in self._cache:
            return self._cache[sid]
        seen, cur, out = set(), sid, 0
        while cur and cur not in seen:
            seen.add(cur)
            lvl = self.direct.get(cur)
            if lvl is not None:
                out = lvl
                break
            cur = self.based.get(cur)
        self._cache[sid] = out
        return out


def _level(val):
    """ערך w:outlineLvl (0–8 רמות, 9 גוף הטקסט) → 1–9, או 0."""
    try:
        v = int(val)
    except (TypeError, ValueError):
        return 0
    return v + 1 if 0 <= v <= 8 else 0


class _Walker:
    def __init__(self, w, styles):
        self.w = w
        self.styles = styles
        self.index = 0                  # מספר הפסקה הבאה ברשימת הפסקאות של Word
        self.headings = []              # [טקסט, רמה, מקום משוער]
        self.P, self.TBL, self.TR, self.TC = w + "p", w + "tbl", w + "tr", w + "tc"
        self.T, self.TAB, self.PTAB, self.BR, self.CR = w + "t", w + "tab", w + "ptab", w + "br", w + "cr"
        self.NBH, self.SYM = w + "noBreakHyphen", w + "sym"
        self.TXBX = w + "txbxContent"
        self.SKIP = {w + "del", w + "moveFrom", w + "instrText", w + "delText", w + "rPr", w + "pPr",
                     w + "sectPr", w + "tblPr", w + "trPr", w + "tcPr", w + "tblGrid", w + "sdtPr",
                     w + "footnoteReference", w + "endnoteReference", self.TXBX, _MC_FALLBACK}

    def block(self, elem):
        for ch in elem:
            tag = ch.tag
            if tag == self.P:
                self.para(ch)
            elif tag == self.TBL:
                self.table(ch)
            elif tag not in self.SKIP:
                self.block(ch)

    def table(self, tbl):
        for ch in tbl:
            if ch.tag == self.TR:
                for cell in ch:
                    if cell.tag == self.TC:
                        self.block(cell)
                    elif cell.tag not in self.SKIP:          # תאים בתוך sdt / customXml
                        for inner in cell.iter(self.TC):
                            self.block(inner)
                self.index += 1                              # סימן סוף השורה – "פסקה" ריקה ב-Word
            elif ch.tag not in self.SKIP:
                for row in ch.iter(self.TR):                # שורות בתוך sdt / customXml
                    self.table([row])

    def para(self, p):
        ppr = p.find(self.w + "pPr")
        level = 0
        direct = None
        if ppr is not None:
            ol = ppr.find(self.w + "outlineLvl")
            if ol is not None:
                direct = _level(ol.get(self.w + "val"))
            ps = ppr.find(self.w + "pStyle")
            level = self.styles.level(ps.get(self.w + "val") if ps is not None else None)
        else:
            level = self.styles.level(None)
        if direct is not None:
            level = direct
        if level:
            buf = []
            self.inline(p, buf)
            text = "".join(buf)
            if text.strip():
                self.headings.append([text, level, self.index])
        self.index += 1

    def inline(self, elem, buf):
        for ch in elem:
            tag = ch.tag
            if tag == self.T:
                if ch.text:
                    buf.append(ch.text)
            elif tag == self.TAB or tag == self.PTAB:
                buf.append("\t")
            elif tag == self.BR or tag == self.CR:
                buf.append(" ")
            elif tag == self.NBH:
                buf.append("-")
            elif tag == self.P:                 # פסקה בתוך פסקה (תיבת טקסט בלי txbxContent) – לא חלק מהטקסט
                continue
            elif tag not in self.SKIP:
                self.inline(ch, buf)


def docx_headings(path: str):
    """{"headings": [[טקסט, רמה 1–9, מקום משוער], ...], "paras": מספר הפסקאות המשוער ב-Word}."""
    if posixpath.splitext(path.replace("\\", "/"))[1].lower() not in DOCX_EXTS:
        raise ValueError("not a docx file")
    with zipfile.ZipFile(path) as z:
        main = _rels(z, "").get("officeDocument", "word/document.xml")
        root = ET.fromstring(z.read(main))
        w = root.tag[: root.tag.index("}") + 1] if root.tag.startswith("{") else ""
        styles_part = _rels(z, main).get("styles")
        sroot = None
        if styles_part:
            try:
                sroot = ET.fromstring(z.read(styles_part))
            except KeyError:
                sroot = None
        walker = _Walker(w, _Styles(sroot, w))
        body = root.find(w + "body")
        if body is not None:
            walker.block(body)
    return {"headings": walker.headings, "paras": walker.index}
