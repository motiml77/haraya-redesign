// טקסט המסמך מחולק לפסקאות – מקריאה אחת של Content.Text (קריאה אחת למודל של Word, ולא פסקה
// אחר פסקה: כל קריאה כזו רצה על התהליך הראשי של Word ומאטה אותו).
// החלוקה, טביעת האצבע ובניית הבקשה לרכיב העזר רצות על תהליך נפרד – אין בהן גישה ל-Word.
//
// המיקום של פסקה במסמך הוא הערכה: Content.Text מחזיר לתא בטבלה "\r\a" (שני תווים) בעוד שבמסמך
// זה מקום אחד, ושדות/תמונות מוסיפים מקומות שאינם בטקסט. לכן כשקופצים לתוצאה בודקים שהטקסט
// במקום המשוער הוא הטקסט שחיפשנו, ואם לא – מוצאים אותו בעזרת Find של Word, ולומדים את ההפרש.
using System;
using System.Collections.Generic;
using System.Text;
using Word = Microsoft.Office.Interop.Word;

namespace HebDocSearch.WordAddin
{
    /// <summary>תמצית של גרסת מסמך: טביעת אצבע ורמת כותרת לכל פסקה, וההפרשים במיקום שנלמדו.</summary>
    internal sealed class DocSnapshot
    {
        public string TextHash;
        public ulong[] Hashes;
        public byte[] Levels;
        public int[] DriftKeys, DriftValues;
    }

    internal sealed class DocText
    {
        public readonly string TextHash;            // אורך + FNV-1a של כל הטקסט
        public readonly List<string> Texts;
        public readonly List<int> Starts;           // מיקום משוער של תחילת כל פסקה במסמך
        public readonly int[] Levels;               // 1–9 כותרת, 0 גוף
        public readonly bool HasLevels;             // האם רמות הכותרות כבר נקראו מהמסמך
        public readonly string Key;                 // מזהה הגרסה אצל רכיב העזר (טקסט + כותרות)
        // פסקאות שנוספו או שהטקסט שלהן השתנה מאז הגרסה הקודמת (כשהרמות עברו ממנה): רק את רמת הכותרת
        // שלהן צריך לבדוק במסמך. ריק – הכל ידוע.
        public readonly int[] Changed;
        public readonly ulong[] ParaHashes;         // טביעת אצבע של כל פסקה – להשוואה לגרסה קודמת (גם מהדיסק)
        // הגרסה הקודמת שממנה נבנתה הזו: הטביעה של הטקסט שלה, ולכל פסקה כאן – מספר הפסקה שם (או ‎-1 לחדשה).
        // כך אפשר לשלוח לרכיב העזר רק את הפסקאות שהשתנו.
        public readonly string BaseTextHash;
        public readonly int[] Source;

        // הפרש שנלמד בין המיקום המשוער למיקום האמיתי (פסקה → הפרש). נלמד בתהליך הראשי, ונקרא גם
        // ב-Build של הגרסה הבאה (בתהליך נפרד) – לכן כל גישה בנעילה.
        readonly SortedList<int, int> _drift = new SortedList<int, int>();

        // פסקאות קצרות לפי הטקסט המנורמל → מספרי הפסקאות (בסדר עולה), להתאמת כותרות בלי לסרוק.
        // נבנה בתהליך הנפרד (ב-Build), ומשותף לגרסאות של אותו טקסט.
        readonly Dictionary<string, List<int>> _byText;
        const int IndexedLength = 400;

        DocText(string hash, List<string> texts, List<int> starts, int[] levels, bool hasLevels, Dictionary<string, List<int>> byText,
                ulong[] paraHashes, int[] changed = null, string baseTextHash = null, int[] source = null)
        {
            ParaHashes = paraHashes;
            BaseTextHash = baseTextHash;
            Source = source;
            TextHash = hash;
            Texts = texts;
            Starts = starts;
            Levels = levels;
            HasLevels = hasLevels;
            Changed = changed ?? new int[0];
            Key = hash + "/" + (hasLevels ? Fnv(levels) : "nolevels");
            _byText = byText;
        }

        // ================================================================ בנייה (בלי Word)
        public static string Hash(string raw)
        {
            return raw.Length + ":" + Fnv(raw);
        }

        static string Fnv(string s) => Fnv64(s).ToString("x16");

        internal static ulong Fnv64(string s)
        {
            ulong h = 14695981039346656037UL;
            foreach (char c in s)
            {
                h ^= c;
                h *= 1099511628211UL;
            }
            return h;
        }

        static string Fnv(int[] levels)
        {
            var sb = new StringBuilder(levels.Length);
            foreach (int l in levels) sb.Append((char)('0' + l));
            return Fnv(sb.ToString());
        }

        /// <summary>מחלק את הטקסט לפסקאות. previous – גרסה קודמת של אותו מסמך: לפסקאות שהטקסט שלהן זהה
        /// (לפי הסדר) עוברות רמת הכותרת וההפרש שנלמד במיקום; את השאר (Changed) צריך לבדוק במסמך.</summary>
        public static DocText Build(string raw, DocText previous = null)
        {
            return Build(raw, previous != null && previous.HasLevels ? previous.Snapshot() : null);
        }

        /// <summary>מה שצריך מגרסה קודמת כדי לא לקרוא את הכותרות מחדש (נשמר גם בדיסק, בלי הטקסט עצמו).</summary>
        public DocSnapshot Snapshot()
        {
            var snap = new DocSnapshot { TextHash = TextHash, Hashes = ParaHashes, Levels = new byte[Levels.Length] };
            for (int i = 0; i < Levels.Length; i++) snap.Levels[i] = (byte)Levels[i];
            lock (_drift)
            {
                snap.DriftKeys = new int[_drift.Count];
                snap.DriftValues = new int[_drift.Count];
                for (int i = 0; i < _drift.Count; i++)
                {
                    snap.DriftKeys[i] = _drift.Keys[i];
                    snap.DriftValues[i] = _drift.Values[i];
                }
            }
            return snap;
        }

        public static DocText Build(string raw, DocSnapshot previous)
        {
            raw = raw ?? "";
            var texts = new List<string>();
            var starts = new List<int>();
            var sb = new StringBuilder();
            int bells = 0, paraStart = 0;
            for (int i = 0; i < raw.Length; i++)
            {
                char c = raw[i];
                if (c == '\r')
                {
                    texts.Add(sb.ToString());
                    starts.Add(paraStart);
                    sb.Clear();
                    if (i + 1 < raw.Length && raw[i + 1] == '\a') { i++; bells++; }    // סוף תא / שורה בטבלה
                    paraStart = i + 1 - bells;
                    continue;
                }
                // תווים מיוחדים של Word מוחלפים באורך זהה, כדי שהמיקומים בתוך הפסקה לא יזוזו
                switch (c)
                {
                    case '\v': case '\a': case '\f': case '\u001f': case '\u0001': case '\u0002': case '\u0013': case '\u0014': case '\u0015':
                        c = ' '; break;
                    case '\u001e':
                        c = '-'; break;
                }
                sb.Append(c);
            }
            if (sb.Length > 0)
            {
                texts.Add(sb.ToString());
                starts.Add(paraStart);
            }

            var hashes = new ulong[texts.Count];
            for (int i = 0; i < hashes.Length; i++) hashes[i] = Fnv64(texts[i]);

            var levels = new int[texts.Count];
            bool hasLevels = false;
            int[] changed = null, fromPrevious = null;
            if (previous != null && previous.Hashes.Length == previous.Levels.Length)
            {
                // כל פסקה של הגרסה הקודמת – לפי הטקסט (טביעת האצבע) ובאותו סדר
                int n = previous.Hashes.Length;
                var first = new Dictionary<ulong, int>(n);
                var next = new int[n];
                for (int j = n - 1; j >= 0; j--)
                {
                    next[j] = first.TryGetValue(previous.Hashes[j], out int f) ? f : -1;
                    first[previous.Hashes[j]] = j;
                }
                var news = new List<int>();
                fromPrevious = new int[n];
                for (int j = 0; j < n; j++) fromPrevious[j] = -1;
                for (int i = 0; i < texts.Count; i++)
                {
                    if (first.TryGetValue(hashes[i], out int j) && j >= 0)
                    {
                        first[hashes[i]] = next[j];
                        levels[i] = previous.Levels[j] < 10 ? previous.Levels[j] : 0;
                        fromPrevious[j] = i;
                    }
                    else if (!string.IsNullOrWhiteSpace(texts[i]))
                        news.Add(i);                    // פסקה חדשה או שנערכה – אולי כותרת
                }
                changed = news.ToArray();
                hasLevels = true;
            }
            var byText = new Dictionary<string, List<int>>();
            for (int i = 0; i < texts.Count; i++)
            {
                if (texts[i].Length > IndexedLength) continue;
                string key = Norm(texts[i]);
                if (key.Length == 0) continue;
                if (!byText.TryGetValue(key, out var list)) byText[key] = list = new List<int>(1);
                list.Add(i);
            }
            int[] source = null;
            if (fromPrevious != null)
            {
                source = new int[texts.Count];
                for (int i = 0; i < source.Length; i++) source[i] = -1;
                for (int j = 0; j < fromPrevious.Length; j++)
                    if (fromPrevious[j] >= 0) source[fromPrevious[j]] = j;
            }
            var dt = new DocText(Hash(raw), texts, starts, levels, hasLevels, byText, hashes, changed,
                                 previous != null ? previous.TextHash : null, source);
            if (fromPrevious != null && previous.DriftKeys != null)
                for (int k = 0; k < previous.DriftKeys.Length; k++)      // ההפרש במיקום (שדות וכו') נשאר בפסקאות שלא זזו
                {
                    int j = previous.DriftKeys[k];
                    if (j >= 0 && j < fromPrevious.Length && fromPrevious[j] >= 0) dt._drift[fromPrevious[j]] = previous.DriftValues[k];
                }
            return dt;
        }

        public DocText WithLevels(int[] levels)
        {
            var copy = new DocText(TextHash, Texts, Starts, levels, true, _byText, ParaHashes, null, BaseTextHash, Source);
            lock (_drift)
                foreach (var kv in _drift) copy._drift[kv.Key] = kv.Value;
            return copy;
        }

        public int Headings
        {
            get { int n = 0; foreach (int l in Levels) if (l > 0) n++; return n; }
        }

        /// <summary>רמות הכותרות כמחרוזת ספרות (ספרה לכל פסקה) – לרכיב העזר, כשהטקסט כבר אצלו בדיסק.</summary>
        public string LevelString()
        {
            var chars = new char[Levels.Length];
            for (int i = 0; i < chars.Length; i++) chars[i] = (char)('0' + (Levels[i] > 0 && Levels[i] < 10 ? Levels[i] : 0));
            return new string(chars);
        }

        /// <summary>האם כדאי לשלוח לרכיב העזר רק את השינויים מהגרסה הקודמת (ולא את כל הפסקאות).</summary>
        public bool CanPatch => Source != null && BaseTextHash != null && BaseTextHash != TextHash;

        /// <summary>הגרסה הזו כשינויים מהגרסה הקודמת: [התחלה, כמה] = פסקאות רצופות משם, מחרוזת = פסקה חדשה.</summary>
        public List<object> PatchOps()
        {
            var ops = new List<object>();
            int n = Texts.Count, i = 0;
            while (i < n)
            {
                if (Source[i] < 0) { ops.Add(Texts[i]); i++; continue; }
                int start = Source[i], k = 1;
                while (i + k < n && Source[i + k] == start + k) k++;
                ops.Add(new[] { start, k });
                i += k;
            }
            return ops;
        }

        /// <summary>הכותרות שנקראו מקובץ ה-docx (טקסט, רמה, מקום משוער ברשימת הפסקאות) → רמה לכל פסקה כאן.
        /// כל כותרת הולכת לפסקה עם אותו טקסט שאחרי הקודמת, והקרובה ביותר למקום המשוער (ההפרש בין המקום
        /// המשוער לאמיתי נלמד תוך כדי). unmatched – כמה כותרות לא נמצאו (ייבדקו ב-Word).</summary>
        public int[] MatchFileHeadings(IList<object[]> headings, out int unmatched)
        {
            var levels = new int[Texts.Count];
            unmatched = 0;
            int last = -1, offset = 0;
            foreach (object[] h in headings)
            {
                string text = Convert.ToString(h[0]);
                int level = Convert.ToInt32(h[1]), est = Convert.ToInt32(h[2]);
                string want = Norm(text);
                if (want.Length == 0 || level < 1 || level > 9) continue;
                int best = -1;
                if (_byText != null && _byText.TryGetValue(want, out var list))
                {
                    long bestDistance = long.MaxValue;
                    int target = est + offset;
                    foreach (int c in list)
                    {
                        if (c <= last) continue;
                        long d = Math.Abs((long)c - target);
                        if (d < bestDistance) { bestDistance = d; best = c; }
                        else if (c > target) break;                 // הרשימה ממוינת – רק מתרחקים
                    }
                }
                else if (text.Length > IndexedLength)
                    best = MatchParagraph(text, last + 1);
                if (best < 0) { unmatched++; continue; }
                levels[best] = level;
                offset = best - est;
                last = best;
            }
            return levels;
        }

        public List<Dictionary<string, object>> Paras()
        {
            var list = new List<Dictionary<string, object>>(Texts.Count);
            for (int i = 0; i < Texts.Count; i++)
                list.Add(new Dictionary<string, object> { ["t"] = Texts[i], ["h"] = Levels[i] });
            return list;
        }

        /// <summary>הפסקה שמתאימה לכותרת שנמצאה במסמך: אותו טקסט, מהמקום שבו עצרנו והלאה.</summary>
        public int MatchParagraph(string headingText, int from)
        {
            string want = Norm(headingText);
            if (want.Length == 0) return -1;
            from = Math.Max(0, from);
            if (_byText != null && _byText.TryGetValue(want, out var list))
            {
                int k = list.BinarySearch(from);
                if (k < 0) k = ~k;
                return k < list.Count ? list[k] : -1;
            }
            if (headingText.Length <= IndexedLength) return -1;            // קצר ולא באינדקס – אין כזו פסקה
            int stop = Math.Min(Texts.Count, from + 2000);                // כותרת ארוכה מאוד (נדיר) – סריקה קצרה
            for (int i = from; i < stop; i++)
                if (Texts[i].Length > IndexedLength && Norm(Texts[i]) == want) return i;
            return -1;
        }

        /// <summary>הפסקה שמתאימה לכותרת שנמצאה במקום actualStart במסמך: אותו טקסט, והקרובה ביותר למקום
        /// לפי המיקום המשוער (כולל ההפרש שכבר נלמד – שדות ותוכן עניינים מוסיפים מקומות). כשאותה כותרת
        /// חוזרת כמה פעמים (למשל "סיכום" בכל פרק) זה מה שמבדיל ביניהן.</summary>
        public int MatchNear(string headingText, int actualStart)
        {
            string want = Norm(headingText);
            if (want.Length == 0) return -1;
            if (_byText == null || !_byText.TryGetValue(want, out var list))
                return headingText.Length > IndexedLength ? MatchParagraph(headingText, 0) : -1;
            if (list.Count == 1) return list[0];
            // המיקום המשוער קטן או שווה לאמיתי: מתחילים מהאחרונה שלפני המקום, ובודקים את השכנות
            int lo = 0, hi = list.Count - 1, k = 0;
            while (lo <= hi)
            {
                int mid = (lo + hi) / 2;
                if (Starts[list[mid]] <= actualStart + 2) { k = mid; lo = mid + 1; }
                else hi = mid - 1;
            }
            int best = -1;
            long bestDistance = long.MaxValue;
            for (int m = Math.Min(list.Count - 1, k + 1); m >= 0 && m >= k - 200; m--)
            {
                long d = Math.Abs((long)EstimatedStart(list[m]) - actualStart);
                if (d < bestDistance) { bestDistance = d; best = list[m]; }
                else if (m < k && EstimatedStart(list[m]) < actualStart) break;       // מתרחקים
            }
            return best;
        }

        /// <summary>המיקום המשוער של תחילת פסקה במסמך (כולל ההפרש שנלמד).</summary>
        public int EstimatedStart(int para) => Math.Max(0, Starts[para] + DriftAt(para));

        // ================================================================ קטע סביב תוצאה (לחלון נפרד)
        /// <summary>כ-before מילים לפני התוצאה ו-after מילים אחריה (גם מפסקאות סמוכות).</summary>
        public Excerpt Around(int para, List<int[]> ranges, int before, int after)
        {
            return Excerpt.Build(Texts, para, ranges, before, after);
        }

        /// <summary>טקסט של פסקה מ-Word (Range.Text) – באותם החלפות של תווים מיוחדים כמו ב-Build,
        /// כדי שההשוואה לפסקאות תהיה מדויקת (למשל מקף לא-שביר בכותרת).</summary>
        public static string Clean(string paragraphText)
        {
            if (paragraphText == null) return "";
            var sb = new StringBuilder(paragraphText.Length);
            foreach (char ch in paragraphText)
            {
                char c = ch;
                if (c == '\r') continue;
                switch (c)
                {
                    case '\v': case '\a': case '\f': case '\u001f': case '\u0001': case '\u0002': case '\u0013': case '\u0014': case '\u0015':
                        c = ' '; break;
                    case '\u001e':
                        c = '-'; break;
                }
                sb.Append(c);
            }
            return sb.ToString();
        }

        // ================================================================ הגעה לתוצאה (תהליך ראשי)
        public void Learn(int para, int actualStart)
        {
            if (para >= 0 && para < Starts.Count)
                lock (_drift) _drift[para] = actualStart - Starts[para];
        }

        int DriftAt(int para)
        {
            // ההפרש שנלמד בפסקה הקרובה ביותר שלפני (השדות שמוסיפים מקומות מצטברים לאורך המסמך)
            lock (_drift)
            {
                int lo = 0, hi = _drift.Count - 1, best = -1;
                while (lo <= hi)
                {
                    int mid = (lo + hi) / 2;
                    if (_drift.Keys[mid] <= para) { best = mid; lo = mid + 1; }
                    else hi = mid - 1;
                }
                return best < 0 ? 0 : _drift.Values[best];
            }
        }

        /// <summary>הטווח במסמך של התוצאה (מהמילה הראשונה עד האחרונה), או null אם לא נמצא.
        /// בלי Find ככל האפשר: Find של Word משתף את ההגדרות שלו עם החיפוש של Word עצמו ומאפס אותו.</summary>
        public Word.Range Locate(Word.Document doc, int para, List<int[]> ranges)
        {
            if (ranges.Count == 0 || para < 0 || para >= Texts.Count) return null;
            string text = Texts[para];
            int a = ranges[0][0], b = ranges[ranges.Count - 1][1];
            if (a < 0 || b > text.Length || b <= a) return null;
            string expect = text.Substring(a, b - a);
            int docEnd = doc.Content.End;
            int guess = Math.Max(0, Starts[para] + DriftAt(para));

            // 1. במקום המשוער
            Word.Range r = Check(doc, guess + a, guess + b, docEnd, expect);
            if (r != null) { Learn(para, guess); return r; }

            // 2. הפסקה עצמה (בסביבת המקום המשוער), ואז המילים בתוכה
            Word.Paragraph p = LocateParagraph(doc, para, docEnd);
            if (p != null)
            {
                Word.Range pr = p.Range;
                int ps = pr.Start;
                r = Check(doc, ps + a, ps + b, docEnd, expect);
                if (r != null) return r;
                string inPara = Clean(pr.Text);
                int k = inPara.IndexOf(expect, StringComparison.Ordinal);
                if (k >= 0 && (r = Check(doc, ps + k, ps + k + expect.Length, docEnd, expect)) != null) return r;
            }

            // 3. (נדיר) המילים עצמן בכל המסמך – רק כשהמשתמש בחר תוצאה, אף פעם לא ברקע
            r = Find(doc, Math.Max(0, guess + a - 400), docEnd, expect) ?? Find(doc, 0, docEnd, expect);
            if (r != null) Learn(para, r.Start - a);
            return r;
        }

        /// <summary>הפסקה במסמך (ל-OutlineLevel) – במקום המשוער, או בין הפסקאות הסמוכות לו (עד 60 לכל כיוון).
        /// בלי Find (נקרא ברקע לכל פסקה שנערכה). null אם לא נמצאה.</summary>
        public Word.Paragraph LocateParagraph(Word.Document doc, int para, int docEnd)
        {
            if (para < 0 || para >= Texts.Count || docEnd <= 0) return null;
            string text = Texts[para];
            int guess = Math.Min(EstimatedStart(para), docEnd - 1);
            Word.Paragraph at = doc.Range(guess, guess).Paragraphs.First;
            if (at == null) return null;
            if (IsParagraph(at, para, text)) return at;
            Word.Paragraph fwd = at, back = at;
            for (int k = 0; k < 60 && (fwd != null || back != null); k++)
            {
                if (fwd != null)
                {
                    fwd = fwd.Next();
                    if (fwd != null && IsParagraph(fwd, para, text)) return fwd;
                }
                if (back != null)
                {
                    back = back.Previous();
                    if (back != null && IsParagraph(back, para, text)) return back;
                }
            }
            return null;
        }

        bool IsParagraph(Word.Paragraph p, int para, string text)
        {
            Word.Range r = p.Range;
            if (!SameText(Clean(r.Text), text)) return false;
            Learn(para, r.Start);
            return true;
        }

        static Word.Range Check(Word.Document doc, int start, int end, int docEnd, string expect)
        {
            if (start < 0 || end > docEnd) return null;
            Word.Range r = doc.Range(start, end);
            return Same(r.Text, expect) ? r : null;
        }

        static Word.Range Find(Word.Document doc, int start, int end, string needle)
        {
            if (string.IsNullOrEmpty(needle) || start >= end) return null;
            int fullLength = needle.Length;
            if (needle.Length > 200) needle = needle.Substring(0, 200);      // Find מוגבל ל-255 תווים
            Word.Range r = doc.Range(start, end);
            Word.Find f = r.Find;
            f.ClearFormatting();
            f.Text = needle.Replace("^", "^^");
            f.Forward = true;
            f.Wrap = Word.WdFindWrap.wdFindStop;
            f.Format = false;
            f.MatchCase = false;
            f.MatchWholeWord = false;
            f.MatchWildcards = false;
            f.MatchSoundsLike = false;
            f.MatchAllWordForms = false;
            try { f.MatchDiacritics = true; } catch { }
            if (!f.Execute()) return null;
            if (fullLength > needle.Length) r.End = Math.Min(doc.Content.End, r.Start + fullLength);
            return r;
        }

        public static bool SameText(string a, string b) => Norm(a) == Norm(b);

        static bool Same(string a, string b)
        {
            return Norm(a) == Norm(b);
        }

        static string Norm(string s)
        {
            if (s == null) return "";
            var chars = new StringBuilder(s.Length);
            foreach (char c in s)
                if (!char.IsWhiteSpace(c) && c != '\a' && !char.IsControl(c)) chars.Append(c);
            return chars.ToString();
        }
    }
}
