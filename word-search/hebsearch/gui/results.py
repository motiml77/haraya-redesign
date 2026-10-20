"""תצוגת התוצאות: כרטיסים מקובצים לפי קובץ, עם הדגשת המילים שנמצאו."""

import html
import os

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import QTextBrowser

from ..normalize import restore_finals
from ..search import SEG_GAP, SEG_MATCH, SEG_PARA

PAGE = 100

C_BG = "#f4f6fb"
C_CARD = "#ffffff"
C_FILE = "#e6edfb"
C_ACCENT = "#1d4ed8"
C_MUTED = "#64748b"
C_HL_BG = "#fde68a"
C_HL_FG = "#7c2d12"

SNIPPET_FONT = "'David', 'Frank Ruehl CLM', 'Frank Ruehl', 'Times New Roman', serif"


def _esc(s):
    return html.escape(s.replace("\t", " ").replace("\n", " "))


def ltr(s: str) -> str:
    """עוטף טקסט משמאל-לימין (נתיבים, יחידות) כדי שלא יתבלגן בתוך עברית."""
    return f"\u202a{s}\u202c"


def short_path(path: str, limit=40) -> str:
    """מקצר נתיב ארוך לתיקיות האחרונות שבו: …\\מסמכים\\תורה"""
    if len(path) <= limit:
        return path
    parts = path.replace("\\", "/").rstrip("/").split("/")
    sep = "\\" if "\\" in path else "/"
    tail = parts[-1]
    for part in reversed(parts[:-1]):
        if len(tail) + len(part) + 1 > limit:
            break
        tail = part + sep + tail
    return "…" + sep + tail


def doc_name(path: str) -> str:
    """שם המסמך בלי סיומת – הסיומת הלטינית משבשת את כיווניות השם."""
    return os.path.splitext(os.path.basename(path))[0]


# Qt לא מסדר עמודות טבלה מימין לשמאל, ולכן העמודה הימנית נכתבת אחרונה
SYNTAX_TABLE = f"""
<table align="right" cellpadding="4" cellspacing="0">
<tr><td align="right" style="color:{C_MUTED}">כוכבית – כל רצף אותיות (הלכה, הלכות, הלכתא…)</td><td align="right"><b>הלכ*</b></td></tr>
<tr><td align="right" style="color:{C_MUTED}">סימן שאלה – אות אחת כלשהי (משה, משל…)</td><td align="right"><b>מש?</b></td></tr>
<tr><td align="right" style="color:{C_MUTED}">קו אנכי – אחת מהמילים</td><td align="right"><b>משה|אהרן</b></td></tr>
<tr><td align="right" style="color:{C_MUTED}">מינוס – פסקאות עם 'שבת' שאין בהן 'חול'</td><td align="right"><b>שבת &nbsp;-חול</b></td></tr>
</table>"""


WELCOME = f"""
<div dir="rtl" style="color:#334155; font-size:11pt">
<p style="font-size:17pt; font-weight:bold; color:{C_ACCENT}; margin-bottom:4px">ברוכים הבאים</p>
<p style="color:{C_MUTED}; margin-top:0">חיפוש מהיר וגמיש בתוך מסמכי וורד בעברית</p>
<table align="right" cellpadding="6">
<tr><td align="right"><b>מלאו את הסל</b> – הוסיפו תיקיות או קבצים בודדים (אפשר גם לגרור לכאן מהסייר).</td><td style="font-size:15pt; color:{C_ACCENT}">①</td></tr>
<tr><td align="right"><b>המפה נבנית לבד</b> – בפעם הראשונה כל מסמך נקרא פעם אחת; אחר כך רק מסמכים שהשתנו.</td><td style="font-size:15pt; color:{C_ACCENT}">②</td></tr>
<tr><td align="right"><b>חפשו</b> – הניקוד והסימנים מתעלמים מעצמם. לחיצה על תוצאה פותחת את המסמך במקום.</td><td style="font-size:15pt; color:{C_ACCENT}">③</td></tr>
</table>
<p style="color:#334155; margin-top:16px; margin-bottom:2px"><b>חיפוש מתקדם</b></p>
{SYNTAX_TABLE}
</div>
"""


class ResultsView(QTextBrowser):
    hitClicked = Signal(object)        # Hit
    fileClicked = Signal(str)          # נתיב
    folderClicked = Signal(str)        # נתיב

    def __init__(self, materialize, parent=None):
        super().__init__(parent)
        self._materialize = materialize
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._on_anchor)
        self.document().setDocumentMargin(14)
        self.result = None
        self.hits = []
        self.shown = 0
        self._paths = {}
        self.show_message(WELCOME)

    def show_message(self, body_html):
        self.result, self.hits, self.shown = None, [], 0
        self.setHtml(f'<html><body dir="rtl" style="background:{C_BG}">{body_html}</body></html>')

    def show_hits(self, result, hits):
        self.result, self.hits = result, hits
        self.shown = min(PAGE, len(hits))
        self._render()
        self.verticalScrollBar().setValue(0)

    def _render(self, keep_scroll=False):
        pos = self.verticalScrollBar().value()
        parts = [f'<html><body dir="rtl" style="background:{C_BG}">']
        last_file = None
        counts = {fid: c for fid, _, c in self.result.files} if self.result else {}
        self._paths = {}
        for i, hit in enumerate(self.hits[: self.shown]):
            self._materialize(hit)
            if hit.file_id != last_file:
                last_file = hit.file_id
                self._paths[hit.file_id] = hit.path
                parts.append(self._file_header(hit, counts.get(hit.file_id, 0)))
            parts.append(self._card(i, hit))
        if self.shown < len(self.hits):
            rest = len(self.hits) - self.shown
            parts.append(
                f'<p align="center" style="margin:18px"><a href="more:" style="color:{C_ACCENT}; '
                f'font-size:12pt; font-weight:bold; text-decoration:none">הצג עוד {min(PAGE, rest):,} '
                f'תוצאות (נותרו {rest:,}) ▾</a></p>')
        parts.append("</body></html>")
        self.setHtml("".join(parts))
        if keep_scroll:
            self.verticalScrollBar().setValue(pos)

    def _file_header(self, hit, count):
        name = _esc(doc_name(hit.path))
        folder = _esc(ltr(os.path.dirname(hit.path)))
        word = "תוצאה" if count == 1 else "תוצאות"
        return (
            f'<table width="100%" cellspacing="0" cellpadding="9" style="background:{C_FILE}; margin-top:16px">'
            f'<tr><td><span style="font-size:13pt; font-weight:bold; color:#1e3a8a">📄 {name}</span>'
            f'<span style="color:{C_MUTED}">&nbsp;&nbsp;·&nbsp;&nbsp;{count:,} {word}</span><br>'
            f'<span style="color:{C_MUTED}; font-size:8.5pt">{folder}</span></td>'
            f'<td align="left" style="white-space:nowrap">'
            f'<a href="file:{hit.file_id}" style="color:{C_ACCENT}; text-decoration:none">פתח מסמך</a>'
            f'<span style="color:#94a3b8">&nbsp; | &nbsp;</span>'
            f'<a href="dir:{hit.file_id}" style="color:{C_ACCENT}; text-decoration:none">הצג בתיקייה</a>'
            f'</td></tr></table>')

    def _card(self, i, hit):
        segs = []
        for text, kind in hit.snippet:
            t = _esc(text)
            if kind == SEG_MATCH:
                segs.append(f'<span style="background:{C_HL_BG}; color:{C_HL_FG}; font-weight:bold">{t}</span>')
            elif kind == SEG_PARA:
                segs.append('<span style="color:#cbd5e1"> ¶ </span>')
            elif kind == SEG_GAP:
                segs.append(f'<span style="color:#94a3b8">{t}</span>')
            else:
                segs.append(t)
        return (
            f'<table width="100%" cellspacing="0" cellpadding="10" style="background:{C_CARD}; margin-top:3px">'
            f'<tr><td>'
            f'<a href="hit:{i}" style="color:{C_ACCENT}; text-decoration:none; font-weight:bold">'
            f'<span style="color:#94a3b8; font-weight:normal">{i + 1}.</span>&nbsp; {_esc(hit.location)}'
            f'&nbsp; <span style="font-weight:normal">↗ פתח כאן</span></a>'
            f'<p dir="rtl" style="font-family:{SNIPPET_FONT}; font-size:15pt; margin-top:5px; margin-bottom:0; '
            f'line-height:140%">{"".join(segs)}</p>'
            f'</td></tr></table>')

    def _on_anchor(self, url: QUrl):
        s = url.toString()
        kind, _, arg = s.partition(":")
        if kind == "more":
            self.shown = min(len(self.hits), self.shown + PAGE)
            self._render(keep_scroll=True)
        elif kind == "hit":
            self.hitClicked.emit(self.hits[int(arg)])
        elif kind in ("file", "dir"):
            path = self._paths.get(int(arg))
            if path:
                (self.fileClicked if kind == "file" else self.folderClicked).emit(path)


def form_of(word):
    return restore_finals(word)
