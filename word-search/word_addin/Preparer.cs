// הכנת המסמכים לחיפוש מאחורי הקלעים – לפי ההנחיות של Microsoft לתוספים:
//   * כל גישה למודל של Word רק מהתהליך הראשי (המודל הוא STA), ומעט ככל האפשר;
//   * עבודה כבדה (חלוקה, טביעת אצבע, בניית מפת החיפוש) – על תהליך נפרד / ברכיב העזר;
//   * שום דבר בזמן הפתיחה: אחרי שהמסמך נפתח מחכים שהמשתמש לא נוגע במקלדת ובעכבר,
//     ש-Word לא מציג חלון דו-שיח ולא שומר/מדפיס ברקע – ורק אז קוראים את הטקסט (קריאה אחת).
//   * הכותרות נקראות במנות קצרות (עד ~40ms) בזמני מנוחה, כך ש-Word אף פעם לא נתקע.
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
            public string Error;
        }

        internal sealed class HeadingScan
        {
            public DocText Text;
            public int[] Levels;
            public int Pos = -1;                // המיקום במסמך של הכותרת האחרונה שנמצאה
            public int NextPara;
            public int Steps;
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

        public event Action<Word.Document> StateChanged;

        public Preparer(ThisAddIn addin, HelperClient helper)
        {
            _addin = addin;
            _helper = helper;
            _ui = new Control();
            IntPtr unused = _ui.Handle;          // יוצר את החלון הנסתר בתהליך הראשי
            _timer.Tick += (s, e) => Tick();
            _timer.Start();
        }

        public HelperClient Helper => _helper;

        // ================================================================ מצב המסמכים
        DocState Find(Word.Document doc)
        {
            foreach (var s in _docs)
                if (ReferenceEquals(s.Doc, doc)) return s;
            return null;
        }

        public DocState StateOf(Word.Document doc)
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
            string counts = $"{s.Text.Texts.Count:N0} פסקאות";
            if (!s.Text.HasLevels || s.NeedsHeadings)
                return "המסמך מוכן לחיפוש · " + counts + " · קורא את הכותרות…";
            return "המסמך מוכן לחיפוש · " + counts + $" · {s.Text.Headings:N0} כותרות";
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
                    HeadingSlice(next);
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
            var sw = Stopwatch.StartNew();
            string raw = s.Doc.Content.Text;           // הקריאה היחידה למודל של Word
            long readMs = sw.ElapsedMilliseconds;
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
                        s.Text = dt;
                        s.NeedsHeadings = !dt.HasLevels || dt != previous;
                        s.Scan = null;
                        s.NotBefore = DateTime.Now;
                        Log.Write($"read {raw.Length:N0} chars in {readMs}ms → {dt.Texts.Count:N0} paragraphs");
                        BeginIndex(s, dt);
                        Changed(s);
                    });
                }
                catch (Exception e)
                {
                    Post(() => { s.Reading = false; s.Error = e.Message; Log.Error("read", e); Changed(s); });
                }
            });
        }

        void BeginIndex(DocState s, DocText dt)
        {
            if (s.IndexedKey == dt.Key) return;
            s.Indexing = true;
            Task.Run(() =>
            {
                try
                {
                    var t0 = Stopwatch.StartNew();
                    var reply = Ask(new Dictionary<string, object> { ["cmd"] = "index", ["doc"] = dt.Key }, dt);
                    bool ok = reply.ContainsKey("ok") && (bool)reply["ok"];
                    Post(() =>
                    {
                        s.Indexing = false;
                        if (ok) s.IndexedKey = dt.Key;
                        else s.Error = reply.ContainsKey("error") ? Convert.ToString(reply["error"]) : "שגיאה";
                        Log.Write($"index {dt.Texts.Count:N0} paragraphs ({dt.Headings} headings) in {t0.ElapsedMilliseconds}ms ok={ok}");
                        Changed(s);
                    });
                }
                catch (Exception e)
                {
                    Post(() => { s.Indexing = false; s.Error = e.Message; Log.Error("index", e); Changed(s); });
                }
            });
        }

        // ================================================================ הכותרות, במנות קצרות
        void HeadingSlice(DocState s)
        {
            if (s.Text == null) { s.NeedsHeadings = false; return; }
            var sw = Stopwatch.StartNew();
            var scan = s.Scan;
            if (scan == null || scan.Text != s.Text)
            {
                scan = s.Scan = new HeadingScan { Text = s.Text, Levels = new int[s.Text.Texts.Count] };
                Word.Paragraph first = s.Doc.Paragraphs.First;           // GoTo "הבאה" מדלג על הפסקה הראשונה
                scan.Pos = first.Range.Start;
                Take(scan, first);
            }
            int maxSteps = s.Text.Texts.Count + 10;
            bool done = false;
            while (sw.ElapsedMilliseconds < SliceMs)
            {
                Word.Range at = s.Doc.Range(scan.Pos, scan.Pos);
                Word.Range r = at.GoTo(Word.WdGoToItem.wdGoToHeading, Word.WdGoToDirection.wdGoToNext);
                if (r == null || r.Start <= scan.Pos || ++scan.Steps > maxSteps) { done = true; break; }
                scan.Pos = r.Start;
                Take(scan, r.Paragraphs.First);
            }
            if (!done) return;                                            // ממשיכים בזמן המנוחה הבא

            s.Scan = null;
            s.NeedsHeadings = false;
            DocText withLevels = scan.Text.WithLevels(scan.Levels);
            if (s.Text == scan.Text) s.Text = withLevels;
            Log.Write($"headings: {withLevels.Headings} ({scan.Steps} steps)");
            BeginIndex(s, s.Text);
            Changed(s);
        }

        static void Take(HeadingScan scan, Word.Paragraph p)
        {
            int level = (int)p.OutlineLevel;                              // 10 = גוף הטקסט
            if (level < 1 || level > 9) return;
            Word.Range pr = p.Range;
            int idx = scan.Text.MatchParagraph(DocText.Clean(pr.Text), scan.NextPara);
            if (idx < 0) return;
            scan.Levels[idx] = level;
            scan.NextPara = idx + 1;
            scan.Text.Learn(idx, pr.Start);
        }

        // ================================================================ חיפוש (מהחלונית)
        /// <summary>קורא את הטקסט הנוכחי (קריאה אחת), ומחפש ברכיב העזר על תהליך נפרד.
        /// done נקרא בתהליך הראשי עם התשובה והגרסה שבה חיפשו (בשביל המעבר לתוצאות).</summary>
        public void Search(Word.Document doc, Dictionary<string, object> request,
                           Action<Dictionary<string, object>, DocText, Exception> done)
        {
            var s = StateOf(doc);
            string raw = doc.Content.Text;
            DocText previous = s.Text;
            Task.Run(() =>
            {
                try
                {
                    DocText dt = previous != null && previous.TextHash == DocText.Hash(raw) ? previous : DocText.Build(raw, previous);
                    var req = new Dictionary<string, object>(request) { ["cmd"] = "search", ["doc"] = dt.Key };
                    var reply = Ask(req, dt);
                    Post(() =>
                    {
                        if (dt != previous && _docs.Contains(s))
                        {
                            // המסמך השתנה מאז ההכנה: הגרסה החדשה נשמרת, והכותרות ייקראו שוב בזמן מנוחה
                            s.Text = dt;
                            s.IndexedKey = dt.Key;
                            s.NeedsRead = false;
                            s.NeedsHeadings = true;
                            s.Scan = null;
                            s.NotBefore = DateTime.Now.AddSeconds(1);
                            _timer.Start();
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

        /// <summary>שולח לרכיב העזר. את הפסקאות שולחים רק אם הוא עוד לא מכיר את הגרסה הזו.</summary>
        Dictionary<string, object> Ask(Dictionary<string, object> req, DocText dt)
        {
            bool known;
            lock (_sent) known = _sent.Contains(dt.Key);
            if (!known) req["paras"] = dt.Paras();
            var reply = _json.Deserialize<Dictionary<string, object>>(_helper.Call(_json.Serialize(req)));
            if (reply.ContainsKey("need_paras"))                  // רכיב העזר הופעל מחדש או פינה את המסמך
            {
                req["paras"] = dt.Paras();
                reply = _json.Deserialize<Dictionary<string, object>>(_helper.Call(_json.Serialize(req)));
            }
            if (reply.ContainsKey("ok") && (bool)reply["ok"])
                lock (_sent) _sent.Add(dt.Key);
            return reply;
        }

        // ================================================================ עזרים
        void Post(Action a)
        {
            try { _ui.BeginInvoke(a); } catch (Exception e) { Log.Error("post", e); }
        }

        void Changed(DocState s)
        {
            try { StateChanged?.Invoke(s.Doc); } catch (Exception e) { Log.Error("state", e); }
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
