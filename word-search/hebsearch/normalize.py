"""נרמול טקסט עברי.

כל מילה עוברת אותו נרמול גם באינדקס וגם בשאילתה:
  * הסרת ניקוד וטעמי מקרא (U+0591–U+05C7, חוץ ממקף, פסק וסוף פסוק).
  * הסרת גרש, גרשיים ומירכאות בתוך מילה (רש"י == רשי).
  * המרת אותיות סופיות לרגילות (ך→כ, ם→מ ...) כדי שגזע "הלכ" יתאים ל"הלך".
  * פירוק צורות תצוגה (U+FB1D–U+FB4F) וליגטורות יידיש.
  * אותיות לטיניות – לאותיות קטנות.
"""

import re
import unicodedata

# אותיות שמרכיבות מילה
_LETTER = "0-9A-Za-zÀ-ɏא-תװ-ײיִ-ﭏ"
# סימנים שמוצמדים לאות ונמחקים (ניקוד, טעמים, סימני כיווניות)
_MARK = "֑-ׇֽֿׁׂׅׄ̀-ͯ͏‌‍‎‏"
# מירכאות/גרשיים – חלק מהמילה רק כשאחריהם באה אות (רש"י, ע"פ)
_QUOTE = "'\"`´׳״‘’“”„"

TOKEN_RE = re.compile(f"[{_LETTER}][{_MARK}]*(?:[{_QUOTE}]*[{_LETTER}][{_MARK}]*)*")
_PRESENTATION_RE = re.compile("[יִ-ﭏ]")

FINALS = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}


def _expand(ranges: str):
    """מרחיב מחרוזת בסגנון מחלקת regex ("a-z") לרשימת תווים."""
    out, i = [], 0
    while i < len(ranges):
        if i + 2 < len(ranges) and ranges[i + 1] == "-":
            out.extend(chr(c) for c in range(ord(ranges[i]), ord(ranges[i + 2]) + 1))
            i += 3
        else:
            out.append(ranges[i])
            i += 1
    return out


_TABLE = {ord(c): None for c in _expand(_MARK) + _expand(_QUOTE)}
_TABLE.update({ord(k): v for k, v in FINALS.items()})
_TABLE.update({ord("װ"): "וו", ord("ױ"): "וי", ord("ײ"): "יי"})

# טבלה לתצוגה: מסירה ניקוד ומירכאות אבל משאירה אותיות סופיות
_DISPLAY_TABLE = {ord(c): None for c in _expand(_MARK) + _expand(_QUOTE)}


def normalize_word(word: str) -> str:
    if _PRESENTATION_RE.search(word):
        word = unicodedata.normalize("NFKD", word)
    return word.translate(_TABLE).lower()


def display_word(word: str) -> str:
    """צורה קריאה של מילה (בלי ניקוד, עם אותיות סופיות)."""
    if _PRESENTATION_RE.search(word):
        word = unicodedata.normalize("NFKD", word)
    return word.translate(_DISPLAY_TABLE)


def _normalize_many(words):
    """נרמול של הרבה מילים בקריאה אחת ל-translate (מהיר בהרבה ממילה-מילה)."""
    joined = "\n".join(words)
    if _PRESENTATION_RE.search(joined):
        joined = unicodedata.normalize("NFKD", joined)
    return joined.translate(_TABLE).lower().split("\n")


def tokenize(text: str):
    """מחזיר רשימת (התחלה, סוף, מילה_מנורמלת) לפי המיקום בטקסט המקורי."""
    ms = list(TOKEN_RE.finditer(text))
    if not ms:
        return []
    norms = _normalize_many([m.group() for m in ms])
    return [(m.start(), m.end(), n) for m, n in zip(ms, norms) if n]


def normalize_text(text: str):
    words = TOKEN_RE.findall(text)
    return [n for n in _normalize_many(words) if n] if words else []


def strip_finals(word: str) -> str:
    return word.translate({ord(k): v for k, v in FINALS.items()})


_TO_FINAL = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}


def restore_finals(word: str) -> str:
    """הופך מילה מנורמלת לצורה קריאה (אות אחרונה כסופית)."""
    if len(word) > 1 and word[-1] in _TO_FINAL:
        return word[:-1] + _TO_FINAL[word[-1]]
    return word
