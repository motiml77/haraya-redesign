// הכנת המסמכים לחיפוש מאחורי הקלעים – לפי ההנחיות של Microsoft לתוספים:
//   * כל גישה למודל של Word רק מהתהליך הראשי (המודל הוא STA), ומעט ככל האפשר;
//   * עבודה כבדה (חלוקה, טביעת אצבע, בניית מפת החיפוש) – על תהליך נפרד / ברכיב העזר, בעדיפות נמוכה;
//   * שום דבר בזמן הפתיחה עצמה: הטקסט נקרא (קריאה אחת) רגע אחרי שהמסמך נפתח, בהפסקה קצרה בהקלדה.
//
// מהירות בלי לתקוע: ההכנה לא מחכה שהמשתמש יפסיק לעבוד. היא רצה כל הזמן, במנות קצרות מאוד:
//   * כל קריאה ל-Word קצרה (חיפוש הכותרות נעשה על קטע של המסמך בכל פעם, והקטע מותאם כך שקריאה
//     אחת תיקח אלפיות שנייה בודדות) – ולכן המסך וההקלדה לא מרגישים אותה;
//   * כמה עבודה בכל מנה תלוי במשתמש: מיד אחרי הקשה או תזוזת עכבר – כלום; בזמן עבודה – ~12 אלפיות שנייה;
//     כשהוא נח – יותר. בין המנות Word מטפל בכל מה שמחכה לו;
//   * לא מחכים לרכיב העזר: בזמן שהוא בונה את מפת החיפוש (בתהליך אחר), הכותרות כבר נקראות.
//
// לא עושים פעמיים את אותה עבודה:
//   * לכל מסמך נשמר בדיסק (HeadingCache) מה שנקרא ממנו. בפתיחה הבאה, אם הקובץ לא השתנה – הכותרות
//     מוכנות מיד; אם השתנה – הרמות עוברות לפסקאות שלא השתנו, נבדקות רק הפסקאות החדשות, וברקע נעשה
//     אימות מלא אחד (שינוי של סגנון בלבד לא נראה בטקסט);
//   * מפת החיפוש עצמה נשמרת בדיסק אצל רכיב העזר לפי טביעת האצבע של הטקסט – לא נשלחת ולא נבנית שוב;
//   * אחרי עריכה בודקים רק את הפסקאות שנוספו או שנערכו. כשמחפשים בכותרות אחרי עריכה – אימות מלא ברקע,
//     ואם התגלה שינוי (פסקה שהפכה לכותרת) התוצאות מתעדכנות.
//
// כותרת = פסקה עם רמת חלוקה 1–9, כמו בחלונית הניווט של Word (סגנונות "כותרת 1–9" וגם סגנונות אישיים):
//     1. חיפוש של Word לפי רמת חלוקה (Find עם ParagraphFormat.OutlineLevel) – רק הכותרות עצמן;
//     2. אם זה לא נתמך או לא מצא כלום – לפי הסגנונות המובנים "כותרת 1" עד "כותרת 9";
//     3. ואז בדיקת רמת החלוקה של כל פסקה קצרה.
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
            public int Phase;                   // 0 חיפוש לפי רמת חלוקה, 1 לפי סגנון "כותרת N", 2 פסקה אחר פסקה,
                                                // 3 רק הפסקאות שהשתנו מאז הגרסה הקודמת
            public int Level = 1;               // הרמה / הסגנון שמחפשים עכשיו (1–9)
            public int Pos;                     // מאיפה ממשיך החיפוש של הרמה הנוכחית
            public int Chunk = FirstChunk;      // כמה תווים בכל קריאה ל-Find (מותאם לפי הזמן שהיא לוקחת)
            public int OutlineIndex;
            public int[] Changed;               // שלב 3: הפסקאות לבדיקה
            public int Checked, Missed;
            public int Found, FoundByOutline, FoundByStyle, Unmatched, Steps, Failures;
            public int EditsAtStart;
            public bool UsedFind, Failed;
            public Stopwatch Time = new Stopwatch();
        }

        const int IncrementalLimit = 500;       // יותר פסקאות שהשתנו (למשל הדבקה גדולה) – קוראים את כל הכותרות
        const int FirstChunk = 60000, MinChunk = 4000, MaxChunk = 4000000;
        const int ChunkOverlap = 400;           // אחרי קטע בלי כותרות חוזרים מעט אחורה (כותרת על קו התפר)
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
            if (s != null) _docs.Remove(s);
        }

        public string Status(Word.Document doc)
        {
            var s = Find(doc);
            if (s == null || (s.Text == null && !s.Reading))
                return "המסמך יוכן לחיפוש בעוד רגע. אפשר כבר לחפש.";
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
                    if (IdleMs() >= (FocusGuard.InAddIn ? 1000 : 350) && WordAvailable())
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

        /// <summary>כמה אלפיות שנייה של עבודה מול Word מותר עכשיו. מיד אחרי הקשה או תזוזת עכבר – כלום
        /// (Word מטפל בה); בזמן שהמשתמש עובד – מנה קצרה שלא מורגשת; כשהוא נח – מנות ארוכות יותר.</summary>
        static int SliceBudget()
        {
            if (GetAsyncKeyState(0x01) < 0 || GetAsyncKeyState(0x02) < 0) return 0;      // גרירה / לחיצה בעכבר
            int idle = IdleMs();
            if (idle < 80) return 0;
            if (idle < 1000) return 12;
            if (idle < 5000) return 30;
            return 80;
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
                        BeginIndex(s, dt);
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
                Wake(s, 300);
            }
        }

        void Wake(DocState s, int delayMs)
        {
            DateTime when = DateTime.Now.AddMilliseconds(delayMs);
            if (s.NotBefore < when) s.NotBefore = when;
            _timer.Start();
        }

        void BeginIndex(DocState s, DocText dt)
        {
            if (s.IndexedKey == dt.Key || s.Indexing) return;
            s.Indexing = true;
            Background(() =>
            {
                try
                {
                    var t0 = Stopwatch.StartNew();
                    var reply = Ask(new Dictionary<string, object> { ["cmd"] = "index", ["doc"] = dt.Key }, dt, true);
                    bool ok = Ok(reply);
                    bool fromDisk = ok && reply.ContainsKey("cached") && reply["cached"] is bool b && b && !reply.ContainsKey("sent");
                    Post(() =>
                    {
                        s.Indexing = false;
                        if (ok) s.IndexedKey = dt.Key;
                        else s.Error = reply.ContainsKey("error") ? Convert.ToString(reply["error"]) : "שגיאה";
                        Log.Write($"index {dt.Texts.Count:N0} paragraphs ({dt.Headings} headings) in {t0.ElapsedMilliseconds}ms ok={ok}" +
                                  (fromDisk ? " (search map was already on disk)" : ""));
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
                    if (scan.Phase < 2)
                    {
                        done = FindStep(s, scan, docEnd);
                    }
                    else if (scan.Phase == 3)
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
                    }
                    else
                    {
                        if (scan.OutlineIndex >= scan.Text.Texts.Count) { done = true; break; }
                        int i = scan.OutlineIndex++;
                        if (scan.Levels[i] != 0) continue;
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
                    scan.Failures = 0;
                }
            }
            catch (Exception e)
            {
                // Word עסוק (חלון דו-שיח, עריכה בתא…) – מנסים שוב; רק אחרי כמה כישלונות רצופים מוותרים
                scan.Failures++;
                Log.Write($"headings: attempt failed ({scan.Failures}): {e.Message}");
                if (scan.Failures < MaxFailures)
                {
                    s.NotBefore = DateTime.Now.AddSeconds(scan.Failures < 3 ? 1 : 3);
                    scan.Time.Stop();
                    ClearFind(s.Doc, scan);
                    return false;
                }
                s.HeadingsError = e.Message;
                scan.Failed = true;
                done = true;
            }
            scan.Time.Stop();
            ClearFind(s.Doc, scan);
            if (!done) return false;                                      // ממשיכים במנה הבאה

            Finish(s, scan);
            return true;
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
                          $"{withLevels.Headings} (outline find {scan.FoundByOutline}, style find {scan.FoundByStyle}, " +
                          $"per paragraph {scan.Found - scan.FoundByOutline - scan.FoundByStyle}, not matched {scan.Unmatched}){levels} " +
                          $"in {scan.Time.ElapsedMilliseconds}ms of work, {scan.Steps} steps, last chunk {scan.Chunk:N0}");

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

        /// <summary>צעד אחד של חיפוש הכותרות ב-Word: קטע אחד של המסמך, רמה אחת. הקטע קצר מספיק כדי
        /// שהקריאה תיקח אלפיות שנייה בודדות (ומתארך כשהיא מהירה). מחזיר true כשכל הסריקה הסתיימה.</summary>
        bool FindStep(DocState s, HeadingScan scan, int docEnd)
        {
            if (scan.Level > 9)
            {
                // החיפוש לפי רמת חלוקה עבד – הסגנונות "כותרת N" לא מוסיפים עליו (הם תמיד ברמת חלוקה N)
                if (scan.Phase == 0 && scan.FoundByOutline > 0) return true;
                scan.Phase++;
                scan.Level = 1;
                scan.Pos = 0;
                // פסקה אחר פסקה: רק אם החיפוש לפי רמת חלוקה לא מצא כלום (לא נתמך, או שאין במסמך כותרות)
                return scan.Phase == 2 && scan.Text.Texts.Count > 60000;
            }
            if (scan.Pos >= docEnd)
            {
                scan.Level++;
                scan.Pos = 0;
                return false;
            }

            int end = (int)Math.Min((long)docEnd, (long)scan.Pos + scan.Chunk);
            var clock = Stopwatch.StartNew();
            Word.Range r = s.Doc.Range(scan.Pos, end);
            bool found;
            try
            {
                scan.UsedFind = true;
                if (scan.Phase == 0) OutlineFind(r.Find, scan.Level);
                else StyleFind(s.Doc, r.Find, scan.Level);
                found = r.Find.Execute();
            }
            catch (COMException e) when (scan.Phase == 0 && scan.Steps == 0)
            {
                Log.Write("headings: find by outline level not available: " + e.Message);
                scan.Phase = 1;                     // ממשיכים לפי סגנונות
                scan.Level = 1;
                scan.Pos = 0;
                return false;
            }
            scan.Steps++;

            if (!found)
            {
                long ms = clock.ElapsedMilliseconds;
                if (ms <= 3 && scan.Chunk < MaxChunk) scan.Chunk *= 2;
                else if (ms > 12 && scan.Chunk > MinChunk) scan.Chunk /= 2;
                if (end >= docEnd)
                {
                    scan.Level++;
                    scan.Pos = 0;
                }
                else scan.Pos = Math.Max(scan.Pos + 1, end - ChunkOverlap);
                return false;
            }

            int start = r.Start, stop = r.End;
            int before = scan.Found;
            if (TakeFound(scan, r.Text, start, scan.Level) > 0)
            {
                // הטקסט שנמצא אינו פסקה שלמה (כותרת שנחתכה בקצה הקטע) – לוקחים את הפסקאות השלמות
                try
                {
                    object unit = Word.WdUnits.wdParagraph;
                    r.Expand(ref unit);
                    start = r.Start;
                    stop = Math.Max(stop, r.End);
                    scan.Unmatched += TakeFound(scan, r.Text, start, scan.Level);
                }
                catch (COMException) { scan.Unmatched++; }
            }
            if (scan.Phase == 0) scan.FoundByOutline += scan.Found - before;
            else scan.FoundByStyle += scan.Found - before;
            scan.Pos = Math.Max(stop, scan.Pos + 1);
            return false;
        }

        /// <summary>חיפוש של Word לפי רמת חלוקה (כמו "עיצוב ← פסקה ← רמת חלוקה" בחלון החיפוש):
        /// מוצא גם כותרות בסגנונות אישיים, לא רק "כותרת 1–9".</summary>
        static void OutlineFind(Word.Find f, int level)
        {
            f.ClearFormatting();
            f.Text = "";
            Word.ParagraphFormat pf = f.ParagraphFormat;
            pf.OutlineLevel = (Word.WdOutlineLevel)level;
            f.ParagraphFormat = pf;
            f.Format = true;
            f.Forward = true;
            f.Wrap = Word.WdFindWrap.wdFindStop;
            f.MatchCase = false;
            f.MatchWholeWord = false;
            f.MatchWildcards = false;
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

        /// <summary>החיפוש של Word זוכר את העיצוב האחרון (גם בחלון "חיפוש והחלפה") – מנקים אחרינו בסוף כל
        /// מנה, כדי שחיפוש של המשתמש בין המנות לא יושפע.</summary>
        static void ClearFind(Word.Document doc, HeadingScan scan)
        {
            if (!scan.UsedFind) return;
            scan.UsedFind = false;
            try
            {
                var f = doc.Content.Find;
                f.ClearFormatting();
                f.Format = false;
            }
            catch { }
        }

        /// <summary>כותרות שנמצאו (כמה פסקאות רצופות באותה רמה חוזרות כטווח אחד) → רמות הפסקאות.
        /// מחזיר כמה חלקים לא התאימו לאף פסקה (טווח שאינו פסקאות שלמות).</summary>
        static int TakeFound(HeadingScan scan, string text, int start, int level)
        {
            int offset = 0, unmatched = 0;
            foreach (string part in (text ?? "").Split('\r'))
            {
                string clean = DocText.Clean(part);
                if (clean.Trim().Length > 0)
                {
                    int idx = scan.Text.MatchNear(clean, start + offset);
                    if (idx < 0) unmatched++;
                    else if (scan.Levels[idx] == 0)
                    {
                        scan.Levels[idx] = level;
                        scan.Found++;
                        if (offset == 0) scan.Text.Learn(idx, start);
                    }
                }
                offset += part.Length + 1;
            }
            return unmatched;
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
                    var reply = Ask(req, dt, false);
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

        Dictionary<string, object> Call(Dictionary<string, object> req, bool background)
        {
            return _json.Deserialize<Dictionary<string, object>>(_helper.Call(_json.Serialize(req), 60000, background));
        }

        /// <summary>שולח לרכיב העזר. הפסקאות נשלחות רק אם הוא לא מכיר את הטקסט הזה – לא מהזיכרון (גרסה
        /// קודמת באותה הפעלה) ולא מהדיסק (מפת חיפוש שנשמרה בפתיחה קודמת).</summary>
        Dictionary<string, object> Ask(Dictionary<string, object> req, DocText dt, bool background)
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
            if (!known)
            {
                // אולי מפת החיפוש של הטקסט הזה כבר בדיסק: שולחים רק את טביעת האצבע ואת רמות הכותרות
                req["text"] = dt.TextHash;
                req["levels"] = dt.LevelString();
            }
            var reply = Call(req, background);
            if (reply.ContainsKey("need_paras"))                  // לא מוכר לרכיב העזר (או שהופעל מחדש / פינה את המסמך)
            {
                req["text"] = dt.TextHash;
                req.Remove("levels");
                req["paras"] = dt.Paras();
                reply = Call(req, background);
                reply["sent"] = true;
            }
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
            _docs.Clear();
            try { _ui.Dispose(); } catch { }
        }
    }
}
