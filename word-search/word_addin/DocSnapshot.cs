// תמונת מצב של טקסט המסמך: לכל פסקה – הטקסט, המיקום שלה במסמך ורמת הכותרת (1–9, או 0 לגוף).
// נקראת מחדש רק כשהטקסט השתנה. המיקום של תוצאה = תחילת הפסקה + מיקום המילה בתוך הפסקה.
using System;
using System.Collections.Generic;

namespace HebDocSearch.WordAddin
{
    internal sealed class DocSnapshot
    {
        public string Key;
        public readonly List<int> Starts = new List<int>();
        public readonly List<string> Texts = new List<string>();
        public readonly List<int> Levels = new List<int>();

        /// <summary>קורא את המסמך, או מחזיר את התמונה הקודמת אם הטקסט לא השתנה.</summary>
        public static DocSnapshot Read(dynamic doc, DocSnapshot previous)
        {
            string full = Convert.ToString(doc.Content.Text) ?? "";
            string name;
            try { name = Convert.ToString(doc.FullName); } catch { name = "document"; }
            string key = name + "|" + full.Length + "|" + full.GetHashCode().ToString("x");
            if (previous != null && previous.Key == key) return previous;

            var snap = new DocSnapshot { Key = key };
            foreach (dynamic p in doc.Paragraphs)
            {
                dynamic r = p.Range;
                int start = (int)r.Start;
                string text = Convert.ToString(r.Text) ?? "";
                text = text.TrimEnd('\r', '\a', '\n');
                // תווים מיוחדים של Word מוחלפים ברווח – באורך זהה, כדי שהמיקומים לא יזוזו
                text = text.Replace('\v', ' ').Replace('\a', ' ').Replace('\f', ' ').Replace('\u001e', '-').Replace('\u001f', ' ');
                int level;
                try { level = (int)p.OutlineLevel; } catch { level = 10; }
                snap.Starts.Add(start);
                snap.Texts.Add(text);
                snap.Levels.Add(level >= 1 && level <= 9 ? level : 0);
            }
            return snap;
        }

        public List<Dictionary<string, object>> Paras()
        {
            var list = new List<Dictionary<string, object>>(Texts.Count);
            for (int i = 0; i < Texts.Count; i++)
                list.Add(new Dictionary<string, object> { ["t"] = Texts[i], ["h"] = Levels[i] });
            return list;
        }

        /// <summary>מסמן במסמך את התוצאה (מהמילה הראשונה עד האחרונה) וגולל אליה.</summary>
        public void Select(dynamic window, int para, List<int[]> ranges)
        {
            if (ranges.Count == 0 || para < 0 || para >= Starts.Count) return;
            dynamic doc = window.Document;
            int ps = Starts[para];
            int a = ranges[0][0], b = ranges[ranges.Count - 1][1];
            string text = Texts[para];
            string expect = (a >= 0 && b <= text.Length && b > a) ? text.Substring(a, b - a) : "";
            dynamic rng = doc.Range(ps + a, ps + b);
            if (!Same(Convert.ToString(rng.Text), expect))
            {
                // שדות, תמונות או קישורים בתוך הפסקה מזיזים את המיקומים – מחפשים את הטקסט בתוך הפסקה
                rng = FindInParagraph(doc, ps, text, expect, text.Substring(ranges[0][0], ranges[0][1] - ranges[0][0]));
                if (rng == null) throw new Exception("הטקסט השתנה מאז החיפוש – חפשו שוב");
            }
            rng.Select();
            try { window.ScrollIntoView(rng, true); } catch { }
        }

        static dynamic FindInParagraph(dynamic doc, int paraStart, string paraText, string phrase, string firstWord)
        {
            foreach (string needle in new[] { phrase, firstWord })
            {
                if (string.IsNullOrEmpty(needle) || needle.Length > 250) continue;
                dynamic r = doc.Range(paraStart, paraStart + paraText.Length + 40);
                dynamic f = r.Find;
                f.ClearFormatting();
                f.Text = needle;
                f.Forward = true;
                f.Wrap = 0;              // wdFindStop
                f.MatchCase = false;
                f.MatchWholeWord = false;
                f.MatchWildcards = false;
                if ((bool)f.Execute()) return r;
            }
            return null;
        }

        static bool Same(string a, string b)
        {
            return Norm(a) == Norm(b);
        }

        static string Norm(string s)
        {
            if (s == null) return "";
            var chars = new System.Text.StringBuilder(s.Length);
            foreach (char c in s)
                if (!char.IsWhiteSpace(c) && c != '\a') chars.Append(c);
            return chars.ToString();
        }
    }
}
