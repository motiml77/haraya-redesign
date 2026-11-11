// הכנת המסמכים לחיפוש מאחורי הקלעים – לפי ההנחיות של Microsoft לתוספים:
//   * כל גישה למודל של Word רק מהתהליך הראשי (המודל הוא STA), ומעט ככל האפשר;
//   * עבודה כבדה (חלוקה, טביעת אצבע, בניית מפת החיפוש) – על תהליך נפרד / ברכיב העזר, בעדיפות נמוכה;
//   * שום דבר בזמן הפתיחה עצמה: הטקסט נקרא (קריאה אחת) רגע אחרי שהמסמך נפתח, בהפסקה קצרה בהקלדה.
//
// מהירות בלי לתקוע: ההכנה לא מחכה שהמשתמש יפסיק לעבוד. היא רצה כל הזמן, במנות קצרות מאוד:
//   * כל קריאה ל-Word קצרה (קריאת רמת החלוקה של פסקה אחת), ובכל מנה כמה שנכנס בזמן שלה – ולכן המסך
//     וההקלדה לא מרגישים אותה;
//   * היא עוצרת רק בזמן כתיבה (הקשה במקלדת ב-Word או בחלונית – Typing). תזוזת עכבר וגלילה לא עוצרות
//     אותה, רק מקצרות את המנות כדי שהמסך יישאר חלק. כמה עבודה בכל מנה: אחרי הקשה – ~12 אלפיות שנייה,
//     כשלא מקלידים כמה שניות – יותר. בין המנות Word מטפל בכל מה שמחכה לו;
//   * לא מחכים לרכיב העזר: בזמן שהוא בונה את מפת החיפוש (בתהליך אחר), הכותרות כבר נקראות.
//
// כותרות בלי Word: במסמך docx שמור, רמות הכותרות נקראות ישירות מהקובץ ברכיב העזר (כמו שחלונית הניווט
// של Word קוראת אותן – תכונה של הפסקה, לא חיפוש). רק מה שלא התאים נבדק ב-Word.
//
// לא עושים פעמיים את אותה עבודה:
//   * לכל מסמך נשמר בדיסק (HeadingCache) מה שנקרא ממנו. בפתיחה הבאה, אם הקובץ לא השתנה – הכותרות
//     מוכנות מיד; אם השתנה – הרמות עוברות לפסקאות שלא השתנו, נבדקות רק הפסקאות החדשות, וברקע נעשה
//     אימות מלא אחד (שינוי של סגנון בלבד לא נראה בטקסט);
//   * מפת החיפוש עצמה נשמרת בדיסק אצל רכיב העזר לפי טביעת האצבע של הטקסט – לא נשלחת ולא נבנית שוב
//     (נשמרת כשהמסמך נסגר; מסמך שלא נפתח 3 ימים – נמחק, ונבנה שוב כשייפתח);
//   * אחרי עריכה בודקים רק את הפסקאות שנוספו או שנערכו, ולרכיב העזר נשלחות רק הן (patch) – המילים של
//     שאר הפסקאות לא מעובדות שוב. כשמחפשים בכותרות אחרי עריכה – אימות מלא ברקע, ואם התגלה שינוי
//     (פסקה שהפכה לכותרת) התוצאות מתעדכנות.
//
// כותרת = פסקה עם רמת חלוקה 1–9, כמו בחלונית הניווט של Word (סגנונות "כותרת 1–9" וגם סגנונות אישיים).
// הכותרות נקראות במעבר על הפסקאות של המסמך (Paragraph.OutlineLevel, ולכותרת – גם הטקסט והמקום), ולא
// בחיפוש של Word: ההגדרות של Find משותפות לחיפוש של Word עצמו (חלונית הניווט, "חיפוש והחלפה"), וכל חיפוש
// כזה ברקע איפס את החיפוש שהמשתמש עשה ב-Word. שום פעולה ברקע לא משתמשת ב-Find, לא משנה את המסמך ולא
// מזיזה את הסמן.
//
// בחיפוש קוראים את הטקסט מחדש רק אם ייתכן שהמסמך השתנה מאז הקריאה הקודמת: האורך השתנה,
// המסמך נשמר, או שהסמן זז במסמך שיש בו שינויים שלא נשמרו (כל הקלדה מזיזה את הסמן).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using Word = Microsoft.Office.Interop.Word;
using Timer = System.Windows.Forms.Timer;

namespace HebDocSearch.WordAddin
{
    internal sealed class Preparer : IDisposable
    {
        internal sealed class DocState
        {
            public Word.Document Doc;
            public string Path;                 // המקום של המסמך (לשמירה בדיסק); null למסמך חדש בלי שם
            public DocText Text;                // הגרסה האחרונה שנקראה
            public string IndexedKey;           // הגרסה שרכיב העזר כבר בנה לה מפת חיפוש
            public bool NeedsRead = true;
            public bool NeedsHeadings;          // הרמות חסרות (לא נקראו, או שיש פסקאות חדשות לבדוק)
            public bool NeedsVerify;            // הרמות ידועות, אבל רוצים אימות מלא ברקע
            public bool Unverified;             // ייתכן שסגנון של פסקה השתנה מאז הקריאה המלאה האחרונה
            public int Edits;                   // כמה פעמים המסמך נקרא מחדש (כדי לדעת אם סריקה שהסתיימה עדיין תקפה)
            public DateTime LastFullScan;
            public bool Reading, Indexing;
            public bool DocxPending;            // רמות הכותרות נקראות עכשיו מקובץ ה-docx (בלי Word)
            public DateTime DocxSince;
            public double IndexProgress;        // 0..1 – בניית מפת החיפוש ברכיב העזר
            public double HeadingProgress;      // 0..1 – קריאת הכותרות (לא יורד)
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
            public bool Verify;                 // אימות ברקע של רמות שכבר ידועות
            public int Phase;                   // 0 מעבר על כל הפסקאות, 3 רק הפסקאות שהשתנו מאז הגרסה הקודמת
            public Word.Paragraph Para;         // שלב 0: הפסקה הבאה לבדיקה (null בהתחלה / אחרי תקלה)
            public bool Started;
            public int Resume;                  // אחרי תקלה (למשל הפסקה נמחקה) – ממשיכים מהמקום הזה
            public int Visited;                 // כמה פסקאות כבר נבדקו
            public int OutlineIndex;
            public int[] Changed;               // שלב 3: הפסקאות לבדיקה
            public int Checked, Missed;
            public int Found, Unmatched, Failures;
            public int EditsAtStart;
            public bool Failed;
            public Stopwatch Time = new Stopwatch();
        }

        const int IncrementalLimit = 500;       // יותר פסקאות שהשתנו (למשל הדבקה גדולה) – קוראים את כל הכותרות
        const int TickMs = 30;
        const int MaxFailures = 6;              // כישלונות רצופים (Word עסוק) לפני שמוותרים

        readonly ThisAddIn _addin;
        readonly HelperClient _helper;
        readonly System.Windows.Forms.Control _ui;       // להחזרת תוצאות מהתהליך הנפרד לתהליך הראשי
        readonly Timer _timer = new Timer { Interval = TickMs };
        readonly List<DocState> _docs = new List<DocState>();
        readonly HashSet<string> _sent = new HashSet<string>();
        readonly JavaScriptSerializer _json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        readonly DateTime _started = DateTime.Now;
        bool _openDocsQueued;
        int _ignoreSelectionUntil;
        IntPtr _mainWindow;
        int _mainWindowAt;

        /// <summary>האימות ברקע גילה שרמות הכותרות השתנו (למשל פסקה שהפכה לכותרת בלי שהטקסט שלה השתנה).</summary>
        public event Action<Word.Document> HeadingsChanged;

        public Preparer(ThisAddIn addin, HelperClient helper)
        {
            _addin = addin;
            _helper = helper;
            _ui = new System.Windows.Forms.Control();
            IntPtr unused = _ui.Handle;          // יוצר את החלון הנסתר בתהליך הראשי
            Typing.Start();
            Background(HeadingCache.Cleanup);    // מה שנשמר על מסמכים שלא נפתחו 3 ימים
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

        /// <summary>מסמך נפתח: רק רושמים אותו. ההכנה תתחיל רגע אחרי שהפתיחה הסתיימה.</summary>
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
            if (s == null) return;
            _docs.Remove(s);
            Persist(s, false);
        }

        /// <summary>המסמך נסגר: מה שנבנה בשבילו נשמר בדיסק, כדי שבפתיחה הבאה לא ייבנה שוב.</summary>
        void Persist(DocState s, bool wait)
        {
            try { SaveCache(s); } catch (Exception e) { Log.Error("save cache", e); }
            DocText dt = s.Text;
            string key = null;
            lock (_sent)
            {
                if (dt != null && _sent.Contains(dt.Key)) key = dt.Key;
                else if (s.IndexedKey != null && _sent.Contains(s.IndexedKey)) key = s.IndexedKey;
            }
            if (key == null || s.Path == null) return;
            Action work = () =>
            {
                try
                {
                    var reply = Call(new Dictionary<string, object> { ["cmd"] = "persist", ["doc"] = key }, true, null, 15000);
                    Log.Write($"persist {key}: " + (Ok(reply) ? (reply.ContainsKey("saved") && reply["saved"] is bool b && b ? "saved" : "already on disk") : "failed"));
                }
                catch (Exception e) { Log.Write("persist failed: " + e.Message); }
            };
            if (wait) work();
            else Background(work);
        }

        public string Status(Word.Document doc)
        {
            var s = Find(doc);
            if (s == null || (s.Text == null && !s.Reading))
                return "המסמך יוכן לחיפוש בעוד רגע. אפשר כבר לחפש.";
            if (s.Error != null) return "אפשר לחפש. (ההכנה ברקע נכשלה: " + s.Error + ")";
            if (s.Text == null || s.Reading || s.Indexing && s.IndexedKey == null)
                return "מכין את המסמך לחיפוש…";
            int percent = Percent(s);
            if (percent < 100) return $"מכין את המסמך לחיפוש… {percent}%";
            string counts = Words.Paragraphs(s.Text.Texts.Count);
            return "המסמך מוכן לחיפוש · " + counts + " · " + Words.Headings(s.Text.Headings);
        }

        /// <summary>כמה מההכנה הסתיים: קריאת הטקסט (5%), מפת החיפוש ברכיב העזר (60%), הכותרות (35%).
        /// 100 רק כשהכל מוכן – אפשר לחפש תוך כדי הקלדה, וגם בכותרות.</summary>
        static int Percent(DocState s)
        {
            if (s.Text == null || s.Reading) return 2;
            bool indexed = s.IndexedKey != null && s.IndexedKey.StartsWith(s.Text.TextHash + "/", StringComparison.Ordinal);
            bool headings = s.Text.HasLevels && !s.NeedsHeadings && !s.DocxPending;
            if (indexed && headings) return 100;
            double index = indexed ? 1 : Math.Min(0.99, Math.Max(0, s.IndexProgress));
            double heads = headings ? 1 : Math.Min(0.99, s.Scan != null ? Math.Max(s.HeadingProgress, ScanProgress(s.Scan)) : s.HeadingProgress);
            if (!headings) s.HeadingProgress = heads;
            return (int)Math.Min(99, Math.Round(5 + 60 * index + 35 * heads));
        }

        static double ScanProgress(HeadingScan scan)
        {
            if (scan.Verify) return 1;
            if (scan.Phase == 0) return Math.Min(1, (double)scan.Visited / Math.Max(1, scan.Text.Texts.Count));
            return scan.Changed == null || scan.Changed.Length == 0 ? 1 : (double)scan.OutlineIndex / scan.Changed.Length;
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
            try { return s == null || !FocusGuard.Run(() => Fresh(s)); }
            catch { return true; }
        }

        /// <summary>האם אפשר לחפש תוך כדי הקלדה: המסמך כבר נקרא, לא השתנה, ורכיב העזר כבר בנה את מפת החיפוש
        /// (וגם הכותרות, לחיפוש בכותרות). אחרת חיפוש תוך כדי הקלדה היה קורא את המסמך ומעכב את Word.</summary>
        public bool ReadyForLive(Word.Document doc, bool headings)
        {
            var s = Find(doc);
            if (s == null || s.Text == null || s.Reading || s.Indexing || s.IndexedKey != s.Text.Key) return false;
            if (headings && (!s.Text.HasLevels || s.NeedsHeadings)) return false;
            try { return FocusGuard.Run(() => Fresh(s)); }
            catch { return false; }
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

        /// <summary>המסמך נקרא מחדש כי ייתכן שהשתנה: גם אם הטקסט זהה, אולי סגנון של פסקה השתנה.</summary>
        static void Reread(DocState s)
        {
            s.Edits++;
            if (s.Text != null) s.Unverified = true;
        }

        // ================================================================ הלולאה: מנות קצרות, כל הזמן
        void Tick()
        {
            try
            {
                if (!_openDocsQueued)
                {
                    if ((DateTime.Now - _started).TotalSeconds < 3 || IdleMs() < 300) return;
                    _openDocsQueued = true;
                    QueueOpenDocuments();
                }

                // קודם מה שחסר (טקסט, ואז כותרות), ורק אחר כך אימות
                DocState next = null;
                int nextRank = int.MaxValue;
                bool pending = false;
                DateTime now = DateTime.Now;
                foreach (var s in _docs)
                {
                    if (s.Reading) continue;                    // התוצאה תגיע לבד, ותפעיל את השעון אם צריך
                    if (s.DocxPending)
                    {
                        // הכותרות נקראות מהקובץ ברכיב העזר; אם זה נתקע – חוזרים לקריאה דרך Word
                        if ((now - s.DocxSince).TotalSeconds < 20) { pending = true; continue; }
                        s.DocxPending = false;
                        Log.Write("headings from file: no answer in time – reading them in Word");
                    }
                    int rank = s.NeedsRead ? 0 : s.NeedsHeadings ? 1 : s.NeedsVerify ? 2 : -1;
                    if (rank < 0) continue;
                    pending = true;
                    if (s.NotBefore <= now && rank < nextRank) { next = s; nextRank = rank; }
                }
                if (!pending) { _timer.Stop(); return; }
                if (next == null) return;

                if (next.NeedsRead)
                {
                    // קריאת הטקסט היא קריאה אחת שאי אפשר לחלק – מחכים להפסקה קצרה בהקלדה
                    if (TypingIdleMs() >= (FocusGuard.InAddIn ? 1000 : 350) && !MouseButtonDown() && WordAvailable())
                        FocusGuard.Run(() => BeginRead(next));
                }
                else
                {
                    int budget = SliceBudget();
                    if (budget > 0 && WordAvailable())
                        FocusGuard.Run(() => HeadingSlice(next, budget));
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

        /// <summary>כמה אלפיות שנייה של עבודה מול Word מותר עכשיו. רק כתיבה עוצרת: מיד אחרי הקשה – כלום (Word
        /// מטפל בה); אחר כך מנה קצרה שלא מורגשת; כשלא מקלידים כמה שניות – מנות ארוכות יותר. עכבר לא עוצר:
        /// בזמן תזוזה, גלילה או גרירה המנות רק קצרות (כדי שהמסך יישאר חלק).</summary>
        static int SliceBudget()
        {
            int typing = TypingIdleMs();
            if (typing < 100) return 0;
            int budget = typing < 1000 ? 12 : typing < 5000 ? 30 : 80;
            if (MouseButtonDown()) return Math.Min(budget, 8);
            if (IdleMs() < 400) return Math.Min(budget, 16);          // העכבר זז / גלילה
            return budget;
        }

        /// <summary>זמן מההקשה האחרונה (ואם אין "וו" למקלדת – מכל קלט, כמו קודם).</summary>
        static int TypingIdleMs() => Typing.Active ? Typing.IdleMs : IdleMs();

        static bool MouseButtonDown() => GetAsyncKeyState(0x01) < 0 || GetAsyncKeyState(0x02) < 0;

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
            if (previous != null) Reread(s);
            string path = null;
            try { path = s.Doc.FullName; } catch { }
            s.Path = HeadingCache.HasIdentity(path) ? path : null;
            bool saved = s.ReadSaved;
            s.NeedsRead = false;
            s.Reading = true;
            s.Error = null;
            Background(() =>
            {
                try
                {
                    DocText dt;
                    CacheEntry cached = null;
                    bool trusted = false;
                    if (previous != null)
                        dt = previous.TextHash == DocText.Hash(raw) ? previous : DocText.Build(raw, previous);
                    else
                    {
                        // פתיחה: מה שנשמר בדיסק מהפעם הקודמת שהמסמך הזה היה פתוח
                        cached = s.Path != null ? HeadingCache.Load(s.Path) : null;
                        if (cached != null)
                        {
                            dt = DocText.Build(raw, cached.Snap);
                            trusted = cached.Verified && saved && dt.TextHash == cached.Snap.TextHash
                                      && HeadingCache.FileStamp(s.Path, out long ticks, out long size)
                                      && ticks == cached.FileTicks && size == cached.FileSize;
                        }
                        else dt = DocText.Build(raw);
                    }
                    Post(() =>
                    {
                        s.Reading = false;
                        if (!_docs.Contains(s)) return;
                        if (cached != null)
                        {
                            s.Unverified = !trusted;
                            s.NeedsVerify = !trusted;
                            Log.Write(trusted
                                ? $"cache: document unchanged since last time – {dt.Headings} headings ready without reading them"
                                : $"cache: document changed since last time – {dt.Headings} headings kept, {dt.Changed.Length} changed paragraphs to check, full check in the background");
                        }
                        Adopt(s, dt, previous);
                        string docx = null;
                        if (!dt.HasLevels && saved && IsDocxFile(s.Path))
                        {
                            docx = s.Path;
                            s.DocxPending = true;
                            s.DocxSince = DateTime.Now;
                        }
                        BeginIndex(s, dt, docx);
                    });
                }
                catch (Exception e)
                {
                    Post(() => { s.Reading = false; s.Error = e.Message; Log.Error("read", e); });
                }
            });
        }

        /// <summary>גרסה חדשה של הטקסט: נשמרת, והכותרות ייקראו אם צריך – בפעם הראשונה כולן, ואחרי עריכה (או
        /// כשהרמות הגיעו מהדיסק) רק הפסקאות שהשתנו; אם לא השתנתה אף פסקה עם טקסט – כלום.</summary>
        void Adopt(DocState s, DocText dt, DocText previous)
        {
            if (dt == s.Text) return;
            s.Text = dt;
            if (dt != previous || !dt.HasLevels)
            {
                s.Scan = null;
                if (dt.HasLevels && dt.Changed.Length == 0)
                {
                    s.NeedsHeadings = false;
                    if (s.NeedsVerify) Wake(s, 300);
                    else SaveCache(s);
                    return;
                }
                s.NeedsHeadings = true;
                s.HeadingProgress = 0;
                Wake(s, 300);
            }
        }

        static bool IsDocxFile(string path)
        {
            if (!HeadingCache.IsLocalFile(path)) return false;
            string ext = System.IO.Path.GetExtension(path).ToLowerInvariant();
            return ext == ".docx" || ext == ".docm" || ext == ".dotx" || ext == ".dotm";
        }

        /// <summary>רמות הכותרות מקובץ ה-docx הגיעו: כל כותרת לפסקה שלה. אם הכל התאים – הכותרות מוכנות בלי
        /// שום עבודה של Word; אחרת – בדיקה ב-Word ברקע (רק בשביל מה שלא התאים זה עדיין חוסך הרבה).</summary>
        void ApplyFileHeadings(DocState s, DocText dt, Dictionary<string, object> reply, long ms)
        {
            s.DocxPending = false;
            if (!_docs.Contains(s)) return;
            if (!Ok(reply) || !reply.ContainsKey("headings") || !(reply["headings"] is System.Collections.IList list))
            {
                Log.Write("headings from file: not available (" + (reply != null && reply.ContainsKey("error") ? reply["error"] : "?") + ") – reading them in Word");
                Wake(s, 0);
                return;
            }
            if (s.Text == null || s.Text.TextHash != dt.TextHash || s.Text.HasLevels)
            {
                Wake(s, 0);                                      // המסמך השתנה בינתיים, או שהכותרות כבר נקראו
                return;
            }
            var headings = new List<object[]>(list.Count);
            foreach (object h in list)
                if (h is System.Collections.IList x && x.Count >= 3) headings.Add(new[] { x[0], x[1], x[2] });
            int[] levels = s.Text.MatchFileHeadings(headings, out int unmatched);
            int fileParas = reply.ContainsKey("paras") ? Convert.ToInt32(reply["paras"]) : -1;
            bool exact = unmatched == 0 && fileParas == s.Text.Texts.Count;
            s.Scan = null;
            s.Text = s.Text.WithLevels(levels);
            s.NeedsHeadings = false;
            s.HeadingProgress = 1;
            // לא הכל התאים (או שמספר הפסקאות שונה) – בדיקה מלאה ב-Word ברקע, בלי לעכב את החיפוש
            s.NeedsVerify = !exact;
            s.Unverified = !exact;
            if (exact) s.LastFullScan = DateTime.Now;
            Log.Write($"headings from file: {s.Text.Headings} of {headings.Count} matched ({unmatched} not matched; " +
                      $"{fileParas:N0} paragraphs in the file, {s.Text.Texts.Count:N0} in Word) in {ms}ms – " +
                      (exact ? "no Word work needed" : "checking in Word in the background"));
            BeginIndex(s, s.Text);
            SaveCache(s);
            if (s.NeedsVerify) Wake(s, 500);
        }

        void Wake(DocState s, int delayMs)
        {
            DateTime when = DateTime.Now.AddMilliseconds(delayMs);
            if (s.NotBefore < when) s.NotBefore = when;
            _timer.Start();
        }

        void BeginIndex(DocState s, DocText dt, string docxPath = null)
        {
            if (docxPath != null)
            {
                // קודם הכותרות מהקובץ (מהיר), ורק אחר כך מפת החיפוש – רכיב העזר עונה לבקשה אחת בכל פעם
                Background(() =>
                {
                    var t = Stopwatch.StartNew();
                    Dictionary<string, object> reply;
                    try { reply = Call(new Dictionary<string, object> { ["cmd"] = "docx_headings", ["path"] = docxPath }, true, null, 20000); }
                    catch (Exception e) { reply = new Dictionary<string, object> { ["ok"] = false, ["error"] = e.Message }; }
                    long ms = t.ElapsedMilliseconds;
                    Post(() =>
                    {
                        ApplyFileHeadings(s, dt, reply, ms);
                        if (s.Text != null) BeginIndex(s, s.Text);
                    });
                });
                return;
            }
            if (s.IndexedKey == dt.Key || s.Indexing) return;
            s.Indexing = true;
            s.IndexProgress = 0;
            Background(() =>
            {
                try
                {
                    var t0 = Stopwatch.StartNew();
                    var reply = Ask(new Dictionary<string, object> { ["cmd"] = "index", ["doc"] = dt.Key }, dt, true,
                                    f => s.IndexProgress = f);
                    bool ok = Ok(reply);
                    bool fromDisk = ok && reply.ContainsKey("cached") && reply["cached"] is bool b && b && !reply.ContainsKey("sent");
                    Post(() =>
                    {
                        s.Indexing = false;
                        if (ok) s.IndexedKey = dt.Key;
                        else s.Error = reply.ContainsKey("error") ? Convert.ToString(reply["error"]) : "שגיאה";
                        string how = fromDisk ? " (search map was already on disk)"
                                   : reply.ContainsKey("normalized") ? $" (only {reply["normalized"]} changed paragraphs sent)" : "";
                        Log.Write($"index {dt.Texts.Count:N0} paragraphs ({dt.Headings} headings) in {t0.ElapsedMilliseconds}ms ok={ok}{how}");
                        if (s.Text != null && s.Text.Key != s.IndexedKey && ok) BeginIndex(s, s.Text);
                    });
                }
                catch (Exception e)
                {
                    Post(() => { s.Indexing = false; s.Error = e.Message; Log.Error("index", e); });
                }
            });
        }

        // ================================================================ שמירה בדיסק
        /// <summary>שומר את מה שידוע על המסמך (טביעות אצבע של הפסקאות ורמות הכותרות), לפתיחה הבאה.</summary>
        void SaveCache(DocState s)
        {
            DocText dt = s.Text;
            string path = s.Path;
            if (path == null || dt == null || !dt.HasLevels || s.NeedsHeadings) return;
            bool saved;
            try { saved = FocusGuard.Run(() => s.Doc.Saved); }
            catch { saved = false; }
            // "מאומת" רק אם הרמות נקראו במלואן מהמסמך, והמסמך עכשיו זהה לקובץ שבדיסק
            bool verified = saved && !s.Unverified && !s.NeedsVerify;
            DocSnapshot snap = dt.Snapshot();
            Background(() =>
            {
                var entry = new CacheEntry { Snap = snap };
                entry.Verified = HeadingCache.FileStamp(path, out entry.FileTicks, out entry.FileSize) && verified;
                HeadingCache.Save(path, entry);
            });
        }

        // ================================================================ הכותרות, במנות קצרות
        static HeadingScan NewScan(DocText t)
        {
            if (t.HasLevels && t.Changed.Length <= IncrementalLimit)
                return new HeadingScan { Text = t, Levels = (int[])t.Levels.Clone(), Phase = 3, Changed = t.Changed, Found = t.Headings };
            return new HeadingScan { Text = t, Levels = new int[t.Texts.Count] };
        }

        /// <summary>מנה אחת של קריאת הכותרות (עד budgetMs). מחזיר true כשהסתיים.</summary>
        bool HeadingSlice(DocState s, int budgetMs)
        {
            if (s.Text == null) { s.NeedsHeadings = s.NeedsVerify = false; return true; }
            var sw = Stopwatch.StartNew();
            var scan = s.Scan;
            if (scan == null || scan.Text != s.Text)
            {
                scan = s.NeedsHeadings
                    ? NewScan(s.Text)
                    : new HeadingScan { Text = s.Text, Levels = new int[s.Text.Texts.Count], Verify = true };
                scan.EditsAtStart = s.Edits;
                s.Scan = scan;
            }
            scan.Time.Start();
            bool done = false;
            try
            {
                int docEnd = s.Doc.Content.End;
                while (!done && sw.ElapsedMilliseconds < budgetMs)
                {
                    if (scan.Phase == 0)
                    {
                        done = WalkStep(s, scan);
                    }
                    else
                    {
                        if (scan.OutlineIndex >= scan.Changed.Length)
                        {
                            // רוב הפסקאות שנערכו לא נמצאו במסמך (משהו השתנה מאוד) – קוראים את כל הכותרות
                            if (scan.Checked >= 5 && scan.Missed * 5 > scan.Checked)
                            {
                                Log.Write($"headings: {scan.Missed} of {scan.Checked} changed paragraphs not found – reading all headings");
                                var full = new HeadingScan { Text = scan.Text, Levels = new int[scan.Text.Texts.Count], EditsAtStart = s.Edits };
                                full.Time.Start();
                                scan.Time.Stop();
                                scan = s.Scan = full;
                                continue;
                            }
                            done = true;
                            break;
                        }
                        int i = scan.Changed[scan.OutlineIndex++];
                        scan.Checked++;
                        Word.Paragraph p = scan.Text.LocateParagraph(s.Doc, i, docEnd);
                        if (p == null) { scan.Missed++; continue; }
                        int level = (int)p.OutlineLevel;                     // 10 = גוף הטקסט
                        scan.Levels[i] = level >= 1 && level <= 9 ? level : 0;
                        if (scan.Levels[i] > 0) scan.Found++;
                        Release(p);
                    }
                    scan.Failures = 0;
                }
            }
            catch (Exception e)
            {
                // Word עסוק (חלון דו-שיח, עריכה בתא…), או שהפסקה שעמדנו עליה נמחקה – ממשיכים מהמקום האחרון
                // שידוע; רק אחרי כמה כישלונות רצופים מוותרים
                scan.Failures++;
                Release(scan.Para);
                scan.Para = null;
                Log.Write($"headings: attempt failed ({scan.Failures}): {e.Message}");
                if (scan.Failures < MaxFailures)
                {
                    s.NotBefore = DateTime.Now.AddSeconds(scan.Failures < 3 ? 1 : 3);
                    scan.Time.Stop();
                    return false;
                }
                s.HeadingsError = e.Message;
                scan.Failed = true;
                done = true;
            }
            scan.Time.Stop();
            if (!done) return false;                                      // ממשיכים במנה הבאה

            Release(scan.Para);
            scan.Para = null;
            Finish(s, scan);
            return true;
        }

        /// <summary>פסקה אחת במעבר על המסמך: רמת החלוקה שלה, ואם היא כותרת – גם הטקסט והמקום, כדי לשייך
        /// אותה לפסקה שלה (כמה קריאות קטנות ל-Word; בלי Find ובלי שום שינוי). true כשהגענו לסוף המסמך.</summary>
        bool WalkStep(DocState s, HeadingScan scan)
        {
            if (scan.Para == null)
            {
                if (scan.Started && scan.Resume < 0) return true;           // כבר בסוף
                scan.Para = scan.Started
                    ? s.Doc.Range(scan.Resume, scan.Resume).Paragraphs.First    // אחרי תקלה: מהכותרת האחרונה שנמצאה
                    : s.Doc.Paragraphs.First;
                scan.Started = true;
                if (scan.Para == null) return true;
            }
            Word.Paragraph p = scan.Para;
            int level = (int)p.OutlineLevel;                                 // 10 = גוף הטקסט
            if (level >= 1 && level <= 9)
            {
                Word.Range pr = p.Range;
                int start = pr.Start;
                string clean = DocText.Clean(pr.Text);
                Release(pr);
                if (clean.Trim().Length > 0)
                {
                    int idx = scan.Text.MatchNear(clean, start);
                    if (idx < 0) scan.Unmatched++;
                    else if (scan.Levels[idx] == 0)
                    {
                        scan.Levels[idx] = level;
                        scan.Found++;
                        scan.Text.Learn(idx, start);
                    }
                }
                scan.Resume = start;
            }
            scan.Visited++;
            Word.Paragraph next = p.Next();
            Release(p);
            scan.Para = next;
            if (next == null)
            {
                scan.Resume = -1;
                return true;
            }
            return false;
        }

        static void Release(object com)
        {
            try { if (com != null && Marshal.IsComObject(com)) Marshal.ReleaseComObject(com); } catch { }
        }

        /// <summary>הסריקה הסתיימה: הרמות החדשות נכנסות לשימוש, נשמרות בדיסק, ורכיב העזר מתעדכן.</summary>
        void Finish(DocState s, HeadingScan scan)
        {
            s.Scan = null;
            bool full = scan.Phase != 3;
            if (scan.Verify && scan.Failed)
            {
                // אימות שלא הסתיים: נשארים עם הרמות הידועות, ולא מנסים שוב ושוב
                s.NeedsVerify = false;
                Log.Write("headings: background check did not finish – keeping the known headings");
                return;
            }
            DocText withLevels = scan.Text.WithLevels(scan.Levels);
            bool changed = !scan.Text.HasLevels || withLevels.Key != scan.Text.Key;
            if (s.Text == scan.Text) s.Text = withLevels;
            s.NeedsHeadings = false;
            s.HeadingProgress = 1;
            if (full)
            {
                s.NeedsVerify = false;
                s.LastFullScan = DateTime.Now;
                s.Unverified = scan.Failed || s.Edits != scan.EditsAtStart;
            }

            var perLevel = new int[10];
            foreach (int l in scan.Levels) if (l > 0 && l < 10) perLevel[l]++;
            var levels = new System.Text.StringBuilder();
            for (int l = 1; l <= 9; l++) if (perLevel[l] > 0) levels.Append($" L{l}={perLevel[l]}");
            if (scan.Phase == 3)
                Log.Write($"headings: {withLevels.Headings} – checked only the {scan.Checked} changed paragraphs " +
                          $"({scan.Missed} not found){levels} in {scan.Time.ElapsedMilliseconds}ms");
            else
                Log.Write($"headings{(scan.Verify ? " (background check" + (changed ? ", CHANGED" : ", no change") + ")" : "")}: " +
                          $"{withLevels.Headings} ({scan.Visited:N0} paragraphs read, not matched {scan.Unmatched}){levels} " +
                          $"in {scan.Time.ElapsedMilliseconds}ms of work");

            if (s.Text == withLevels)
            {
                BeginIndex(s, s.Text);
                SaveCache(s);
                if (scan.Verify && changed)
                {
                    try { HeadingsChanged?.Invoke(s.Doc); }
                    catch (Exception e) { Log.Error("headings changed", e); }
                }
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
            return FocusGuard.Run(() => EnsureHeadingsCore(doc, budgetMs));
        }

        bool EnsureHeadingsCore(Word.Document doc, int budgetMs)
        {
            var s = StateOf(doc);
            if (s.Text == null || !Fresh(s))
            {
                DocText previous = s.Text;
                string raw = ReadText(s);
                if (previous != null) Reread(s);
                DocText dt = previous != null && previous.TextHash == DocText.Hash(raw) ? previous : DocText.Build(raw, previous);
                Adopt(s, dt, previous);
                s.NeedsRead = false;
            }
            if (s.Text.HasLevels && !s.NeedsHeadings) return true;
            if (s.DocxPending && (DateTime.Now - s.DocxSince).TotalSeconds < 20) return false;   // עוד רגע – מהקובץ
            s.DocxPending = false;
            s.NeedsHeadings = true;
            return HeadingSlice(s, budgetMs) && !s.NeedsHeadings;
        }

        /// <summary>חיפוש בכותרות במסמך שאולי נערך מאז שהכותרות נקראו במלואן: אימות מלא ברקע (לא מעכב את
        /// החיפוש). אם יתגלה שינוי – HeadingsChanged.</summary>
        void RequestVerify(DocState s)
        {
            if (!s.Unverified || s.NeedsVerify || s.Text == null || !s.Text.HasLevels) return;
            if ((DateTime.Now - s.LastFullScan).TotalSeconds < 20) return;
            s.NeedsVerify = true;
            Wake(s, 0);
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
            if (reuse == null) raw = FocusGuard.Run(() => Fresh(s) ? null : ReadText(s));
            if (raw != null && previous != null) Reread(s);
            DocText known = reuse ?? (raw == null ? previous : null);
            bool headings = reuse == null && request.ContainsKey("headings_only") && request["headings_only"] is bool h && h;
            Task.Run(() =>
            {
                try
                {
                    DocText dt = known ?? (previous != null && previous.TextHash == DocText.Hash(raw) ? previous : DocText.Build(raw, previous));
                    var req = new Dictionary<string, object>(request) { ["cmd"] = "search", ["doc"] = dt.Key };
                    var reply = Ask(req, dt, false, null);
                    Post(() =>
                    {
                        if (_docs.Contains(s) && reuse == null)
                        {
                            Adopt(s, dt, previous);
                            if (Ok(reply) && dt == s.Text) s.IndexedKey = dt.Key;
                            s.NeedsRead = false;
                            if (headings) RequestVerify(s);
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

        Dictionary<string, object> Call(Dictionary<string, object> req, bool background, Action<double> progress = null, int timeoutMs = 60000)
        {
            if (progress != null) req["progress"] = true;
            return _json.Deserialize<Dictionary<string, object>>(_helper.Call(_json.Serialize(req), timeoutMs, background, progress));
        }

        /// <summary>שולח לרכיב העזר. הפסקאות נשלחות רק אם הוא לא מכיר את הטקסט הזה – לא מהזיכרון (גרסה
        /// קודמת באותה הפעלה) ולא מהדיסק (מפת חיפוש שנשמרה בפתיחה קודמת).</summary>
        Dictionary<string, object> Ask(Dictionary<string, object> req, DocText dt, bool background, Action<double> progress)
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
                var relevel = Call(new Dictionary<string, object> { ["cmd"] = "relevel", ["from"] = sibling, ["doc"] = dt.Key, ["levels"] = dt.Levels }, background);
                if (Ok(relevel))
                {
                    known = true;
                    lock (_sent) _sent.Add(dt.Key);
                }
            }
            Dictionary<string, object> patched = null;
            if (!known && dt.CanPatch)
            {
                // אחרי עריכה: רק הפסקאות שהשתנו (רכיב העזר לוקח את השאר מהגרסה הקודמת – בזיכרון או בדיסק)
                patched = Call(new Dictionary<string, object>
                {
                    ["cmd"] = "patch", ["doc"] = dt.Key, ["text"] = dt.TextHash, ["base"] = dt.BaseTextHash,
                    ["ops"] = dt.PatchOps(), ["levels"] = dt.LevelString(),
                }, background, progress);
                if (Ok(patched))
                {
                    known = true;
                    lock (_sent)
                    {
                        _sent.RemoveWhere(k => k.StartsWith(dt.BaseTextHash + "/", StringComparison.Ordinal));   // שוחררו שם
                        _sent.Add(dt.Key);
                    }
                }
                else patched = null;
            }
            if (!known)
            {
                // אולי מפת החיפוש של הטקסט הזה כבר בדיסק: שולחים רק את טביעת האצבע ואת רמות הכותרות
                req["text"] = dt.TextHash;
                req["levels"] = dt.LevelString();
            }
            var reply = Call(req, background, known ? null : progress);
            if (reply.ContainsKey("need_paras"))                  // לא מוכר לרכיב העזר (או שהופעל מחדש / פינה את המסמך)
            {
                req["text"] = dt.TextHash;
                req.Remove("levels");
                req["paras"] = dt.Paras();
                reply = Call(req, background, progress);
                reply["sent"] = true;
            }
            if (patched != null && patched.ContainsKey("normalized") && !reply.ContainsKey("normalized"))
                reply["normalized"] = patched["normalized"];
            if (Ok(reply)) lock (_sent) _sent.Add(dt.Key);
            return reply;
        }

        // ================================================================ עזרים
        void Post(Action a)
        {
            try { _ui.BeginInvoke(a); } catch (Exception e) { Log.Error("post", e); }
        }

        /// <summary>עבודה ברקע שאף אחד לא מחכה לה – בעדיפות נמוכה, כדי לא להפריע ל-Word ולתוכנות אחרות.</summary>
        static void Background(Action work)
        {
            Task.Run(() =>
            {
                Thread thread = Thread.CurrentThread;
                ThreadPriority old = thread.Priority;
                try
                {
                    thread.Priority = ThreadPriority.BelowNormal;
                    work();
                }
                finally { thread.Priority = old; }
            });
        }

        /// <summary>Word לא באמצע משהו שאסור להפריע לו: חלון דו-שיח, שמירה או הדפסה ברקע.</summary>
        bool WordAvailable()
        {
            int now = Environment.TickCount;
            if (_mainWindow == IntPtr.Zero || unchecked(now - _mainWindowAt) > 2000)
            {
                using (Process p = Process.GetCurrentProcess()) _mainWindow = p.MainWindowHandle;
                _mainWindowAt = now;
            }
            if (_mainWindow != IntPtr.Zero && !IsWindowEnabled(_mainWindow)) return false;     // חלון דו-שיח פתוח
            try
            {
                var app = _addin.Application;
                if (app.BackgroundSavingStatus != 0 || app.BackgroundPrintingStatus != 0) return false;
            }
            catch (COMException) { return false; }
            return true;
        }

        /// <summary>כמה אלפיות שנייה עברו מאז ההקשה או תזוזת העכבר האחרונה (בכל המחשב).</summary>
        static int IdleMs()
        {
            var info = new LASTINPUTINFO { cbSize = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO)) };
            if (!GetLastInputInfo(ref info)) return int.MaxValue;
            uint idle = unchecked((uint)Environment.TickCount - info.dwTime);
            return idle > int.MaxValue ? int.MaxValue : (int)idle;
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

        [DllImport("user32.dll")]
        static extern short GetAsyncKeyState(int vKey);

        public void Dispose()
        {
            _timer.Stop();
            _timer.Dispose();
            Typing.Stop();
            foreach (var s in _docs.ToArray()) Persist(s, true);
            _docs.Clear();
            try { _ui.Dispose(); } catch { }
        }
    }
}
