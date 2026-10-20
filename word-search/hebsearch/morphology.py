"""בניית תבנית התאמה למילת חיפוש.

התבנית לא רצה על הטקסט עצמו אלא על אוצר המילים (רשימת המילים הייחודיות
שבאינדקס), ולכן גם תבנית "רחבה" עם הטיות היא זולה: עשרות אלפי מילים
במקום מיליוני מופעים.

כל המילים כאן כבר מנורמלות (בלי ניקוד, בלי אותיות סופיות).

מבנה התבנית:
    [אותיות שימוש] [תחילית בניין/זמן] גזע [סיומת]

 * אותיות שימוש: ו, ש/כש/מש/לכש, ב/כ/ל/מ, ה   – לפי סדר הופעתן בעברית.
 * הטיות: הסרת סיומת מהשאילתה (הליכה → הליכ), הסרת אמות קריאה פנימיות
   (הליכ → הלכ), ובחיפוש מתירים ו/י בין אותיות הגזע (הלכ → הליכה, הולך)
   וסיומות ותחיליות של נטיית פעלים ושמות.
 * שורשים שאות ראשונה שלהם (י/נ/ה) נשמטת בנטייה: הלך → ילך, וילך, ללכת;
   ירד → תרד, לרדת.
 זהו קירוב היוריסטי ולא מנתח מורפולוגי מלא.
 * אהו"י: האותיות שנבחרו מוסרות מהשאילתה ומותרות (עד 2) בין כל שתי אותיות.
"""

import re
from dataclasses import dataclass

from .normalize import normalize_word, strip_finals

PROCLITICS = "ו?(?:ש|כש|מש|לכש)?[בכלמ]?ה?"
VERB_PREFIXES = "(?:הת|נת|מת|ית|את|תת|[איתנמה])?"
# פעלים שאות השורש הראשונה נשמטת: עתיד (ילך, וכשתלך) ושם פועל (ללכת, בלכתו)
WEAK_FIRST = "יהנ"
FUTURE_PROCLITICS = "ו?(?:ש|כש)?ל?[איתנ]"
INFINITIVE_PROCLITICS = "ו?[בכל]?"

_SUFFIXES_RAW = [
    "ה", "ת", "ית", "ות", "ים", "ין", "י", "ו", "הו", "נו", "ני", "ך", "כה",
    "כם", "כן", "הם", "הן", "ם", "ן", "תי", "תה", "תם", "תן", "יה", "יו",
    "יהם", "יהן", "יך", "יכם", "יכן", "ינו", "ותי", "ותיו", "ותיה", "ותינו",
    "ותיכם", "ותיכן", "ותיהם", "ותיהן", "ותיך", "תו", "תך", "תנו", "תיו",
    "יות", "יים", "ייה", "יית", "נה", "ונה", "יא",
]
SUFFIXES = sorted({strip_finals(s) for s in _SUFFIXES_RAW}, key=len, reverse=True)
SUFFIX_RE = "(?:" + "|".join(SUFFIXES) + ")?"

AHEVI_SETS = {"none": "", "vy": "וי", "all": "אהוי"}
MATRES = "וי"
WILDCARDS = "*?"


@dataclass(frozen=True)
class MatchOptions:
    prefixes: bool = True        # לאפשר אותיות שימוש בתחילת המילה
    inflections: bool = False    # הטיות (סיומות, תחיליות פעליות, ו/י בגזע)
    ahevi: str = "none"          # "none" | "vy" | "all"


def normalize_query_word(word: str) -> str:
    """נרמול מילת שאילתה תוך שמירה על תווי כוכבית/סימן שאלה."""
    parts = re.split(r"([*?])", word)
    return "".join(p if p in WILDCARDS else normalize_word(p) for p in parts)


def _stems(core: str):
    """גזעים אפשריים למילת השאילתה (כולל המילה עצמה)."""
    stems = {core}
    if any(c in WILDCARDS for c in core):
        return stems
    cands = {core}
    for suf in SUFFIXES:
        if core.endswith(suf) and len(core) - len(suf) >= 3:
            cands.add(core[: -len(suf)])
    for c in list(cands):
        stems.add(c)
        inner = c[0] + "".join(ch for ch in c[1:-1] if ch not in MATRES) + c[-1] if len(c) > 2 else c
        if len(inner) >= 3:
            stems.add(inner)
    for c in list(stems):
        # גזרת ל"ה: בנה → בנ (בנית, בונים, בניה)
        if len(c) == 3 and c.endswith("ה"):
            stems.add(c[:-1])
    return {s for s in stems if len(s) >= 2 or s == core}


def _letters_pattern(word: str, gap: str, edges: bool) -> str:
    out = []
    for ch in word:
        if ch == "*":
            out.append("[^\\n]*")
        elif ch == "?":
            out.append("[^\\n]")
        else:
            out.append(re.escape(ch))
    body = gap.join(out) if gap else "".join(out)
    if edges and gap:
        body = gap + body + gap
    return body


def word_pattern(word: str, opts: MatchOptions) -> str:
    """מחזיר regex (ללא עוגנים) שמתאר את כל הצורות המותרות של המילה."""
    core = normalize_query_word(word)
    if not core:
        return ""
    ahevi = AHEVI_SETS.get(opts.ahevi, "")

    if ahevi:
        stripped = "".join(c for c in core if c not in ahevi)
        if stripped.replace("*", "").replace("?", ""):
            core = stripped
        ahevi_gap = f"[{ahevi}]{{0,2}}"
    else:
        ahevi_gap = ""

    if opts.inflections:
        stems = _stems(core)
        gap = ahevi_gap or "[וי]?"
        if ahevi and "ו" not in ahevi:
            gap = f"[{''.join(sorted(set(ahevi + MATRES)))}]{{0,2}}"
        alts = sorted({_letters_pattern(s, gap, edges=bool(ahevi)) for s in stems}, key=len, reverse=True)
        stem_re = "(?:" + "|".join(alts) + ")"
        pre = f"{PROCLITICS}{VERB_PREFIXES}" if opts.prefixes else VERB_PREFIXES
        pattern = f"{pre}{stem_re}{SUFFIX_RE}"
        weak = {s[1:] for s in stems if len(s) == 3 and s[0] in WEAK_FIRST}
        if weak:
            rest = "(?:" + "|".join(_letters_pattern(w, gap, edges=False) for w in sorted(weak)) + ")"
            fut = FUTURE_PROCLITICS if opts.prefixes else "[איתנ]"
            inf = INFINITIVE_PROCLITICS if opts.prefixes else ""
            pattern += f"|{fut}{rest}{SUFFIX_RE}|{inf}{rest}ת{SUFFIX_RE}"
        return pattern

    stem_re = _letters_pattern(core, ahevi_gap, edges=bool(ahevi))
    if opts.prefixes:
        return f"{PROCLITICS}(?:{stem_re})"
    return stem_re


def term_regex(alternatives, opts: MatchOptions):
    """regex מקומפל לחיפוש שורה-שורה באוצר המילים (מחרוזת מופרדת ב-\\n)."""
    pats = [p for p in (word_pattern(a, opts) for a in alternatives) if p]
    if not pats:
        return None
    return re.compile("^(?:" + "|".join(f"(?:{p})" for p in pats) + ")$", re.M)
