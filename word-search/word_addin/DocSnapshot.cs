// תמונת מצב של טקסט המסמך: לכל פסקה – הטקסט, המיקום שלה במסמך ורמת הכותרת (1–9, או 0 לגוף).
// נבנית פסקה אחר פסקה (כדי שאפשר יהיה לקרוא מסמך גדול במנות קטנות ברקע), ונשמרת גם בדיסק:
// כשפותחים שוב קובץ שלא השתנה – התמונה נטענת מהדיסק בלי לקרוא את המסמך מחדש.
// המיקום של תוצאה = תחילת הפסקה + מיקום המילה בתוך הפסקה.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

namespace HebDocSearch.WordAddin
{
    internal sealed class DocSnapshot
    {
        public string Name;                 // FullName של המסמך
        public string Key;                  // שם + אורך + טביעת אצבע של הטקסט – מזהה את הגרסה אצל רכיב העזר
        public int End;                     // Content.End – בדיקה זולה אם המסמך השתנה
        public List<int> Starts = new List<int>();
        public List<string> Texts = new List<string>();
        public List<int> Levels = new List<int>();

        // ----- טביעת אצבע של הטקסט (יציבה גם בין הפעלות, בניגוד ל-GetHashCode) -----
        public static string KeyOf(string name, string fullText)
        {
            ulong h = 14695981039346656037UL;
            foreach (char c in fullText)
            {
                h ^= c;
                h *= 1099511628211UL;
            }
            return name + "|" + fullText.Length + "|" + h.ToString("x16");
        }

        public static string NameOf(dynamic doc)
        {
            try { return Convert.ToString(doc.FullName); } catch { return "document"; }
        }

        /// <summary>מוסיף פסקה אחת (נקרא במנות מתוך DocIndexer, או ברצף מ-ReadAll).</summary>
        public void Add(dynamic paragraph)
        {
            dynamic r = paragraph.Range;
            int start = (int)r.Start;
            string text = Convert.ToString(r.Text) ?? "";
            text = text.TrimEnd('\r', '\a', '\n');
            // תווים מיוחדים של Word מוחלפים באורך זהה, כדי שהמיקומים לא יזוזו
            text = text.Replace('\v', ' ').Replace('\a', ' ').Replace('\f', ' ').Replace('\u001e', '-').Replace('\u001f', ' ');
            int level;
            try { level = (int)paragraph.OutlineLevel; } catch { level = 10; }
            Starts.Add(start);
            Texts.Add(text);
            Levels.Add(level >= 1 && level <= 9 ? level : 0);
        }

        /// <summary>קריאה מלאה ברצף (כשמחפשים לפני שהקריאה ברקע הסתיימה).</summary>
        public static DocSnapshot ReadAll(dynamic doc)
        {
            string name = NameOf(doc);
            string full = Convert.ToString(doc.Content.Text) ?? "";
            var snap = new DocSnapshot { Name = name, Key = KeyOf(name, full), End = (int)doc.Content.End };
            foreach (dynamic p in doc.Paragraphs) snap.Add(p);
            return snap;
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

        // ================================================================ שמירה בדיסק
        static string CacheDir
        {
            get
            {
                string dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                                          "HebWordSearch", "word-cache");
                Directory.CreateDirectory(dir);
                return dir;
            }
        }

        static string CachePath(string name)
        {
            using (var sha = SHA1.Create())
            {
                byte[] h = sha.ComputeHash(Encoding.UTF8.GetBytes(name.ToLowerInvariant()));
                return Path.Combine(CacheDir, BitConverter.ToString(h).Replace("-", "").Substring(0, 24) + ".json.gz");
            }
        }

        static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };

        /// <summary>שומר את התמונה עם תאריך וגודל הקובץ – רק לקובץ שמור שלא שונה מאז הפתיחה.</summary>
        public void Save(dynamic doc)
        {
            try
            {
                if (!(bool)doc.Saved || string.IsNullOrEmpty(Convert.ToString(doc.Path))) return;
                var file = new FileInfo(Name);
                if (!file.Exists) return;
                var data = new Dictionary<string, object>
                {
                    ["name"] = Name, ["key"] = Key, ["end"] = End,
                    ["mtime"] = file.LastWriteTimeUtc.Ticks.ToString(), ["size"] = file.Length.ToString(),
                    ["starts"] = Starts, ["texts"] = Texts, ["levels"] = Levels,
                };
                string path = CachePath(Name);
                using (var fs = File.Create(path + ".tmp"))
                using (var gz = new GZipStream(fs, CompressionLevel.Fastest))
                using (var w = new StreamWriter(gz, new UTF8Encoding(false)))
                    w.Write(Json.Serialize(data));
                File.Copy(path + ".tmp", path, true);
                File.Delete(path + ".tmp");
                Prune();
            }
            catch { }
        }

        /// <summary>טוען תמונה שמורה אם הקובץ בדיסק לא השתנה והמסמך הפתוח לא שונה מאז שנפתח.</summary>
        public static DocSnapshot Load(dynamic doc)
        {
            try
            {
                if (!(bool)doc.Saved) return null;
                string name = NameOf(doc);
                string path = CachePath(name);
                var file = new FileInfo(name);
                if (!File.Exists(path) || !file.Exists) return null;
                Dictionary<string, object> d;
                using (var fs = File.OpenRead(path))
                using (var gz = new GZipStream(fs, CompressionMode.Decompress))
                using (var r = new StreamReader(gz, Encoding.UTF8))
                    d = Json.Deserialize<Dictionary<string, object>>(r.ReadToEnd());
                if (Convert.ToString(d["name"]) != name
                    || Convert.ToString(d["mtime"]) != file.LastWriteTimeUtc.Ticks.ToString()
                    || Convert.ToString(d["size"]) != file.Length.ToString()
                    || Convert.ToInt32(d["end"]) != (int)doc.Content.End)
                    return null;
                var snap = new DocSnapshot { Name = name, Key = Convert.ToString(d["key"]), End = Convert.ToInt32(d["end"]) };
                foreach (object x in (System.Collections.IList)d["starts"]) snap.Starts.Add(Convert.ToInt32(x));
                foreach (object x in (System.Collections.IList)d["texts"]) snap.Texts.Add(Convert.ToString(x));
                foreach (object x in (System.Collections.IList)d["levels"]) snap.Levels.Add(Convert.ToInt32(x));
                return snap.Texts.Count == snap.Starts.Count && snap.Texts.Count == snap.Levels.Count ? snap : null;
            }
            catch { return null; }
        }

        static void Prune()
        {
            // שומרים עד 60 מסמכים אחרונים
            var files = new DirectoryInfo(CacheDir).GetFiles("*.json.gz");
            if (files.Length <= 60) return;
            Array.Sort(files, (x, y) => y.LastWriteTimeUtc.CompareTo(x.LastWriteTimeUtc));
            for (int i = 60; i < files.Length; i++)
            {
                try { files[i].Delete(); } catch { }
            }
        }

        // ================================================================ סימון תוצאה במסמך
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
                string first = (ranges[0][1] <= text.Length) ? text.Substring(ranges[0][0], ranges[0][1] - ranges[0][0]) : "";
                rng = FindInParagraph(doc, ps, text, expect, first);
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
            var chars = new StringBuilder(s.Length);
            foreach (char c in s)
                if (!char.IsWhiteSpace(c) && c != '\a') chars.Append(c);
            return chars.ToString();
        }
    }
}
