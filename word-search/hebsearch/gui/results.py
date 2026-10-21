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
C_HL_BG = "#fff200"   # מרקר צהוב
C_HL_FG = "#111111"

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
<p style="color:{C_MUTED}; margin-top:0">חיפוש מהיר וגמיש בתוך מסמכי Word ו-PDF בעברית</p>
<table align="right" cellpadding="6">
<tr><td align="right"><b>צרו סלים</b> – לכל סל שם משלו (שיעורים, תורה…), ובו תיקיות ומסמכי Word או PDF. אפשר לגרור מהסייר.</td><td style="font-size:15pt; color:{C_ACCENT}">①</td></tr>
<tr><td align="right"><b>המפה נבנית לבד</b> – בפעם הראשונה כל מסמך נקרא פעם אחת; אחר כך רק מסמכים שהשתנו.</td><td style="font-size:15pt; color:{C_ACCENT}">②</td></tr>
<tr><td align="right"><b>בחרו סלים וחפשו</b> – לחיצה על שם סל מעל תיבת החיפוש מכלילה או מוציאה אותו. התוצאות המדויקות ביותר ראשונות, ולחיצה על תוצאה פותחת את המסמך במקום.</td><td style="font-size:15pt; color:{C_ACCENT}">③</td></tr>
</table>
<p style="color:#334155; margin-top:16px; margin-bottom:2px"><b>חיפוש מתקדם</b></p>
{SYNTAX_TABLE}
</div>
"""


def _meter(score):
    """מד התאמה של 5 נקודות."""
    n = max(1, min(5, round(score * 5)))
    return (f'<span style="color:#22c55e">{"●" * n}</span>'
            f'<span style="color:#d1d5db">{"●" * (5 - n)}</span>')


class ResultsView(QTextBrowser):
    hitClicked = Signal(object)        # Hit – פתיחה במקום
    hitPreview = Signal(object)        # Hit – תצוגה מובנית
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
        self.grouped = False
        self._paths = {}
        self.show_message(WELCOME)

    def show_message(self, body_html):
        self.result, self.hits, self.shown = None, [], 0
        self.setHtml(f'<html><body dir="rtl" style="background:{C_BG}">{body_html}</body></html>')

    def show_hits(self, result, hits, grouped):
        """grouped=True: מקובץ לפי מסמך; אחרת רשימה אחת לפי דירוג."""
        self.result, self.hits, self.grouped = result, hits, grouped
        self.shown = min(PAGE, len(hits))
        self._render()
        self.verticalScrollBar().setValue(0)

    def _render(self, keep_scroll=False):
        pos = self.verticalScrollBar().value()
        parts = [f'<html><body dir="rtl" style="background:{C_BG}">']
        last_file = None
        counts = {fid: c for fid, _, c in self.result.files} if self.result else {}
        highlight = self.result.highlight if self.result else frozenset()
        self._paths = {}
        for i, hit in enumerate(self.hits[: self.shown]):
            self._materialize(hit, highlight)
            self._paths[hit.file_id] = hit.path
            if self.grouped and hit.file_id != last_file:
                last_file = hit.file_id
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
        kind = "📕" if hit.path.lower().endswith(".pdf") else "📄"
        return (
            f'<table width="100%" cellspacing="0" cellpadding="9" style="background:{C_FILE}; margin-top:16px">'
            f'<tr><td><span style="font-size:13pt; font-weight:bold; color:#1e3a8a">{kind} {name}</span>'
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
                segs.append(f'<span style="background:{C_HL_BG}; color:{C_HL_FG}">{t}</span>')
            elif kind == SEG_PARA:
                segs.append('<span style="color:#cbd5e1"> ¶ </span>')
            elif kind == SEG_GAP:
                segs.append(f'<span style="color:#94a3b8">{t}</span>')
            else:
                segs.append(t)
        doc = ""
        if not self.grouped:
            kind = "📕" if hit.path.lower().endswith(".pdf") else "📄"
            doc = (f'<span style="color:#1e3a8a; font-weight:bold">{kind} {_esc(doc_name(hit.path))}</span>'
                   f'<span style="color:#cbd5e1">&nbsp; | &nbsp;</span>')
        badge = ('&nbsp;&nbsp;<span style="background:#dcfce7; color:#166534; font-size:8.5pt">'
                 '&nbsp;התאמה מדויקת&nbsp;</span>' if hit.exact else "")
        n_terms = self.result.n_terms if self.result else 0
        if n_terms > 1 and hit.covered < n_terms:
            badge += ('&nbsp;&nbsp;<span style="background:#fef3c7; color:#92400e; font-size:8.5pt">'
                      f'&nbsp;{hit.covered} מתוך {n_terms} מילים&nbsp;</span>')
        return (
            f'<table width="100%" cellspacing="0" cellpadding="10" style="background:{C_CARD}; margin-top:3px">'
            f'<tr><td>'
            f'<span style="color:#94a3b8">{i + 1}.</span>&nbsp; {doc}'
            f'<a href="hit:{i}" style="color:{C_ACCENT}; text-decoration:none; font-weight:bold">'
            f'{_esc(hit.location)}&nbsp; <span style="font-weight:normal">↗ פתח במקום</span></a>'
            f'<span style="color:#cbd5e1">&nbsp; | &nbsp;</span>'
            f'<a href="view:{i}" style="color:{C_ACCENT}; text-decoration:none">👁 תצוגה</a>{badge}'
            f'</td><td align="left" width="90" style="font-size:7pt; white-space:nowrap">{_meter(hit.score)}</td>'
            f'</tr><tr><td colspan="2">'
            f'<p dir="rtl" style="font-family:{SNIPPET_FONT}; font-size:15pt; margin-top:0; margin-bottom:0; '
            f'line-height:140%"><a href="hit:{i}" style="color:#1f2937; text-decoration:none">'
            f'{"".join(segs)}</a></p>'
            f'</td></tr></table>')

    def _on_anchor(self, url: QUrl):
        s = url.toString()
        kind, _, arg = s.partition(":")
        if kind == "more":
            self.shown = min(len(self.hits), self.shown + PAGE)
            self._render(keep_scroll=True)
        elif kind == "hit":
            self.hitClicked.emit(self.hits[int(arg)])
        elif kind == "view":
            self.hitPreview.emit(self.hits[int(arg)])
        elif kind in ("file", "dir"):
            path = self._paths.get(int(arg))
            if path:
                (self.fileClicked if kind == "file" else self.folderClicked).emit(path)


def form_of(word):
    return restore_finals(word)
