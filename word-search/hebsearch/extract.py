"""חילוץ טקסט ממסמכי וורד.

docx נקרא ישירות מתוך קובץ ה-ZIP (בלי python-docx) – מהיר יותר ומאפשר
לחלץ גם מספרי עמודים: וורד שומר בקובץ את הסימן lastRenderedPageBreak בכל
מקום שבו התחיל עמוד חדש בפעם האחרונה שהמסמך הוצג, כך שאפשר לדעת באיזה
עמוד נמצאת כל פסקה כפי שהמשתמש רואה אותה בוורד.

כל פסקה נשמרת כ- [טקסט, עמוד, סוג, מספר_הערה, שבירות_עמוד_בתוך_הפסקה]
ובקבצי PDF נוספים שדות: [..., מספר_השורה_הראשונה_בעמוד, היסטי_תחילת_שורות, גובה_כל_שורה_בדף].
"""

import posixpath
import sys
import zipfile
import xml.etree.ElementTree as ET

KIND_BODY, KIND_FOOTNOTE, KIND_ENDNOTE, KIND_TEXTBOX = 0, 1, 2, 3

DOCX_EXTS = {".docx", ".docm", ".dotx", ".dotm"}
DOC_EXTS = {".doc", ".dot", ".rtf"}
PDF_EXTS = {".pdf"}

_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


class _Walker:
    def __init__(self, ns: str, use_rendered: bool):
        self.w = ns
        self.use_rendered = use_rendered
        self.page = 1
        self.count_pages = True
        self.paras = []
        self._buf, self._breaks, self._len, self._start = [], [], 0, 1
        self.note_refs = {"footnote": {}, "endnote": {}}  # id -> (page, number)
        w = ns
        self.T, self.P, self.TAB, self.PTAB, self.BR, self.CR = (
            w + "t", w + "p", w + "tab", w + "ptab", w + "br", w + "cr")
        self.LRPB = w + "lastRenderedPageBreak"
        self.NBH = w + "noBreakHyphen"
        self.FNREF, self.ENREF = w + "footnoteReference", w + "endnoteReference"
        self.SKIP = {w + "del", w + "moveFrom", w + "instrText", w + "delText", w + "rPr",
                     w + "pPr", w + "sectPr", w + "tblPr", w + "trPr", w + "tcPr",
                     w + "tblGrid", w + "sdtPr", _MC_FALLBACK}

    # --- רמת בלוק ---
    def block(self, elem, kind, note=0):
        for ch in elem:
            if ch.tag == self.P:
                self.para(ch, kind, note)
            elif ch.tag not in self.SKIP:
                self.block(ch, kind, note)

    def _page_break(self):
        if not self.count_pages:
            return
        self.page += 1
        if self._len == 0:
            self._start = self.page
        else:
            self._breaks.append(self._len)

    def para(self, p, kind, note):
        saved = (self._buf, self._breaks, self._len, self._start)
        self._buf, self._breaks, self._len, self._start = [], [], 0, self.page
        ppr = p.find(self.w + "pPr")
        section_break = False
        if ppr is not None and not self.use_rendered:
            if ppr.find(self.w + "pageBreakBefore") is not None:
                self._page_break()
            sect = ppr.find(self.w + "sectPr")
            if sect is not None:
                t = sect.find(self.w + "type")
                section_break = t is None or t.get(self.w + "val") != "continuous"
        self.inline(p, kind, note)
        text = "".join(self._buf)
        if text.strip():
            self.paras.append([text, self._start, kind, note, self._breaks])
        self._buf, self._breaks, self._len, self._start = saved
        if section_break:
            self._page_break()

    def _add(self, s):
        if s:
            self._buf.append(s)
            self._len += len(s)

    # --- רמת שורה ---
    def inline(self, elem, kind, note):
        for ch in elem:
            tag = ch.tag
            if tag == self.T:
                self._add(ch.text)
            elif tag == self.TAB or tag == self.PTAB:
                self._add("\t")
            elif tag == self.BR:
                if ch.get(self.w + "type") == "page":
                    if not self.use_rendered:
                        self._page_break()
                    else:
                        self._add(" ")
                else:
                    self._add("\n")
            elif tag == self.CR:
                self._add("\n")
            elif tag == self.LRPB:
                if self.use_rendered:
                    self._page_break()
            elif tag == self.NBH:
                self._add("-")
            elif tag == self.P:
                self.para(ch, KIND_TEXTBOX if kind == KIND_BODY else kind, note)
            elif tag == self.FNREF or tag == self.ENREF:
                refs = self.note_refs["footnote" if tag == self.FNREF else "endnote"]
                nid = ch.get(self.w + "id")
                if nid is not None and nid not in refs:
                    refs[nid] = (self.page, len(refs) + 1)
            elif tag not in self.SKIP:
                self.inline(ch, kind, note)


def _rels(z: zipfile.ZipFile, part: str):
    base, name = posixpath.split(part)
    rels_path = posixpath.join(base, "_rels", name + ".rels")
    try:
        root = ET.fromstring(z.read(rels_path))
    except KeyError:
        return {}
    out = {}
    for r in root.iter(_REL + "Relationship"):
        rtype = r.get("Type", "").rsplit("/", 1)[-1]
        target = r.get("Target", "")
        if r.get("TargetMode") == "External":
            continue
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(base, target))
        out.setdefault(rtype, path)
    return out


def extract_docx(path: str):
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ValueError("הקובץ פגום או מוגן בסיסמה")
    with z:
        main = _rels(z, "").get("officeDocument", "word/document.xml")
        data = z.read(main)
        root = ET.fromstring(data)
        ns = root.tag[: root.tag.index("}") + 1] if root.tag.startswith("{") else ""
        walker = _Walker(ns, use_rendered=b"lastRenderedPageBreak" in data)
        body = root.find(ns + "body")
        if body is not None:
            walker.block(body, KIND_BODY)

        part_rels = _rels(z, main)
        walker.count_pages = False
        for rtype, kind in (("footnotes", KIND_FOOTNOTE), ("endnotes", KIND_ENDNOTE)):
            part = part_rels.get(rtype)
            if not part:
                continue
            try:
                nroot = ET.fromstring(z.read(part))
            except KeyError:
                continue
            refs = walker.note_refs[rtype[:-1]]
            for note in nroot:
                if note.get(ns + "type") not in (None, "normal"):
                    continue
                page, number = refs.get(note.get(ns + "id"), (0, 0))
                if not number:
                    continue
                walker.page = page
                walker.block(note, kind, number)
    return walker.paras


def extract_doc_com(path: str, word_app):
    """קבצי doc ישנים – דרך וורד עצמו (חלונות + pywin32 בלבד)."""
    doc = word_app.Documents.Open(path, ReadOnly=True, AddToRecentFiles=False, Visible=False)
    try:
        paras = []
        for line in doc.Content.Text.split("\r"):
            if line.strip():
                paras.append([line.replace("\x07", " ").replace("\x0b", "\n"), 0, KIND_BODY, 0, []])
        for i in range(1, doc.Footnotes.Count + 1):
            for line in doc.Footnotes(i).Range.Text.split("\r"):
                if line.strip():
                    paras.append([line, 0, KIND_FOOTNOTE, i, []])
        return paras
    finally:
        doc.Close(False)


def doc_support_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False
