// הכנת המסמכים לחיפוש מאחורי הקלעים, בלי לעכב את פתיחת הקובץ:
//
//   1. כל שתי שניות בודקים בזול (שם + Content.End) אילו מסמכים פתוחים עדיין לא מוכנים.
//   2. מסמך חדש מתחיל להיקרא רק אחרי שהוא "נרגע" – באותו אורך בשתי בדיקות רצופות, כלומר נטען במלואו.
//   3. הקריאה נעשית במנות של ~15 אלפיות שנייה בכל פעם (Word מאפשר לקרוא את המסמך רק מהחוט הראשי
//      שלו, ולכן המנות הקטנות הן מה ששומר עליו חלק), עם הפסקה בין מנה למנה.
//   4. בסוף התמונה נשלחת לרכיב העזר, שבונה ממנה מפת חיפוש (בתהליך נפרד – לא על חשבון Word),
//      ונשמרת בדיסק לפתיחה הבאה של אותו קובץ.
//   חיפוש לפני שההכנה הסתיימה משלים את הקריאה במקום (Get), כך שהחיפוש תמיד עובד.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace HebDocSearch.WordAddin
{
    internal sealed class DocIndexer : IDisposable
    {
        const int PollMs = 2000, TickMs = 40, SliceMs = 15;

        readonly dynamic _app;
        readonly Timer _poll = new Timer { Interval = PollMs };
        readonly Timer _work = new Timer { Interval = TickMs };
        readonly Dictionary<string, DocSnapshot> _ready = new Dictionary<string, DocSnapshot>(StringComparer.OrdinalIgnoreCase);
        readonly Dictionary<string, int> _lastEnd = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        readonly JavaScriptSerializer _json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        readonly HashSet<string> _sent = new HashSet<string>();      // מפתחות שרכיב העזר כבר בנה
        readonly object _sentLock = new object();

        Job _job;
        public event Action<string> StateChanged;                    // שם המסמך שמצבו השתנה

        sealed class Job
        {
            public dynamic Doc;
            public string Name;
            public string KeyAtStart;
            public int Total;
            public dynamic Next;                                     // הפסקה הבאה לקריאה
            public DocSnapshot Snap;
        }

        public DocIndexer(dynamic app)
        {
            _app = app;
            _poll.Tick += (s, e) => Poll();
            _work.Tick += (s, e) => Work();
        }

        public void Start(int firstDelayMs = 3000)
        {
            var once = new Timer { Interval = firstDelayMs };
            once.Tick += (s, e) => { once.Stop(); once.Dispose(); _poll.Start(); Poll(); };
            once.Start();
        }

        // ================================================================ מצב, לחלונית
        /// <summary>מצב המסמך: "ready" / "reading:NN" (אחוזים) / "waiting".</summary>
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

        public bool Sent(string key)
        {
            lock (_sentLock) return _sent.Contains(key);
        }

        public void MarkSent(string key)
        {
            lock (_sentLock) _sent.Add(key);
        }

        public void ForgetSent()
        {
            lock (_sentLock) _sent.Clear();                          // רכיב העזר הופעל מחדש
        }

        // ================================================================ בדיקה תקופתית
        void Poll()
        {
            if (_job != null) return;
            try
            {
                dynamic active = null;
                try { active = _app.ActiveDocument; } catch { }
                var docs = new List<dynamic>();
                if (active != null) docs.Add(active);
                foreach (dynamic d in _app.Documents)
                {
                    if (active == null || NameOf(d) != NameOf(active)) docs.Add(d);
                }
                foreach (dynamic doc in docs)
                {
                    string name = NameOf(doc);
                    int end;
                    try { end = (int)doc.Content.End; } catch { continue; }
                    if (_ready.TryGetValue(name, out var snap) && snap.End == end) continue;
                    // ממתינים שהמסמך יירגע: אותו אורך בשתי בדיקות רצופות = נטען במלואו (ולא באמצע הקלדה)
                    if (!_lastEnd.TryGetValue(name, out int last) || last != end)
                    {
                        _lastEnd[name] = end;
                        continue;
                    }
                    var cached = DocSnapshot.Load(doc);              // קובץ שלא השתנה – מהדיסק, בלי לקרוא
                    if (cached != null && cached.End == end)
                    {
                        Finish(doc, cached, save: false);
                        continue;
                    }
                    Begin(doc, name, end);
                    return;
                }
            }
            catch { }
        }

        static string NameOf(dynamic doc) => DocSnapshot.NameOf(doc);

        void Begin(dynamic doc, string name, int end)
        {
            string full = Convert.ToString(doc.Content.Text) ?? "";
            _job = new Job
            {
                Doc = doc,
                Name = name,
                KeyAtStart = DocSnapshot.KeyOf(name, full),
                Total = (int)doc.Paragraphs.Count,
                Next = doc.Paragraphs.First,
                Snap = new DocSnapshot { Name = name, End = end },
            };
            _work.Start();
            StateChanged?.Invoke(name);
        }

        // ================================================================ קריאה במנות
        void Work()
        {
            var job = _job;
            if (job == null) { _work.Stop(); return; }
            try
            {
                if (Step(job, SliceMs)) Complete(job);
            }
            catch
            {
                Abort();                                             // המסמך נסגר או השתנה באמצע – ננסה שוב בבדיקה הבאה
            }
        }

        /// <summary>קורא פסקאות עד שנגמר הזמן. מחזיר true כשהמסמך נקרא כולו.</summary>
        static bool Step(Job job, int budgetMs)
        {
            var sw = Stopwatch.StartNew();
            while (job.Next != null)
            {
                job.Snap.Add(job.Next);
                job.Next = job.Next.Next();
                if (budgetMs > 0 && sw.ElapsedMilliseconds >= budgetMs) return job.Next == null;
            }
            return true;
        }

        void Complete(Job job)
        {
            _work.Stop();
            _job = null;
            string full = Convert.ToString(job.Doc.Content.Text) ?? "";
            string key = DocSnapshot.KeyOf(job.Name, full);
            if (key != job.KeyAtStart)                               // נערך בזמן הקריאה – מתחילים שוב אחר כך
            {
                _lastEnd.Remove(job.Name);
                StateChanged?.Invoke(job.Name);
                return;
            }
            job.Snap.Key = key;
            Finish(job.Doc, job.Snap, save: true);
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
                }
                catch { }
            });
        }

        void Abort()
        {
            _work.Stop();
            if (_job != null) _lastEnd.Remove(_job.Name);
            _job = null;
        }

        // ================================================================ לחיפוש
        /// <summary>תמונה עדכנית של המסמך לחיפוש. אם ההכנה ברקע עוד לא הסתיימה – משלים אותה עכשיו.</summary>
        public DocSnapshot Get(dynamic doc)
        {
            string name = NameOf(doc);
            string full = Convert.ToString(doc.Content.Text) ?? "";
            string key = DocSnapshot.KeyOf(name, full);
            if (_ready.TryGetValue(name, out var snap) && snap.Key == key) return snap;
            if (_job != null && string.Equals(_job.Name, name, StringComparison.OrdinalIgnoreCase) && _job.KeyAtStart == key)
            {
                var job = _job;
                try
                {
                    Step(job, 0);                                    // משלימים את מה שנשאר
                    _work.Stop();
                    _job = null;
                    job.Snap.Key = key;
                    _ready[name] = job.Snap;
                    job.Snap.Save(doc);
                    StateChanged?.Invoke(name);
                    return job.Snap;
                }
                catch
                {
                    Abort();
                }
            }
            snap = DocSnapshot.ReadAll(doc);
            _ready[name] = snap;
            snap.Save(doc);
            StateChanged?.Invoke(name);
            return snap;
        }

        public void Dispose()
        {
            _poll.Stop();
            _work.Stop();
            _poll.Dispose();
            _work.Dispose();
        }
    }
}
