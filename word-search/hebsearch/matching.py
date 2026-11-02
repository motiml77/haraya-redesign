"""מציאת צירופים של כמה מילים בתוך פסקה.

הקלט: לכל מילת חיפוש – רשימת המיקומים (מספרי המילים) שבהם היא מופיעה בפסקה.
התאמה = בחירה של מיקום שונה לכל מילה (או לפחות ל-k מהן), כך ש:
  * בין כל שתי מילים נבחרות סמוכות יש לכל היותר gap מילים אחרות;
  * אם ordered – המילים מופיעות באותו סדר כמו בשאילתה.

האלגוריתם: תכנות דינמי על המופעים לפי סדרם בפסקה. המצב הוא (קבוצת המילים
שכבר נבחרו, המילה האחרונה), ולכל מצב נשמר המופע האחרון שלו – המאוחר ביותר,
כי ממנו אפשר להמשיך הכי רחוק. כך נמצאת כל התאמה שקיימת (חיפוש "חמדני" של
המופע הקרוב הבא מפספס מקרים – למשל כשהמופע הקרוב של מילה 2 רחוק מדי
ממילה 3, אבל מופע מאוחר יותר שלה מתאים).

ההתאמות שמוחזרות לא חופפות, ונבחרות לפי הסוף המוקדם ביותר – זה מבטיח את
המספר המרבי של התאמות נפרדות.
"""


def _events(positions):
    """[(מיקום, (אינדקסי המילים שמתאימות למיקום))] ממוין לפי מיקום."""
    at = {}
    for t, plist in enumerate(positions):
        for p in plist:
            at.setdefault(p, []).append(t)
    return [(p, tuple(at[p])) for p in sorted(at)]


_POPCOUNT = [bin(i).count("1") for i in range(1 << 12)]


def _min_cover(events, n):
    """אורך המקטע הקצר ביותר שמכיל את כל n המילים (בדיקה מקדימה זולה)."""
    counts = [0] * n
    have, lo, best = 0, 0, None
    for hi in range(len(events)):
        for t in events[hi][1]:
            if counts[t] == 0:
                have += 1
            counts[t] += 1
        while have == n:
            w = events[hi][0] - events[lo][0] + 1
            if best is None or w < best:
                best = w
            for t in events[lo][1]:
                counts[t] -= 1
                if counts[t] == 0:
                    have -= 1
            lo += 1
    return best


def _chain(state):
    """שחזור הבחירות ממצב: [(מיקום, מילה)] בסדר עולה."""
    out = []
    while state is not None:
        out.append((state[0], state[2]))
        state = state[3]
    return out[::-1]


def find_spans(positions, gap=0, ordered=True, required=None):
    """מחזיר רשימת התאמות; כל התאמה היא [(מיקום, אינדקס_מילה)] ממוינת לפי מיקום.

    positions: לכל מילת חיפוש רשימת מיקומים. gap: מספר המילים המרבי בין מילה
    נבחרת לבאה (None = ללא הגבלה, בתוך הפסקה). required: כמה מילים לפחות
    (ברירת מחדל: כולן).
    """
    n = len(positions)
    k = n if required is None else max(1, min(required, n))
    if ordered and gap == 0 and k == n:
        return _phrases(positions)
    events = _events(positions)
    if gap is None:
        return _whole(events, n, k)
    if k == n:
        # כל המילים חייבות להיכנס לחלון של n + (n-1)*gap מילים – אם אין חלון כזה, אין התאמה
        cover = _min_cover(events, n)
        if cover is None or cover > n + (n - 1) * gap:
            return []
    reach = gap + 1
    pop = _POPCOUNT
    out = []
    i = 0
    while i < len(events):
        # frontier: (קבוצה, מילה_אחרונה) -> (מיקום_אחרון, מיקום_התחלה, מילה, קודם)
        frontier = {}
        best = None            # (מספר_מילים, -סוף, התחלה, מצב)
        deadline = None
        j = i
        while j < len(events):
            pos, terms = events[j]
            if deadline is not None and pos > deadline:
                break
            new = {}
            live = [(key, st) for key, st in frontier.items() if pos - st[0] <= reach]
            for t in terms:
                bit = 1 << t
                tkey = t if ordered else -1
                key = (bit, tkey)
                if key not in new:
                    new[key] = (pos, pos, t, None)
                for (mask, last), st in live:
                    if mask & bit or (ordered and t < last):
                        continue
                    key = (mask | bit, tkey)
                    old = new.get(key)
                    if old is None or st[1] > old[1]:          # התחלה מאוחרת = צירוף צפוף יותר
                        new[key] = (pos, st[1], t, st)
            # מצבים שכבר לא יכולים להתארך נשמטים
            frontier = dict(live)
            frontier.update(new)
            for (mask, _), st in new.items():
                m = pop[mask]
                if m >= k:
                    cand = (m, -st[0], st[1], st)
                    if best is None or cand[:3] > best[:3]:
                        best = cand
            if best is not None:
                if best[0] == n:
                    break                      # כל המילים – אין מה לשפר
                deadline = -best[1] + reach    # אולי אפשר להוסיף עוד מילים מעט הלאה
            j += 1
        if best is None:
            break
        chain = _chain(best[3])
        out.append(chain)
        end = chain[-1][0]
        while i < len(events) and events[i][0] <= end:
            i += 1
    return out


def _phrases(positions):
    """צירוף מדויק (לפי הסדר, צמוד): מילה i נמצאת במיקום p+i."""
    sets = [set(p) for p in positions[1:]]
    out, last = [], -1
    for p in positions[0]:
        if p > last and all(p + i in st for i, st in enumerate(sets, 1)):
            out.append([(p + i, i) for i in range(len(positions))])
            last = p + len(positions) - 1
    return out


def _whole(events, n, k):
    """"בכל מקום בפסקה": התאמה אחת – כל המופעים, אם יש לפחות k מילים שונות."""
    covered = {t for _, terms in events for t in terms}
    if len(covered) < k or len(events) < k:
        return []
    return [[(p, terms[0]) for p, terms in events]]
