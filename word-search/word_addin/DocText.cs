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
    internal sealed class DocText
    {
        public readonly string TextHash;            // אורך + FNV-1a של כל הטקסט
        public readonly List<string> Texts;
        public readonly List<int> Starts;           // מיקום משוער של תחילת כל פסקה במסמך
        public readonly int[] Levels;               // 1–9 כותרת, 0 גוף
        public readonly bool HasLevels;             // האם רמות הכותרות כבר נקראו מהמסמך
        public readonly string Key;                 // מזהה הגרסה אצל רכיב העזר (טקסט + כותרות)

        // הפרש שנלמד בין המיקום המשוער למיקום האמיתי (פסקה → הפרש). נגיש רק מהתהליך הראשי.
        readonly SortedList<int, int> _drift = new SortedList<int, int>();

        DocText(string hash, List<string> texts, List<int> starts, int[] levels, bool hasLevels)
        {
            TextHash = hash;
            Texts = texts;
            Starts = starts;
            Levels = levels;
            HasLevels = hasLevels;
            Key = hash + "/" + (hasLevels ? Fnv(levels) : "nolevels");
        }

        // ================================================================ בנייה (בלי Word)
        public static string Hash(string raw)
        {
            return raw.Length + ":" + Fnv(raw);
        }

        static string Fnv(string s)
        {
            ulong h = 14695981039346656037UL;
            foreach (char c in s)
            {
                h ^= c;
                h *= 1099511628211UL;
            }
            return h.ToString("x16");
        }

        static string Fnv(int[] levels)
        {
            var sb = new StringBuilder(levels.Length);
            foreach (int l in levels) sb.Append((char)('0' + l));
            return Fnv(sb.ToString());
        }

        /// <summary>מחלק את הטקסט לפסקאות. previous – גרסה קודמת של אותו מסמך: רמות הכותרות
        /// עוברות לפסקאות שהטקסט שלהן זהה (לפי הסדר), עד שהכותרות ייקראו שוב.</summary>
        public static DocText Build(string raw, DocText previous = null)
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

            var levels = new int[texts.Count];
            bool hasLevels = false;
            if (previous != null && previous.HasLevels)
            {
                // הכותרות שהיו – לפי הטקסט ובאותו סדר
                var queue = new Dictionary<string, Queue<int>>();
                for (int i = 0; i < previous.Texts.Count; i++)
                {
                    if (previous.Levels[i] == 0) continue;
                    string t = previous.Texts[i];
                    if (!queue.TryGetValue(t, out var q)) queue[t] = q = new Queue<int>();
                    q.Enqueue(previous.Levels[i]);
                }
                for (int i = 0; i < texts.Count; i++)
                    if (queue.TryGetValue(texts[i], out var q) && q.Count > 0) levels[i] = q.Dequeue();
                hasLevels = true;
            }
            return new DocText(Hash(raw), texts, starts, levels, hasLevels);
        }

        public DocText WithLevels(int[] levels)
        {
            var copy = new DocText(TextHash, Texts, Starts, levels, true);
            foreach (var kv in _drift) copy._drift[kv.Key] = kv.Value;
            return copy;
        }

        public int Headings
        {
            get { int n = 0; foreach (int l in Levels) if (l > 0) n++; return n; }
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
            int stop = Math.Min(Texts.Count, from + 20000);
            for (int i = Math.Max(0, from); i < stop; i++)
                if (Norm(Texts[i]) == want) return i;
            return -1;
        }

        public static string Clean(string paragraphText)
        {
            if (paragraphText == null) return "";
            var sb = new StringBuilder(paragraphText.Length);
            foreach (char c in paragraphText)
                if (c != '\r' && c != '\a') sb.Append(c == '\v' || c == '\f' ? ' ' : c);
            return sb.ToString();
        }

        // ================================================================ הגעה לתוצאה (תהליך ראשי)
        public void Learn(int para, int actualStart)
        {
            if (para >= 0 && para < Starts.Count) _drift[para] = actualStart - Starts[para];
        }

        int DriftAt(int para)
        {
            // ההפרש שנלמד בפסקה הקרובה ביותר שלפני (השדות שמוסיפים מקומות מצטברים לאורך המסמך)
            int lo = 0, hi = _drift.Count - 1, best = -1;
            while (lo <= hi)
            {
                int mid = (lo + hi) / 2;
                if (_drift.Keys[mid] <= para) { best = mid; lo = mid + 1; }
                else hi = mid - 1;
            }
            return best < 0 ? 0 : _drift.Values[best];
        }

        /// <summary>הטווח במסמך של התוצאה (מהמילה הראשונה עד האחרונה), או null אם לא נמצא.</summary>
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

            // 2. מוצאים את הפסקה עצמה לפי תחילתה, ואז את המילים בתוכה
            int lead = 0;
            while (lead < text.Length && char.IsWhiteSpace(text[lead])) lead++;
            string prefix = text.Substring(lead, Math.Min(80, text.Length - lead)).TrimEnd();
            if (prefix.Length >= 2)
            {
                Word.Range p = Find(doc, Math.Max(0, guess - 400), docEnd, prefix)
                               ?? Find(doc, 0, Math.Min(docEnd, guess + 400), prefix);
                if (p != null)
                {
                    int ps = p.Start - lead;
                    r = Check(doc, ps + a, ps + b, docEnd, expect)
                        ?? Find(doc, p.Start, Math.Min(docEnd, ps + text.Length + 2000), expect);
                    if (r != null) { Learn(para, ps); return r; }
                }
            }

            // 3. המילים עצמן, קדימה מהמקום המשוער ואז מתחילת המסמך
            r = Find(doc, Math.Max(0, guess + a - 400), docEnd, expect) ?? Find(doc, 0, docEnd, expect);
            if (r != null) Learn(para, r.Start - a);
            return r;
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
