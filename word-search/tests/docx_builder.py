"""בונה קבצי docx מינימליים לבדיקות (בלי תלות ב-python-docx)."""

import zipfile
from xml.sax.saxutils import escape

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>
</Relationships>"""


def _runs(text):
    """טקסט עם סימונים: '|' = שבירת עמוד מרונדרת, '^N' = הפניה להערה N."""
    out = []
    for piece in text.split("|"):
        if out:
            out.append('<w:r><w:lastRenderedPageBreak/></w:r>')
        parts = piece.split("^")
        out.append(f'<w:r><w:t xml:space="preserve">{escape(parts[0])}</w:t></w:r>')
        for p in parts[1:]:
            num = "".join(c for c in p[:3] if c.isdigit())
            rest = p[len(num):]
            out.append(f'<w:r><w:footnoteReference w:id="{num}"/></w:r>')
            out.append(f'<w:r><w:t xml:space="preserve">{escape(rest)}</w:t></w:r>')
    return "".join(out)


def build_docx(path, paragraphs, footnotes=None, table=None):
    body = "".join(f"<w:p>{_runs(p)}</w:p>" for p in paragraphs)
    if table:
        rows = "".join(
            "<w:tr>" + "".join(f"<w:tc><w:p>{_runs(c)}</w:p></w:tc>" for c in row) + "</w:tr>"
            for row in table)
        body += f"<w:tbl>{rows}</w:tbl>"
    doc = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W}"><w:body>{body}<w:sectPr/></w:body></w:document>'
    notes = "".join(
        f'<w:footnote w:id="{nid}"><w:p>{_runs(t)}</w:p></w:footnote>' for nid, t in (footnotes or {}).items())
    fdoc = (f'<?xml version="1.0" encoding="UTF-8"?><w:footnotes xmlns:w="{W}">'
            f'<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
            f'{notes}</w:footnotes>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/footnotes.xml", fdoc)
