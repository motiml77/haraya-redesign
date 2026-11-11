// קטע סביב תוצאה, לחלון "הצג בחלון נפרד": כ-40 מילים לפני ההתאמה וכ-40 אחריה. אם הפסקה של התוצאה
// קצרה – ממשיכים לפסקאות הסמוכות (כל פסקה בשורה משלה), רק בתחום [lo, hi] – למשל רק בתוך אותה הערה.
// "…" במקום שבו פסקה נחתכה.
// בלי Word ובלי ממשק – אפשר לבדוק אותו לבד.
using System;
using System.Collections.Generic;
using System.Text;

namespace HebDocSearch.WordAddin
{
    internal sealed class Excerpt
    {
        public string Text = "";
        public List<int[]> Marks = new List<int[]>();     // [התחלה, אורך] בתוך Text – המילים שנמצאו

        /// <summary>texts – הפסקאות של המסמך; ranges – מקומות ההתאמות בתוך פסקה para (תווים);
        /// lo..hi – הפסקאות הסמוכות שמותר להמשיך אליהן (ברירת מחדל: כל המסמך).</summary>
        public static Excerpt Build(IList<string> texts, int para, List<int[]> ranges, int before, int after,
                                    int lo = 0, int hi = int.MaxValue)
        {
            if (texts == null || para < 0 || para >= texts.Count || ranges == null || ranges.Count == 0) return null;
            lo = Math.Max(0, Math.Min(lo, para));
            hi = Math.Min(texts.Count - 1, Math.Max(hi, para));
            string t = texts[para] ?? "";
            int a = Math.Max(0, Math.Min(t.Length, ranges[0][0]));
            int b = Math.Max(a, Math.Min(t.Length, ranges[ranges.Count - 1][1]));

            int needBefore = before, needAfter = after;
            int cut = TailStart(t, a, ref needBefore);
            int end = HeadEnd(t, b, ref needAfter);
            string lead = cut > 0 ? "… " : "";
            string body = t.Substring(cut, end - cut).TrimEnd();
            string current = lead + body + (end < t.Length && t.Substring(end).Trim().Length > 0 ? " …" : "");

            var prev = new List<string>();
            for (int p = para - 1; needBefore > 0 && p >= lo && para - p <= 12; p--)
            {
                string pt = (texts[p] ?? "").Trim();
                if (pt.Length == 0) continue;
                int s0 = TailStart(pt, pt.Length, ref needBefore);
                prev.Insert(0, (s0 > 0 ? "… " : "") + pt.Substring(s0));
            }
            var next = new List<string>();
            for (int p = para + 1; needAfter > 0 && p <= hi && p - para <= 12; p++)
            {
                string pt = (texts[p] ?? "").Trim();
                if (pt.Length == 0) continue;
                int e0 = HeadEnd(pt, 0, ref needAfter);
                next.Add(pt.Substring(0, e0).TrimEnd() + (e0 < pt.Length ? " …" : ""));
            }

            var sb = new StringBuilder();
            foreach (string x in prev) sb.Append(x).Append('\n');
            int currentStart = sb.Length + lead.Length;
            sb.Append(current);
            foreach (string x in next) sb.Append('\n').Append(x);

            var ex = new Excerpt { Text = sb.ToString() };
            foreach (var r in ranges)
            {
                int ra = Math.Max(cut, Math.Min(cut + body.Length, r[0]));
                int rb = Math.Max(ra, Math.Min(cut + body.Length, r[1]));
                if (rb > ra) ex.Marks.Add(new[] { currentStart + ra - cut, rb - ra });
            }
            return ex;
        }

        /// <summary>תחילת need המילים שלפני end (או 0); need יורד במספר המילים שנלקחו.</summary>
        static int TailStart(string s, int end, ref int need)
        {
            int i = end;
            while (need > 0)
            {
                while (i > 0 && char.IsWhiteSpace(s[i - 1])) i--;
                if (i == 0) break;
                while (i > 0 && !char.IsWhiteSpace(s[i - 1])) i--;
                need--;
            }
            return i;
        }

        /// <summary>סוף need המילים שאחרי start (או סוף המחרוזת); need יורד במספר המילים שנלקחו.</summary>
        static int HeadEnd(string s, int start, ref int need)
        {
            int i = start;
            while (need > 0)
            {
                while (i < s.Length && char.IsWhiteSpace(s[i])) i++;
                if (i >= s.Length) break;
                while (i < s.Length && !char.IsWhiteSpace(s[i])) i++;
                need--;
            }
            return i;
        }
    }
}
