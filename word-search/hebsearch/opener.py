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
    """חלונות עם וורד מותקן (רישום ה-COM של Word.Application) וספריית pywin32."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        import win32com.client  # noqa: F401
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Word.Application"))
        return True
    except (ImportError, OSError):
        return False


def _story(doc, kind, note):
    if kind == KIND_FOOTNOTE:
        return doc.Footnotes(note).Range
    if kind == KIND_ENDNOTE:
        return doc.Endnotes(note).Range
    return doc.Content


def _find_nth(rng, needle, n, match_diacritics):
    """מצמצם את rng למופע ה-n (מ-0) של needle בתוכו. מחזיר True אם נמצא."""
    find = rng.Find
    find.ClearFormatting()
    try:
        find.MatchDiacritics = match_diacritics
    except Exception:
        pass
    text = _word_find_text(needle)
    for i in range(n + 1):
        # FindText, MatchCase, MatchWholeWord, MatchWildcards, MatchSoundsLike,
        # MatchAllWordForms, Forward, Wrap
        if not find.Execute(text, False, False, False, False, False, True, WD_FIND_STOP):
            return False
        if i < n:
            rng.Collapse(WD_COLLAPSE_END)
    return True


def _locate_in_word(doc, candidates, kind, note, ratio):
    """מחזיר (טווח, טקסט) של התוצאה במסמך, או (None, None).

    1. לפי ספירת המופעים: המופע ה-k של הטקסט בגוף המסמך / בהערה.
    2. גיבוי: לפי המיקום היחסי במסמך – המופע הראשון שמתחיל קצת לפני המקום המשוער.
    """
    for diacritics in (True, False):
        for needle, k in candidates:
            rng = _story(doc, kind, note)
            if _find_nth(rng, needle, k, diacritics):
                return rng, needle
    if ratio is not None:
        story = _story(doc, kind, note)
        guess = story.Start + int((story.End - story.Start) * ratio)
        for diacritics in (True, False):
            for needle, _k in candidates:
                rng = doc.Range(max(story.Start, guess - 1500), story.End)
                if _find_nth(rng, needle, 0, diacritics):
                    return rng, needle
    return None, None


def _bring_to_front(word):
    try:
        if word.WindowState == 2:           # ממוזער
            word.WindowState = 0
    except Exception:
        pass
    word.Activate()
    try:  # חלונות מונעת "גניבת פוקוס"; לחיצת Alt מדומה מתירה להביא את וורד לחזית
        import win32gui
        import win32com.client
        win32com.client.Dispatch("WScript.Shell").SendKeys("%")
        win32gui.SetForegroundWindow(word.ActiveWindow.Hwnd)
    except Exception:
        pass


def _open_in_word(path, candidates, kind, note, ratio):
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
        rng, found = _locate_in_word(doc, candidates, kind, note, ratio)
        if rng is not None:
            rng.Select()
            try:
                word.ActiveWindow.ScrollIntoView(rng, True)
            except Exception:
                pass
            # מרקר צהוב זמני על המילים (לא נשמר בקובץ; נעלם בחיפוש הבא או ב-Esc)
            try:
                doc.Content.Find.HitHighlight(_word_find_text(found), WD_COLOR_YELLOW)
            except Exception:
                pass
        _bring_to_front(word)
        return rng is not None
    finally:
        pythoncom.CoUninitialize()


def open_at(path, candidates=(), kind=0, note=0, ratio=None, on_status=None):
    """פותח את המסמך, ובחלונות עם וורד – גם מנווט למקום ומסמן אותו.

    candidates = [(טקסט, מספר_מופעים_לפניו)], ratio = מיקום יחסי (גיבוי).
    on_status(הודעה) נקרא מתהליכון רקע בסיום. מחזיר True אם נעשה ניסיון ניווט בוורד.
    """
    if word_automation_available() and candidates:
        def run():
            try:
                ok = _open_in_word(path, list(candidates), kind, note, ratio)
                msg = "" if ok else "המסמך נפתח בוורד, אבל המקום המדויק לא אותר – נסו Ctrl+F."
            except Exception as e:
                try:
                    open_default(path)
                except Exception:
                    pass
                msg = f"לא הצלחתי לפתוח בוורד ({e}); המסמך נפתח בתוכנת ברירת המחדל."
            if on_status and msg:
                on_status(msg)
        threading.Thread(target=run, daemon=True).start()
        return True
    open_default(path)
    return False


def _find_exe(*candidates):
    import shutil
    for c in candidates:
        if not c:
            continue
        if os.path.isabs(c):
            if os.path.isfile(c):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return None


def open_pdf_external(path, page=1, word=""):
    """פותח PDF בתוכנה חיצונית – בעמוד הנכון, אם התוכנה תומכת בזה."""
    page = max(1, int(page or 1))
    if sys.platform == "win32":
        pf = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)")]
        acrobat = _find_exe(*[os.path.join(p, sub) for p in pf if p for sub in (
            r"Adobe\Acrobat DC\Acrobat\Acrobat.exe",
            r"Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
            r"Adobe\Acrobat Reader\Reader\AcroRd32.exe")])
        if acrobat:
            action = f"page={page}" + (f"&search={word}" if word else "")
            subprocess.Popen([acrobat, "/A", action, path])
            return
        sumatra = _find_exe(
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "SumatraPDF", "SumatraPDF.exe"),
            *[os.path.join(p, "SumatraPDF", "SumatraPDF.exe") for p in pf if p])
        if sumatra:
            subprocess.Popen([sumatra, "-reuse-instance", "-page", str(page), path])
            return
    elif sys.platform.startswith("linux"):
        for exe, args in (("okular", ["-p", str(page)]), ("evince", ["-i", str(page)])):
            found = _find_exe(exe)
            if found:
                subprocess.Popen([found, *args, path])
                return
    open_default(path)
