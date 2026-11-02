// הכנת המסמכים לחיפוש מאחורי הקלעים – לפי ההנחיות של Microsoft לתוספים:
//   * כל גישה למודל של Word רק מהתהליך הראשי (המודל הוא STA), ומעט ככל האפשר;
//   * עבודה כבדה (חלוקה, טביעת אצבע, בניית מפת החיפוש) – על תהליך נפרד / ברכיב העזר;
//   * שום דבר בזמן הפתיחה: אחרי שהמסמך נפתח מחכים שהמשתמש לא נוגע במקלדת ובעכבר,
//     ש-Word לא מציג חלון דו-שיח ולא שומר/מדפיס ברקע – ורק אז קוראים את הטקסט (קריאה אחת).
//   * הכותרות נקראות במנות קצרות (עד ~40ms) בזמני מנוחה, כך ש-Word אף פעם לא נתקע: חיפוש של Word
//     לפי סגנונות "כותרת 1" עד "כותרת 9" (Find עם Style – רק הכותרות עצמן, בלי לעבור על כל פסקה);
//     ואם אין כאלה – רמת החלוקה (OutlineLevel) של הפסקאות הקצרות. כשבוחרים "כותרות" – משלימים מיד.
//   * בחיפוש קוראים את הטקסט מחדש רק אם ייתכן שהמסמך השתנה מאז הקריאה הקודמת: האורך השתנה,
//     המסמך נשמר, או שהסמן זז במסמך שיש בו שינויים שלא נשמרו (כל הקלדה מזיזה את הסמן).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Word = Microsoft.Office.Interop.Word;

namespace HebDocSearch.WordAddin
{
    internal sealed class Preparer : IDisposable
    {
        internal sealed class DocState
        {
            public Word.Document Doc;
            public DocText Text;                // הגרסה האחרונה שנקראה
            public string IndexedKey;           // הגרסה שרכיב העזר כבר בנה לה מפת חיפוש
            public bool NeedsRead = true;
            public bool NeedsHeadings;
            public bool Reading, Indexing;
            public DateTime NotBefore;
            public HeadingScan Scan;
            public string Error, HeadingsError;

            // מה היה כשקראנו את הטקסט – כדי לדעת אם צריך לקרוא שוב
            public int ReadEnd = -1;
            public bool ReadSaved;
            public bool SelChanged, SaveEvent;
        }

        internal sealed class HeadingScan
        {
            public DocText Text;
            public int[] Levels;
            public int Style = 1;               // סגנון "כותרת N" שמחפשים עכשיו (1–9)
            public Word.Range Range;            // הטווח של החיפוש הנוכחי (מתקדם אחרי כל כותרת)
            public int LastEnd = -1;
            public bool ByOutline;              // אין סגנונות כותרת – בודקים רמת חלוקה של פסקאות קצרות
            public int OutlineIndex;
            public int Found, Failures;
            public Stopwatch Time = new Stopwatch();
        }

        const int SliceMs = 40;
        const int ReadIdleMs = 1500;
        const int SliceIdleMs = 800;

        readonly ThisAddIn _addin;
        readonly HelperClient _helper;
        readonly Control _ui;                    // להחזרת תוצאות מהתהליך הנפרד לתהליך הראשי
        readonly Timer _timer = new Timer { Interval = 400 };
        readonly List<DocState> _docs = new List<DocState>();
        readonly HashSet<string> _sent = new HashSet<string>();
        readonly JavaScriptSerializer _json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        readonly DateTime _started = DateTime.Now;
        bool _openDocsQueued;
        int _ignoreSelectionUntil;

        public Preparer(ThisAddIn addin, HelperClient helper)
        {
            _addin = addin;
            _helper = helper;
            _ui = new Control();
            IntPtr unused = _ui.Handle;          // יוצר את החלון הנסתר בתהליך הראשי
            _timer.Tick += (s, e) => Tick();
            _timer.Start();
        }

        // ================================================================ מצב המסמכים
        DocState Find(Word.Document doc)
        {
            foreach (var s in _docs)
                if (ReferenceEquals(s.Doc, doc)) return s;
            return null;
        }

        DocState StateOf(Word.Document doc)
        {
            var s = Find(doc);
            if (s == null)
            {
                s = new DocState { Doc = doc, NotBefore = DateTime.Now };
                _docs.Add(s);
            }
            return s;
        }

        /// <summary>מסמך נפתח: רק רושמים אותו. ההכנה תתחיל כש-Word יתפנה.</summary>
        public void Enqueue(Word.Document doc, int delayMs)
        {
            bool isNew = Find(doc) == null;
            var s = StateOf(doc);
            DateTime when = DateTime.Now.AddMilliseconds(delayMs);
            if (isNew || when < s.NotBefore) s.NotBefore = when;
            _timer.Start();
        }

        public void Forget(Word.Document doc)
        {
            var s = Find(doc);
            if (s != null) _docs.Remove(s);
        }

        public string Status(Word.Document doc)
        {
            var s = Find(doc);
            if (s == null || (s.Text == null && !s.Reading))
                return "המסמך יוכן לחיפוש כש-Word יתפנה. אפשר כבר לחפש.";
            if (s.Error != null) return "אפשר לחפש. (ההכנה ברקע נכשלה: " + s.Error + ")";
            if (s.Text == null || s.Reading || s.Indexing && s.IndexedKey == null)
                return "מכין את המסמך לחיפוש…";
            string counts = Words.Paragraphs(s.Text.Texts.Count);
            if (!s.Text.HasLevels || s.NeedsHeadings)
                return "המסמך מוכן לחיפוש · " + counts + " · קורא את הכותרות…";
            return "המסמך מוכן לחיפוש · " + counts + " · " + Words.Headings(s.Text.Headings);
        }

        // ================================================================ זיהוי שינויים (בלי לקרוא את המסמך)
        /// <summary>הסמן זז באחד החלונות (כל הקלדה מזיזה אותו). בלי שום קריאה ל-Word – זה קורה הרבה.</summary>
        public void OnSelectionChange()
        {
            if (unchecked(Environment.TickCount - _ignoreSelectionUntil) < 0) return;     // הבחירה שלנו
            foreach (var s in _docs) s.SelChanged = true;
        }

        public void OnBeforeSave(Word.Document doc)
        {
            var s = Find(doc);
            if (s != null) s.SaveEvent = true;
        }

        /// <summary>בחירה של תוצאה במסמך (לא נחשבת עריכה של המשתמש).</summary>
        public void SelectInDocument(Action select)
        {
            _ignoreSelectionUntil = unchecked(Environment.TickCount + 400);
            try { select(); }
            finally { _ignoreSelectionUntil = unchecked(Environment.TickCount + 300); }
        }

        static bool AutoSaveOn(Word.Document doc)
        {
            try { return (bool)((dynamic)doc).AutoSaveOn; }     // Word 2016 ואילך
            catch { return false; }
        }

        /// <summary>האם הטקסט שכבר נקרא עדיין נכון (כמה קריאות זולות ל-Word, בלי לקרוא את הטקסט).</summary>
        bool Fresh(DocState s)
        {
            if (s.Text == null || s.ReadEnd < 0 || s.SaveEvent) return false;
            if (s.Doc.Content.End != s.ReadEnd) return false;
            if (!s.SelChanged) return true;
            // הסמן זז: אם המסמך היה שמור כשקראנו ועדיין שמור (ואין שמירה אוטומטית) – לא נערך
            return s.ReadSaved && s.Doc.Saved && !AutoSaveOn(s.Doc);
        }

        public bool WillRead(Word.Document doc)
        {
            var s = Find(doc);
            try { return s == null || !Fresh(s); }
            catch { return true; }
        }

        string ReadText(DocState s)
        {
            var sw = Stopwatch.StartNew();
            string raw = s.Doc.Content.Text;           // הקריאה היחידה של הטקסט מ-Word
            s.ReadEnd = s.Doc.Content.End;
            s.ReadSaved = s.Doc.Saved;
            s.SelChanged = false;
            s.SaveEvent = false;
            Log.Write($"read {raw.Length:N0} chars in {sw.ElapsedMilliseconds}ms");
            return raw;
        }

        // ================================================================ הלולאה בזמני מנוחה
        void Tick()
        {
            try
            {
                if (!_openDocsQueued && (DateTime.Now - _started).TotalSeconds >= 3)
                {
                    if (!UserIdle(ReadIdleMs)) return;
                    _openDocsQueued = true;
                    QueueOpenDocuments();
                }

                DocState next = null;
                bool pending = !_openDocsQueued;
                foreach (var s in _docs)
                {
                    if (s.Reading || s.Indexing) { pending = true; continue; }
                    if (!s.NeedsRead && !s.NeedsHeadings) continue;
                    pending = true;
                    if (s.NotBefore <= DateTime.Now && next == null) next = s;
                }
                if (!pending) { _timer.Stop(); return; }
                if (next == null) return;

                if (next.NeedsRead)
                {
                    if (WordIsFree(ReadIdleMs)) BeginRead(next);
                }
                else if (WordIsFree(SliceIdleMs))
                {
                    HeadingSlice(next, SliceMs);
                }
            }
            catch (COMException e)
            {
                // Word עסוק (למשל חלון דו-שיח או עריכה בתא) – מנסים שוב בעוד רגע
                Log.Write("busy: " + e.Message);
                foreach (var s in _docs) if (s.NotBefore < DateTime.Now.AddSeconds(2)) s.NotBefore = DateTime.Now.AddSeconds(2);
            }
            catch (Exception e)
            {
                Log.Error("tick", e);
            }
        }

        void QueueOpenDocuments()
        {
            int n = 0;
            foreach (Word.Document d in _addin.Application.Documents)
            {
                Enqueue(d, 0);
                if (++n >= 20) break;
            }
        }

        // ================================================================ קריאת הטקסט
        void BeginRead(DocState s)
        {
            if (Fresh(s)) { s.NeedsRead = false; return; }
            string raw = ReadText(s);
            DocText previous = s.Text;
            s.NeedsRead = false;
            s.Reading = true;
            s.Error = null;
            Task.Run(() =>
            {
                try
                {
                    DocText dt = previous != null && previous.TextHash == DocText.Hash(raw) ? previous : DocText.Build(raw, previous);
                    Post(() =>
                    {
                        s.Reading = false;
                        if (!_docs.Contains(s)) return;
                        Adopt(s, dt, previous);
                        BeginIndex(s, dt);
                    });
                }
                catch (Exception e)
                {
                    Post(() => { s.Reading = false; s.Error = e.Message; Log.Error("read", e); });
                }
            });
        }

        /// <summary>גרסה חדשה של הטקסט: נשמרת, והכותרות ייקראו (שוב) בזמן מנוחה אם צריך.</summary>
        void Adopt(DocState s, DocText dt, DocText previous)
        {
            if (dt == s.Text) return;
            s.Text = dt;
            if (dt != previous || !dt.HasLevels)
            {
                s.NeedsHeadings = true;
                s.Scan = null;
                s.NotBefore = DateTime.Now.AddSeconds(1);
                _timer.Start();
            }
        }

        void BeginIndex(DocState s, DocText dt)
        {
            if (s.IndexedKey == dt.Key || s.Indexing) return;
            s.Indexing = true;
            Task.Run(() =>
            {
                try
                {
                    var t0 = Stopwatch.StartNew();
                    var reply = Ask(new Dictionary<string, object> { ["cmd"] = "index", ["doc"] = dt.Key }, dt);
                    bool ok = Ok(reply);
                    Post(() =>
                    {
                        s.Indexing = false;
                        if (ok) s.IndexedKey = dt.Key;
                        else s.Error = reply.ContainsKey("error") ? Convert.ToString(reply["error"]) : "שגיאה";
                        Log.Write($"index {dt.Texts.Count:N0} paragraphs ({dt.Headings} headings) in {t0.ElapsedMilliseconds}ms ok={ok}");
                        if (s.Text != null && s.Text.Key != s.IndexedKey && ok) BeginIndex(s, s.Text);
                    });
                }
                catch (Exception e)
                {
                    Post(() => { s.Indexing = false; s.Error = e.Message; Log.Error("index", e); });
                }
            });
        }

        // ================================================================ הכותרות, במנות קצרות
        /// <summary>מנה אחת של קריאת הכותרות (עד budgetMs). מחזיר true כשהסתיים.</summary>
        bool HeadingSlice(DocState s, int budgetMs)
        {
            if (s.Text == null) { s.NeedsHeadings = false; return true; }
            var sw = Stopwatch.StartNew();
            var scan = s.Scan;
            if (scan == null || scan.Text != s.Text)
                scan = s.Scan = new HeadingScan { Text = s.Text, Levels = new int[s.Text.Texts.Count] };
            scan.Time.Start();
            bool done = false;
            try
            {
                int docEnd = s.Doc.Content.End;
                while (!done && sw.ElapsedMilliseconds < budgetMs)
                {
                    if (!scan.ByOutline)
                    {
                        if (scan.Style > 9)
                        {
                            if (scan.Found > 0 || scan.Text.Texts.Count > 60000) { done = true; break; }
                            scan.ByOutline = true;                  // אין סגנונות כותרת – לפי רמת חלוקה
                            continue;
                        }
                        if (scan.Range == null)
                        {
                            scan.Range = s.Doc.Content;
                            StyleFind(s.Doc, scan.Range.Find, scan.Style);
                            scan.LastEnd = -1;
                        }
                        if (!scan.Range.Find.Execute() || scan.Range.End <= scan.LastEnd)
                        {
                            scan.Range = null;
                            scan.Style++;
                            continue;
                        }
                        scan.LastEnd = scan.Range.End;
                        TakeFound(scan, scan.Range.Text, scan.Range.Start, scan.Style);
                        if (scan.LastEnd >= docEnd)
                        {
                            scan.Range = null;
                            scan.Style++;
                            continue;
                        }
                        scan.Range.Collapse(Word.WdCollapseDirection.wdCollapseEnd);
                    }
                    else
                    {
                        if (scan.OutlineIndex >= scan.Text.Texts.Count) { done = true; break; }
                        int i = scan.OutlineIndex++;
                        string t = scan.Text.Texts[i];
                        if (t.Trim().Length == 0 || t.Length > 200) continue;
                        int pos = scan.Text.EstimatedStart(i);
                        if (pos >= docEnd) continue;
                        Word.Paragraph p = s.Doc.Range(pos, pos).Paragraphs.First;
                        int level = (int)p.OutlineLevel;                     // 10 = גוף הטקסט
                        if (level < 1 || level > 9) continue;
                        Word.Range pr = p.Range;
                        if (!DocText.SameText(DocText.Clean(pr.Text), t)) continue;
                        scan.Levels[i] = level;
                        scan.Found++;
                        scan.Text.Learn(i, pr.Start);
                    }
                }
            }
            catch (Exception e)
            {
                // Word עסוק (חלון דו-שיח, עריכה בתא…) – מנסים שוב; אחרי 3 כישלונות – מסתפקים במה שנמצא
                scan.Failures++;
                Log.Write($"headings: attempt failed ({scan.Failures}): {e.Message}");
                if (scan.Failures < 3)
                {
                    s.NotBefore = DateTime.Now.AddSeconds(2);
                    scan.Time.Stop();
                    return false;
                }
                s.HeadingsError = e.Message;
                done = true;
            }
            scan.Time.Stop();
            if (!done) return false;                                      // ממשיכים במנה הבאה

            ClearFind(s.Doc, scan);
            s.Scan = null;
            s.NeedsHeadings = false;
            DocText withLevels = scan.Text.WithLevels(scan.Levels);
            if (s.Text == scan.Text) s.Text = withLevels;
            Log.Write($"headings: {withLevels.Headings} ({(scan.ByOutline ? "outline levels" : "heading styles")}) in {scan.Time.ElapsedMilliseconds}ms");
            BeginIndex(s, s.Text);
            return true;
        }

        /// <summary>חיפוש של Word לפי הסגנון המובנה "כותרת N" (לא תלוי בשפת Office).</summary>
        static void StyleFind(Word.Document doc, Word.Find f, int level)
        {
            f.ClearFormatting();
            f.Text = "";
            object style = doc.Styles[(object)(Word.WdBuiltinStyle)(-(level + 1))];     // wdStyleHeading1 = -2
            f.set_Style(ref style);
            f.Format = true;
            f.Forward = true;
            f.Wrap = Word.WdFindWrap.wdFindStop;
            f.MatchCase = false;
            f.MatchWholeWord = false;
            f.MatchWildcards = false;
        }

        /// <summary>החיפוש של Word זוכר את העיצוב האחרון (גם בחלון "חיפוש והחלפה") – מנקים אחרינו.</summary>
        static void ClearFind(Word.Document doc, HeadingScan scan)
        {
            try { scan.Range?.Find.ClearFormatting(); } catch { }
            try
            {
                var f = doc.Content.Find;
                f.ClearFormatting();
                f.Format = false;
            }
            catch { }
            scan.Range = null;
        }

        /// <summary>כותרות שנמצאו (כמה פסקאות רצופות באותו סגנון חוזרות כטווח אחד) → רמות הפסקאות.</summary>
        static void TakeFound(HeadingScan scan, string text, int start, int level)
        {
            int offset = 0;
            foreach (string part in (text ?? "").Split('\r'))
            {
                string clean = DocText.Clean(part);
                if (clean.Trim().Length > 0)
                {
                    int idx = scan.Text.MatchNear(clean, start + offset);
                    if (idx >= 0 && scan.Levels[idx] == 0)
                    {
                        scan.Levels[idx] = level;
                        scan.Found++;
                        if (offset == 0) scan.Text.Learn(idx, start);
                    }
                }
                offset += part.Length + 1;
            }
        }

        public bool HeadingsReady(Word.Document doc)
        {
            var s = Find(doc);
            return s != null && s.Text != null && s.Text.HasLevels && !s.NeedsHeadings;
        }

        public int HeadingsFoundSoFar(Word.Document doc) => Find(doc)?.Scan?.Found ?? 0;

        /// <summary>כשבוחרים "כותרות": משלימים את קריאת הכותרות עכשיו (עד budgetMs בכל קריאה).
        /// מחזיר true כשהכותרות מוכנות; אחרת – לקרוא שוב בעוד רגע (בינתיים Word מגיב).</summary>
        public bool EnsureHeadings(Word.Document doc, int budgetMs)
        {
            var s = StateOf(doc);
            if (s.Text == null || !Fresh(s))
            {
                DocText previous = s.Text;
                string raw = ReadText(s);
                DocText dt = previous != null && previous.TextHash == DocText.Hash(raw) ? previous : DocText.Build(raw, previous);
                Adopt(s, dt, previous);
                s.NeedsRead = false;
            }
            if (s.Text.HasLevels && !s.NeedsHeadings) return true;
            s.NeedsHeadings = true;
            return HeadingSlice(s, budgetMs);
        }

        // ================================================================ חיפוש (מהחלונית)
        /// <summary>מחפש ברכיב העזר על תהליך נפרד. את הטקסט קוראים מ-Word רק אם ייתכן שהשתנה
        /// (או משתמשים ב-reuse שכבר נקרא). done נקרא בתהליך הראשי עם התשובה והגרסה שבה חיפשו.</summary>
        public void Search(Word.Document doc, Dictionary<string, object> request,
                           Action<Dictionary<string, object>, DocText, Exception> done, DocText reuse = null)
        {
            var s = StateOf(doc);
            DocText previous = s.Text;
            string raw = null;
            if (reuse == null && !Fresh(s)) raw = ReadText(s);
            DocText known = reuse ?? (raw == null ? previous : null);
            Task.Run(() =>
            {
                try
                {
                    DocText dt = known ?? (previous != null && previous.TextHash == DocText.Hash(raw) ? previous : DocText.Build(raw, previous));
                    var req = new Dictionary<string, object>(request) { ["cmd"] = "search", ["doc"] = dt.Key };
                    var reply = Ask(req, dt);
                    Post(() =>
                    {
                        if (_docs.Contains(s) && reuse == null)
                        {
                            Adopt(s, dt, previous);
                            if (Ok(reply) && dt == s.Text) s.IndexedKey = dt.Key;
                            s.NeedsRead = false;
                        }
                        done(reply, dt, null);
                    });
                }
                catch (Exception e)
                {
                    Post(() => done(null, null, e));
                }
            });
        }

        static bool Ok(Dictionary<string, object> reply) => reply != null && reply.ContainsKey("ok") && (bool)reply["ok"];

        Dictionary<string, object> Call(Dictionary<string, object> req)
        {
            return _json.Deserialize<Dictionary<string, object>>(_helper.Call(_json.Serialize(req)));
        }

        /// <summary>שולח לרכיב העזר. את הפסקאות שולחים רק אם הוא עוד לא מכיר את הגרסה הזו.</summary>
        Dictionary<string, object> Ask(Dictionary<string, object> req, DocText dt)
        {
            bool known;
            string sibling = null;
            lock (_sent)
            {
                known = _sent.Contains(dt.Key);
                if (!known)
                    foreach (string k in _sent)
                        if (k.StartsWith(dt.TextHash + "/")) { sibling = k; break; }
            }
            if (!known && sibling != null && dt.HasLevels)
            {
                // אותו טקסט, רק רמות הכותרות השתנו – רכיב העזר משתמש שוב במפת החיפוש שכבר בנה
                var relevel = Call(new Dictionary<string, object> { ["cmd"] = "relevel", ["from"] = sibling, ["doc"] = dt.Key, ["levels"] = dt.Levels });
                if (Ok(relevel))
                {
                    known = true;
                    lock (_sent) _sent.Add(dt.Key);
                }
            }
            if (!known) req["paras"] = dt.Paras();
            var reply = Call(req);
            if (reply.ContainsKey("need_paras"))                  // רכיב העזר הופעל מחדש או פינה את המסמך
            {
                req["paras"] = dt.Paras();
                reply = Call(req);
            }
            if (Ok(reply)) lock (_sent) _sent.Add(dt.Key);
            return reply;
        }

        // ================================================================ עזרים
        void Post(Action a)
        {
            try { _ui.BeginInvoke(a); } catch (Exception e) { Log.Error("post", e); }
        }

        bool WordIsFree(int idleMs)
        {
            if (!UserIdle(idleMs)) return false;
            IntPtr main = Process.GetCurrentProcess().MainWindowHandle;
            if (main != IntPtr.Zero && !IsWindowEnabled(main)) return false;     // חלון דו-שיח פתוח
            try
            {
                var app = _addin.Application;
                if (app.BackgroundSavingStatus != 0 || app.BackgroundPrintingStatus != 0) return false;
            }
            catch (COMException) { return false; }
            return true;
        }

        static bool UserIdle(int ms)
        {
            var info = new LASTINPUTINFO { cbSize = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO)) };
            if (!GetLastInputInfo(ref info)) return true;
            uint idle = unchecked((uint)Environment.TickCount - info.dwTime);
            return idle >= ms;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct LASTINPUTINFO
        {
            public uint cbSize;
            public uint dwTime;
        }

        [DllImport("user32.dll")]
        static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

        [DllImport("user32.dll")]
        static extern bool IsWindowEnabled(IntPtr hWnd);

        public void Dispose()
        {
            _timer.Stop();
            _timer.Dispose();
            _docs.Clear();
            try { _ui.Dispose(); } catch { }
        }
    }
}
