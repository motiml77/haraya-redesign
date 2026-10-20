"""פתיחת מסמך – ובחלונות עם וורד מותקן, גם קפיצה וסימון של המילים שנמצאו."""

import os
import subprocess
import sys
import threading

from .extract import KIND_ENDNOTE, KIND_FOOTNOTE

WD_FIND_STOP = 0
WD_COLLAPSE_END = 0
WD_COLOR_YELLOW = 65535


def _word_find_text(s: str) -> str:
    return s.replace("^", "^^").replace("\t", "^t").replace("\n", "^l")


def open_default(path: str):
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def reveal_in_folder(path: str):
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])


def word_automation_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False


def _find(doc, needle, occurrence, kind, note, match_diacritics, word):
    """מחפש את המופע ה-occurrence של needle ומסמן אותו. מחזיר True אם נמצא."""
    if kind == KIND_FOOTNOTE:
        rng = doc.Footnotes(note).Range
    elif kind == KIND_ENDNOTE:
        rng = doc.Endnotes(note).Range
    else:
        rng = doc.Content
    find = rng.Find
    find.ClearFormatting()
    try:
        find.MatchDiacritics = match_diacritics
    except Exception:
        pass
    text = _word_find_text(needle)
    for i in range(occurrence + 1):
        # FindText, MatchCase, MatchWholeWord, MatchWildcards, MatchSoundsLike,
        # MatchAllWordForms, Forward, Wrap
        if not find.Execute(text, False, False, False, False, False, True, WD_FIND_STOP):
            return False
        if i < occurrence:
            rng.Collapse(WD_COLLAPSE_END)
    rng.Select()
    try:
        word.ActiveWindow.ScrollIntoView(rng, True)
    except Exception:
        pass
    return True


def _open_in_word(path, candidates, kind, note):
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        try:
            word = win32com.client.GetActiveObject("Word.Application")
        except Exception:
            word = win32com.client.Dispatch("Word.Application")
        word.Visible = True
        doc = word.Documents.Open(os.path.abspath(path), AddToRecentFiles=True)
        doc.Activate()
        for match_diacritics in (True, False):
            found = next((n for n, k in candidates
                          if _find(doc, n, k, kind, note, match_diacritics, word)), None)
            if found:
                # מרקר צהוב זמני על המילים (לא נשמר בקובץ; נעלם בלחיצה על Esc/חיפוש חדש)
                try:
                    doc.Content.Find.HitHighlight(_word_find_text(found), WD_COLOR_YELLOW)
                except Exception:
                    pass
                break
        word.Activate()
    finally:
        pythoncom.CoUninitialize()


def open_at(path, candidates=(), kind=0, note=0, on_error=None):
    """פותח את הקובץ. candidates = [(טקסט, מספר_מופעים_לפניו)] לאיתור המקום."""
    if word_automation_available() and candidates:
        def run():
            try:
                _open_in_word(path, list(candidates), kind, note)
            except Exception as e:
                try:
                    open_default(path)
                except Exception:
                    pass
                if on_error:
                    on_error(str(e))
        threading.Thread(target=run, daemon=True).start()
        return True
    open_default(path)
    return False
