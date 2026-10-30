"""מציג מסמכי וורד מובנה: כל המסמך, גלול בדיוק למקום התוצאה ומסומן."""

import html

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTextBrowser

from ..extract import KIND_BODY, KIND_ENDNOTE, KIND_FOOTNOTE, KIND_TEXTBOX
from ..opener import reveal_in_folder
from ..search import para_cache
from .theme import C, T, read_font_css
from .viewer_base import HitViewer

C_CURRENT = C.current     # התוצאה הנוכחית – כתום, כדי שתבלוט בין שאר הסימונים


class DocViewer(HitViewer):
    def __init__(self, searcher, highlight, hits, index, open_original, parent=None):
        super().__init__(searcher, highlight, hits, index, parent)
        self.fit(900, 900)
        self.add_action("פתח את המסמך המקורי", lambda: open_original(self.hit),
                        "פותח את הקובץ עצמו (בחלונות עם וורד – גם במקום המדויק)")
        self.add_action("הצג בתיקייה", lambda: reveal_in_folder(self.path))
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.document().setDocumentMargin(T.pad * 2)
        self.layout_.addWidget(self.browser, 1)
        self.go(index)

    def show_hit(self, hit):
        sb = self.browser.verticalScrollBar()
        self.browser.setHtml(self._html(hit))
        QTimer.singleShot(0, lambda: (self.browser.scrollToAnchor("cur"),
                                      sb.setValue(max(0, sb.value() - self.browser.viewport().height() // 3))))

    def _matched_positions(self):
        """פסקה ← מיקומי המילים שהן חלק מהתאמה כלשהי במסמך (בחיפוש של כמה מילים רק אותן מסמנים)."""
        out = {}
        for h in self.hits:
            out.setdefault(h.para_idx, set()).update(h.span)
        return out

    def _para_html(self, entry, i, hit):
        text = entry[0][i][0]
        toks = self.searcher._tokens(entry, i)
        current = set(hit.span) if i == hit.para_idx else ()
        multi = getattr(self.highlight, "multi", False)
        matched = self._matched.get(i, ()) if multi else None
        out, pos = [], 0
        for n, (s, e, norm) in enumerate(toks):
            if n in current:
                mark = C_CURRENT
            elif norm in self.highlight and (matched is None or n in matched):
                mark = C.marker
            else:
                mark = None
            if not mark:
                continue
            out.append(html.escape(text[pos:s]))
            if current and n == min(current):
                out.append('<a name="cur"></a>')
            weight = "; font-weight:bold" if n in current else ""
            out.append(f'<span style="background:{mark}{weight}">{html.escape(text[s:e])}</span>')
            pos = e
        out.append(html.escape(text[pos:]))
        return "".join(out).replace("\n", "<br>").replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")

    def _html(self, hit):
        self._matched = self._matched_positions()
        entry = para_cache.get(self.searcher.db, hit.file_id)
        paras = entry[0]
        body, notes = [], {KIND_FOOTNOTE: [], KIND_ENDNOTE: []}
        page = None
        for i, p in enumerate(paras):
            kind = p[2]
            if kind in notes:
                notes[kind].append(f'<p style="margin:0 0 6px 0"><b>{p[3]}.</b> {self._para_html(entry, i, hit)}</p>')
                continue
            if kind == KIND_BODY and p[1] and p[1] != page:
                if page is not None:
                    body.append(f'<p align="center" style="color:{C.muted}; font-size:{T.caption}px; '
                                f'margin:14px 0">— עמוד {p[1]} —</p>')
                page = p[1]
            content = self._para_html(entry, i, hit)
            if kind == KIND_TEXTBOX:
                body.append(f'<table width="100%" cellpadding="8" style="background:{C.surface_alt}; margin:6px 0">'
                            f'<tr><td>{content}</td></tr></table>')
            else:
                body.append(f'<p style="margin:0 0 10px 0">{content}</p>')
        for kind, title in ((KIND_FOOTNOTE, "הערות שוליים"), (KIND_ENDNOTE, "הערות סיום")):
            if notes[kind]:
                body.append(f'<hr><p style="color:{C.muted}; font-weight:bold">{title}</p>')
                body.append(f'<div style="font-size:{T.snippet - 1}px">{"".join(notes[kind])}</div>')
        return (f'<html><body dir="rtl" style="font-family:{read_font_css()}; font-size:{T.snippet + 1}px; '
                f'color:{C.text}; line-height:150%">{"".join(body)}</body></html>')
