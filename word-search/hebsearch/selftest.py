"""בדיקה עצמית של התוכנה כפי שהיא מותקנת (גם בגרסה הארוזה).

    HebDocSearch --selftest [report.json] [--gui]

בונה מסמכים זמניים, מאנדקס אותם (כולל קריאה מקבילית בכמה תהליכים), מחפש
צירוף של כמה מילים, קורא PDF, ובמצב --gui גם בונה את החלון הראשי.
התוצאה נכתבת לקובץ JSON, וקוד היציאה 0 אומר שהכל תקין.
"""

import json
import os
import platform
import sys
import tempfile
import time
import traceback
import zipfile
from xml.sax.saxutils import escape

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _write_docx(path, paragraphs):
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{escape(p)}</w:t></w:r></w:p>' for p in paragraphs)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/content-types"><Default Extension="rels" ContentType="application/'
                   'vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType='
                   '"application/xml"/><Override PartName="/word/document.xml" ContentType="application/'
                   'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://'
                   'schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                   'Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml",
                   f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{_W}"><w:body>{body}'
                   '</w:body></w:document>')


def run(argv):
    report_path = next((a for a in argv if not a.startswith("--")), None)
    want_gui = "--gui" in argv
    from . import __version__
    report = {"version": __version__, "python": sys.version.split()[0], "platform": platform.platform(),
              "frozen": bool(getattr(sys, "frozen", False)), "checks": {}}
    ok = True

    def check(name, fn):
        nonlocal ok
        t0 = time.perf_counter()
        try:
            detail = fn()
            report["checks"][name] = {"ok": True, "detail": detail, "ms": round((time.perf_counter() - t0) * 1000)}
        except Exception:
            ok = False
            report["checks"][name] = {"ok": False, "error": traceback.format_exc()[-2000:]}

    tmp = tempfile.mkdtemp(prefix="hebdocsearch-selftest-")
    os.environ["HEBSEARCH_DATA"] = os.path.join(tmp, "data")
    docs = os.path.join(tmp, "docs")
    os.makedirs(os.path.join(docs, "sub"))

    def make_docs():
        for i in range(12):   # יותר מ-8 קבצים – מפעיל קריאה מקבילית בכמה תהליכים
            folder = docs if i % 2 else os.path.join(docs, "sub")
            _write_docx(os.path.join(folder, f"מסמך {i}.docx"), [
                f"פסקה ראשונה במסמך {i}",
                "וַיֹּאמֶר מֹשֶׁה אֶל הָעָם זִכְרוּ אֶת הַיּוֹם הַזֶּה" if i == 7 else "טקסט רגיל ללא צירוף",
            ])
        return "12 docx"

    def make_pdf():
        import pymupdf
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Self test PDF line with searchword inside", fontsize=12)
        path = os.path.join(docs, "test.pdf")
        doc.save(path)
        return pymupdf.VersionBind

    def index_and_search():
        from .index import IndexDB, resolve_items
        from .paths import default_db_path
        from .search import Searcher, SearchOptions
        db = IndexDB(default_db_path())
        files = resolve_items([(docs, "folder")])
        n = db.update(db.stale_files(files))
        ids = db.file_ids(files)
        s = Searcher(db)
        r = s.search("ויאמר משה אל העם", ids, SearchOptions())
        assert r.total == 1 and r.hits[0].exact, (r.total, r.message)
        s.materialize(r.hits[0], r.highlight)
        assert r.hits[0].location.endswith("פסקה 2"), r.hits[0].location
        p = s.search("searchword", ids, SearchOptions())
        assert p.total == 1 and p.hits[0].path.endswith(".pdf"), (p.total, p.message)
        db.close()
        return {"indexed": n, "files": len(ids)}

    def gui():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from .gui.main_window import MainWindow, prepare_app
        from .paths import default_db_path
        app = QApplication.instance() or QApplication(sys.argv[:1])
        prepare_app(app)
        win = MainWindow(default_db_path())
        win.show()
        for _ in range(30):
            app.processEvents()
            time.sleep(0.02)
        from .gui import pdf_viewer
        assert pdf_viewer.AVAILABLE, "מודול ה-PDF של Qt לא נטען"
        from PySide6.QtPdf import QPdfDocument
        pdf = QPdfDocument()
        pdf.load(os.path.join(docs, "test.pdf"))
        assert pdf.pageCount() == 1, f"QtPdf לא קרא את הקובץ (עמודים: {pdf.pageCount()})"
        assert not app.windowIcon().isNull(), "הלוגו לא נטען"
        info = {"qt_platform": app.platformName(), "pdf_pages": pdf.pageCount()}
        win.close()
        return info

    check("documents", make_docs)
    check("pdf_library", make_pdf)
    check("index_and_search", index_and_search)
    if want_gui:
        check("gui", gui)
    report["ok"] = ok
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(text)
    if sys.stdout is not None:
        try:
            print(text)
        except Exception:
            pass
    return 0 if ok else 1
