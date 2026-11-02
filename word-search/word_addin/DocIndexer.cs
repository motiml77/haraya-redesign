// הכנת המסמכים לחיפוש מאחורי הקלעים, בלי לעכב את Word:
//
//   1. כל שתי שניות בודקים בזול (שם + Content.End) אם יש מסמך פתוח שעוד לא הוכן.
//   2. מתחילים רק כשהמסמך "נרגע" (אותו אורך בשתי בדיקות רצופות = נטען במלואו).
//   3. קוראים רק כש-Word פנוי: החלון זמין (אין דיאלוג פתוח), אין שמירה או הדפסה ברקע, והמשתמש לא
//      נגע במקלדת או בעכבר בשנייה האחרונה. כל פעם מנה קטנה (~10 אלפיות שנייה) ואז הפסקה.
//   4. כל אובייקט של Word משתחרר מיד אחרי הקריאה: Word מעדכן כל טווח (Range) חי בכל שינוי ובכל
//      עימוד, ואלפי טווחים שלא שוחררו מאטים אותו עד שהוא נראה תקוע.
//   5. בסוף התמונה נשלחת לרכיב העזר (בונה מפת חיפוש בתהליך נפרד) ונשמרת בדיסק לפתיחה הבאה.
//   מסמך מוכן ברקע פעם אחת בלבד. אחרי עריכה הוא נקרא מחדש רק כשמחפשים בו (Get).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace HebDocSearch.WordAddin
{
    internal sealed class DocIndexer : IDisposable
    {
        const int PollMs = 2000, TickMs = 60, SliceMs = 10, IdleMs = 1000;

        readonly dynamic _app;
        readonly Timer _poll = new Timer { Interval = PollMs };
        readonly Timer _work = new Timer { Interval = TickMs };
        readonly Dictionary<string, DocSnapshot> _ready = new Dictionary<string, DocSnapshot>(StringComparer.OrdinalIgnoreCase);
        readonly HashSet<string> _prepared = new HashSet<string>(StringComparer.OrdinalIgnoreCase);   // הוכנו פעם אחת ברקע
        readonly Dictionary<string, int> _lastEnd = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        readonly JavaScriptSerializer _json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        readonly HashSet<string> _sent = new HashSet<string>();      // מפתחות שרכיב העזר כבר בנה
        readonly object _sentLock = new object();
        bool _busy;                                                   // מגן מכניסה חוזרת לטיימר

        Job _job;
        public event Action<string> StateChanged;

        sealed class Job
        {
            public dynamic Doc;
            public string Name;
            public string KeyAtStart;
            public int Total;
            public dynamic Next;                                     // הפסקה הבאה לקריאה
            public DocSnapshot Snap;
            public Stopwatch Clock = Stopwatch.StartNew();
        }

        public DocIndexer(dynamic app)
        {
            _app = app;
            _poll.Tick += (s, e) => Guard("poll", Poll);
            _work.Tick += (s, e) => Guard("work", Work);
        }

        void Guard(string what, Action action)
        {
            if (_busy) return;
            _busy = true;
            try { action(); }
            catch (Exception e) { Log.Error(what, e); }
            finally { _busy = false; }
        }

        public void Start(int firstDelayMs = 5000)
        {
            var once = new Timer { Interval = firstDelayMs };
            once.Tick += (s, e) => { once.Stop(); once.Dispose(); _poll.Start(); };
            once.Start();
            Log.Write("indexer: start in " + firstDelayMs + "ms");
        }

        // ================================================================ האם Word פנוי
        [StructLayout(LayoutKind.Sequential)]
        struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }

        [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO info);
        [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr hwnd);

        static uint UserIdleMs()
        {
            var li = new LASTINPUTINFO { cbSize = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO)) };
            return GetLastInputInfo(ref li) ? unchecked((uint)Environment.TickCount - li.dwTime) : 0;
        }

        bool WordIsFree()
        {
            if (UserIdleMs() < IdleMs) return false;                 // המשתמש מקליד או מזיז את העכבר
            try
            {
                if ((int)_app.BackgroundSavingStatus > 0 || (int)_app.BackgroundPrintingStatus > 0) return false;
                dynamic win = _app.ActiveWindow;
                try { if (!IsWindowEnabled(new IntPtr((int)win.Hwnd))) return false; }   // דיאלוג מודאלי פתוח
                finally { Release(win); }
            }
            catch { return false; }                                  // אין חלון פעיל, Word באמצע פעולה
            return true;
        }

        internal static void Release(object o)
        {
            try { if (o != null && Marshal.IsComObject(o)) Marshal.ReleaseComObject(o); } catch { }
        }

        // ================================================================ מצב, לחלונית
        public string State(string name)
        {
            if (_job != null && string.Equals(_job.Name, name, StringComparison.OrdinalIgnoreCase))
                return "reading:" + (_job.Total > 0 ? Math.Min(99, _job.Snap.Texts.Count * 100 / _job.Total) : 0);
            return _ready.ContainsKey(name) ? "ready" : "waiting";
        }

        public DocSnapshot ReadyFor(string name)
        {
            return _ready.TryGetValue(name, out var s) ? s : null;
        }

        public bool Sent(string key) { lock (_sentLock) return _sent.Contains(key); }
        public void MarkSent(string key) { lock (_sentLock) _sent.Add(key); }
        public void ForgetSent() { lock (_sentLock) _sent.Clear(); }

        // ================================================================ בדיקה תקופתית
        void Poll()
        {
            if (_job != null || !WordIsFree()) return;
            dynamic docs = _app.Documents;
            try
            {
                int count = (int)docs.Count;
                for (int i = 1; i <= count; i++)
                {
                    dynamic doc = docs[i];
                    string name = DocSnapshot.NameOf(doc);
                    if (_prepared.Contains(name)) { Release(doc); continue; }
                    int end;
                    try { end = DocSnapshot.EndOf(doc); } catch { Release(doc); continue; }
                    if (!_lastEnd.TryGetValue(name, out int last) || last != end)
                    {
                        _lastEnd[name] = end;                        // עוד נטען / משתנה – נחכה לבדיקה הבאה
                        Release(doc);
                        continue;
                    }
                    var cached = DocSnapshot.Load(doc);              // קובץ שלא השתנה – מהדיסק, בלי לקרוא
                    if (cached != null)
                    {
                        Log.Write("indexer: from disk cache " + name + " (" + cached.Texts.Count + " paras)");
                        _prepared.Add(name);
                        Finish(doc, cached, save: false);
                        Release(doc);
                        continue;
                    }
                    Begin(doc, name, end);
                    return;                                          // את doc משחררים בסוף הקריאה
                }
            }
            finally { Release(docs); }
        }

        void Begin(dynamic doc, string name, int end)
        {
            dynamic paras = doc.Paragraphs;
            _job = new Job
            {
                Doc = doc,
                Name = name,
                KeyAtStart = DocSnapshot.KeyOf(name, DocSnapshot.TextOf(doc)),
                Total = (int)paras.Count,
                Next = paras.First,
                Snap = new DocSnapshot { Name = name, End = end },
            };
            Release(paras);
            _prepared.Add(name);
            Log.Write("indexer: begin " + name + " (" + _job.Total + " paras)");
            _work.Start();
            StateChanged?.Invoke(name);
        }

        // ================================================================ קריאה במנות
        void Work()
        {
            var job = _job;
            if (job == null) { _work.Stop(); return; }
            if (!WordIsFree()) return;                               // לא מפריעים – ננסה בעוד רגע
            try
            {
                if (Step(job, SliceMs)) Complete(job);
            }
            catch (Exception e)
            {
                Log.Error("read " + job.Name, e);
                Abort();
            }
        }

        /// <summary>קורא פסקאות עד שנגמר הזמן (0 = עד הסוף). מחזיר true כשהמסמך נקרא כולו.</summary>
        static bool Step(Job job, int budgetMs)
        {
            var sw = Stopwatch.StartNew();
            while (job.Next != null)
            {
                dynamic p = job.Next;
                job.Snap.Add(p);
                dynamic next = p.Next();
                Release(p);
                job.Next = next;
                if (budgetMs > 0 && sw.ElapsedMilliseconds >= budgetMs) break;
            }
            return job.Next == null;
        }

        void Complete(Job job)
        {
            _work.Stop();
            _job = null;
            string key = DocSnapshot.KeyOf(job.Name, DocSnapshot.TextOf(job.Doc));
            Log.Write("indexer: read " + job.Name + " in " + job.Clock.ElapsedMilliseconds + "ms");
            if (key != job.KeyAtStart)                               // נערך בזמן הקריאה – ייקרא כשיחפשו
            {
                Release(job.Doc);
                StateChanged?.Invoke(job.Name);
                return;
            }
            job.Snap.Key = key;
            Finish(job.Doc, job.Snap, save: true);
            Release(job.Doc);
        }

        void Finish(dynamic doc, DocSnapshot snap, bool save)
        {
            _ready[snap.Name] = snap;
            if (save) snap.Save(doc);
            StateChanged?.Invoke(snap.Name);
            SendToHelper(snap);
        }

        void SendToHelper(DocSnapshot snap)
        {
            if (Sent(snap.Key)) return;
            string req = _json.Serialize(new Dictionary<string, object>
            {
                ["cmd"] = "index", ["doc"] = snap.Key, ["paras"] = snap.Paras(),
            });
            string key = snap.Key;
            Task.Run(() =>
            {
                try
                {
                    var reply = _json.Deserialize<Dictionary<string, object>>(Connect.Helper.Call(req));
                    if (reply.ContainsKey("ok") && (bool)reply["ok"]) MarkSent(key);
                    Log.Write("helper: index " + (reply.ContainsKey("elapsed") ? reply["elapsed"] + "s" : "failed"));
                }
                catch (Exception e) { Log.Error("helper index", e); }
            });
        }

        void Abort()
        {
            _work.Stop();
            if (_job != null)
            {
                Release(_job.Next);
                Release(_job.Doc);
            }
            _job = null;
        }

        // ================================================================ לחיפוש
        /// <summary>תמונה עדכנית של המסמך לחיפוש. אם ההכנה ברקע עוד לא הסתיימה – משלים אותה עכשיו.</summary>
        public DocSnapshot Get(dynamic doc)
        {
            string name = DocSnapshot.NameOf(doc);
            string key = DocSnapshot.KeyOf(name, DocSnapshot.TextOf(doc));
            if (_ready.TryGetValue(name, out var snap) && snap.Key == key) return snap;
            if (_job != null && string.Equals(_job.Name, name, StringComparison.OrdinalIgnoreCase) && _job.KeyAtStart == key)
            {
                var job = _job;
                try
                {
                    Step(job, 0);                                    // משלימים את מה שנשאר
                    _work.Stop();
                    _job = null;
                    Release(job.Doc);
                    job.Snap.Key = key;
                    _ready[name] = job.Snap;
                    job.Snap.Save(doc);
                    StateChanged?.Invoke(name);
                    return job.Snap;
                }
                catch (Exception e)
                {
                    Log.Error("finish on search", e);
                    Abort();
                }
            }
            var sw = Stopwatch.StartNew();
            snap = DocSnapshot.ReadAll(doc);
            Log.Write("search: read " + name + " (" + snap.Texts.Count + " paras) in " + sw.ElapsedMilliseconds + "ms");
            _ready[name] = snap;
            _prepared.Add(name);
            snap.Save(doc);
            StateChanged?.Invoke(name);
            return snap;
        }

        public void Dispose()
        {
            _poll.Stop();
            _work.Stop();
            Abort();
            _poll.Dispose();
            _work.Dispose();
        }
    }
}
