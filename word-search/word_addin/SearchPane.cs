// חלונית החיפוש שבצד המסמך: מחברת את התצוגה (PaneView) ל-Word ולרכיב החיפוש.
//
// הסמן במסמך זז אך ורק כשהמשתמש בוחר תוצאה בעצמו: לחיצה על תוצאה (או Enter עליה), או לחצני
// "הבאה / הקודמת" (⌄ ⌃ / F3). חיפוש – בהקלדה, ב-Enter או בשינוי אפשרות – רק מציג תוצאות.
//
// היענות: החיפוש עצמו רץ ברכיב העזר על תהליך נפרד; בתהליך הראשי של Word נעשים רק קריאת הטקסט
// (ורק אם המסמך השתנה מאז הקריאה הקודמת), הצגת התוצאות (רשימה מצוירת שמציירת רק מה שעל המסך)
// והקפיצה לתוצאה במסמך.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Word = Microsoft.Office.Interop.Word;

namespace HebDocSearch.WordAddin
{
    public class SearchPane : UserControl
    {
        readonly ThisAddIn _addin;
        readonly Word.Window _window;
        readonly Word.Document _doc;
        readonly PaneView _view = new PaneView { Dock = DockStyle.Fill };
        readonly Timer _timer = new Timer { Interval = 600 };
        readonly Timer _live = new Timer { Interval = 450 };     // חיפוש תוך כדי הקלדה (כמו ב-Word)
        readonly Timer _headingsRetry = new Timer { Interval = 150 };   // השלמת קריאת הכותרות במנות
        int _lastWidth, _initialWidth, _savedWidth;           // רוחב החלונית – נשמר רק אחרי גרירה של המשתמש
        readonly JavaScriptSerializer _json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };

        DocText _searched;                       // הגרסה של המסמך שבה נמצאו התוצאות
        List<ResultItem> _items = new List<ResultItem>();
        int _current = -1;
        string _lastKey;                         // השאילתה + האפשרויות של התוצאות המוצגות
        bool _busy, _again, _loading;
        int _generation, _ticks;

        internal SearchPane(ThisAddIn addin, Word.Window window, Word.Document doc)
        {
            _addin = addin;
            _window = window;
            _doc = doc;
            Controls.Add(_view);
            _view.ApplyTheme(Theme.Current());
            _view.SubmitRequested += OnSubmit;
            // "הבאה / הקודמת" – ממשיכים מהתוצאה שסומנה ברשימה (גם אם סומנה בחיצים בלי לעבור אליה)
            _view.NavigateRequested += d => Go((_view.List.SelectedIndex >= 0 ? _view.List.SelectedIndex : _current) + d);
            _view.ResultActivated += i => Go(i);
            _view.PopOutRequested += PopOut;
            _view.OptionsChanged += OnOptionsChanged;
            _view.ModeChanged += OnOptionsChanged;
            _view.QueryCleared += Reset;
            _view.Search.Box.TextChanged += (s, e) =>
            {
                _live.Stop();
                if (_view.Query.Length >= 2) _live.Start();
                else if (_view.Query.Length == 0 && _lastKey != null) Reset();
            };
            _live.Tick += (s, e) =>
            {
                _live.Stop();
                if (_view.Query.Length < 2 || Key() == _lastKey) return;
                // תוך כדי הקלדה מחפשים רק כשמפת החיפוש של המסמך כבר מוכנה לגמרי; אחרת – רק ב-Enter
                if (_addin.Preparer.ReadyForLive(_doc, _view.HeadingsOnly)) RunSearch();
                else _view.ShowHint("לחצו Enter לחיפוש");
            };
            _headingsRetry.Tick += (s, e) =>
            {
                _headingsRetry.Stop();
                if (_view.HeadingsOnly && _view.Query.Length > 0) RunSearch();
            };
            LoadSettings();
            Reset();
            _timer.Tick += (s, e) => Tick();
            _timer.Start();
        }

        internal void FocusSearch()
        {
            BeginInvoke(new Action(_view.FocusSearch));
        }

        /// <summary>כל ~חצי שנייה: ערכת הנושא של Office (אם הוחלפה) ומצב ההכנה של המסמך. בלי גישה למסמך.</summary>
        void Tick()
        {
            if (!Visible) return;
            if (++_ticks % 4 == 1)                              // ערכת הנושא – כל ~2.5 שניות מספיק
            {
                var theme = Theme.Current();
                if (theme != _view.CurrentTheme) _view.ApplyTheme(theme);
            }
            if (_addin.Preparer != null) _view.SetDocStatus(_addin.Preparer.Status(_doc));
            // רוחב החלונית: נשמר כשהמשתמש גורר את הקצה (אחרי שהגרירה נעצרה)
            if (_initialWidth == 0 && Width > 50) _initialWidth = _savedWidth = Width;
            if (Width != _lastWidth) _lastWidth = Width;                       // עדיין נגרר
            else if (_initialWidth > 0 && Math.Abs(Width - _savedWidth) > 4)
            {
                _savedWidth = Width;
                SaveSettings();
            }
        }

        void Reset()
        {
            _generation++;
            _items = new List<ResultItem>();
            _current = -1;
            _lastKey = null;
            _view.ShowIdle(_addin.Preparer?.Status(_doc) ?? "");
        }

        // ================================================================ חיפוש
        string Key()
        {
            return string.Join("|", _view.Query, _view.Forms, _view.Spelling, _view.Distance, _view.Near, _view.Ordered, _view.HeadingsOnly);
        }

        /// <summary>Enter בשדה החיפוש: רק מחפש (אם השאילתה או האפשרויות השתנו). לא מזיז את הסמן במסמך.</summary>
        void OnSubmit(bool shift)
        {
            _live.Stop();
            if (_view.Query.Length == 0) return;
            if (Key() != _lastKey || _items.Count == 0) RunSearch();
        }

        void OnOptionsChanged()
        {
            if (_loading) return;
            SaveSettings();
            if (_view.Query.Length > 0 && _lastKey != null) RunSearch();
        }

        Dictionary<string, object> Request(bool headingsOnly, int limit)
        {
            return new Dictionary<string, object>
            {
                ["query"] = _view.Query,
                ["headings_only"] = headingsOnly,
                ["limit"] = limit,
                ["options"] = new Dictionary<string, object>
                {
                    ["forms"] = PaneView.FormKeys[_view.Forms],
                    ["spelling"] = PaneView.SpellKeys[_view.Spelling],
                    ["distance"] = PaneView.DistKeys[_view.Distance],
                    ["near"] = _view.Near,
                    ["ordered"] = _view.Ordered,
                },
            };
        }

        void RunSearch()
        {
            if (_view.Query.Length == 0) return;
            if (_busy) { _again = true; return; }          // החיפוש הבא ירוץ כשהנוכחי יסתיים
            _busy = true;
            _again = false;
            int generation = ++_generation;
            string key = Key();
            bool headings = _view.HeadingsOnly;
            var sw = Stopwatch.StartNew();
            _headingsRetry.Stop();
            try
            {
                // "כותרות" לפני שהכותרות נקראו – משלימים עכשיו, במנות קצרות (Word ממשיך להגיב בין המנות)
                if (headings && !_addin.Preparer.HeadingsReady(_doc))
                {
                    int found = _addin.Preparer.HeadingsFoundSoFar(_doc);
                    _view.BeginSearch(true, found > 0 ? $"קורא את הכותרות… ({found:N0} עד עכשיו)" : "קורא את הכותרות של המסמך…");
                    _view.Update();
                    if (!_addin.Preparer.EnsureHeadings(_doc, 700))
                    {
                        _busy = false;
                        _headingsRetry.Start();
                        return;
                    }
                }
                // אם צריך לקרוא את המסמך מחדש (נערך מאז) – "מחפש…" מוצג לפני הקריאה
                bool reading = _addin.Preparer.WillRead(_doc);
                _view.BeginSearch(reading);
                if (reading) _view.Update();
                _addin.Preparer.Search(_doc, Request(headings, 300), (reply, text, error) =>
                {
                    _busy = false;
                    if (IsDisposed) return;
                    if (_again) { RunSearch(); return; }
                    if (generation != _generation) return;
                    try
                    {
                        if (error != null) throw error;
                        if (!(reply.ContainsKey("ok") && (bool)reply["ok"]))
                            throw new Exception(reply.ContainsKey("error") ? Convert.ToString(reply["error"]) : "שגיאה בחיפוש");
                        _searched = text;
                        _lastKey = key;
                        ShowResults(reply, text, headings);
                        Log.Write($"search '{_view.Query}' headings={headings}: {reply["total"]} hits in {sw.ElapsedMilliseconds}ms");
                        CountOtherMode(text, headings, generation);
                    }
                    catch (Exception ex) { SearchFailed(ex); }
                });
            }
            catch (Exception ex)
            {
                _busy = false;
                SearchFailed(ex);
            }
        }

        /// <summary>המספר בלשונית השנייה (כמה תוצאות יש בכותרות / בכל הטקסט), בלי לקרוא שוב את המסמך.</summary>
        void CountOtherMode(DocText text, bool headings, int generation)
        {
            if (!headings && (text == null || !text.HasLevels)) return;      // הכותרות עוד לא נקראו – לא מציגים 0 מטעה
            try
            {
                _addin.Preparer.Search(_doc, Request(!headings, 1), (reply, t, error) =>
                {
                    if (IsDisposed || generation != _generation) return;
                    if (error == null && reply != null && reply.ContainsKey("ok") && (bool)reply["ok"])
                        _view.SetTabCount(!headings, Convert.ToInt32(reply["total"]));
                }, text);
            }
            catch (Exception ex) { Log.Error("count", ex); }
        }

        void SearchFailed(Exception ex)
        {
            Log.Error("search", ex);
            _items = new List<ResultItem>();
            _current = -1;
            _lastKey = null;
            _view.ShowMessage("", "לא ניתן לחפש", new[] { ex.Message }, true);
        }

        void ShowResults(Dictionary<string, object> reply, DocText text, bool headings)
        {
            int total = Convert.ToInt32(reply["total"]);
            int docHeadings = Convert.ToInt32(reply["headings"]);
            int terms = reply.ContainsKey("n_terms") ? Convert.ToInt32(reply["n_terms"]) : 1;
            var hits = (IList)reply["hits"];
            _items = new List<ResultItem>(hits.Count);
            _current = -1;
            string noPath = docHeadings > 0 && !headings ? "לפני הכותרת הראשונה" : "";
            foreach (Dictionary<string, object> h in hits)
            {
                var item = new ResultItem
                {
                    Number = _items.Count + 1,
                    Para = Convert.ToInt32(h["para"]),
                    Level = h.ContainsKey("level") ? Convert.ToInt32(h["level"]) : 0,
                    Covered = h.ContainsKey("covered") ? Convert.ToInt32(h["covered"]) : terms,
                    Terms = terms,
                    HeadingHit = headings,
                    NoPathText = noPath,
                };
                foreach (IList r in (IList)h["ranges"])
                    item.Ranges.Add(new[] { Convert.ToInt32(r[0]), Convert.ToInt32(r[1]) });
                if (h.ContainsKey("path") && h["path"] is IList path)
                {
                    var p = new List<string>();
                    foreach (object s in path) p.Add(Convert.ToString(s));
                    item.Path = p.ToArray();
                }
                else if (h.ContainsKey("heading") && Convert.ToString(h["heading"]).Length > 0)
                    item.Path = new[] { Convert.ToString(h["heading"]) };
                foreach (IList seg in (IList)h["snippet"])
                    item.Snippet.Add(new Seg { Text = Convert.ToString(seg[0]), Kind = Convert.ToInt32(seg[1]) });
                _items.Add(item);
            }

            if (_items.Count == 0)
            {
                if (headings && docHeadings == 0)
                    _view.ShowMessage("אין כותרות", "אין במסמך כותרות", new[]
                    {
                        "כותרות הן פסקאות בסגנונות 'כותרת 1' עד 'כותרת 9', או פסקאות עם רמת חלוקה.",
                        "בלשונית 'תוצאות' מחפשים בכל הטקסט.",
                    }, false);
                else
                {
                    var tips = new List<string>();
                    if (_view.Forms < 2) tips.Add("אפשר להרחיב: מילים ← כל ההטיות.");
                    if (_view.Spelling == 0) tips.Add("או: מילים ← כתיב מלא וחסר.");
                    if (_view.Distance == 0 && _view.Query.Contains(" ")) tips.Add("או: מרחק ← באותה פסקה.");
                    if (headings) tips.Add($"החיפוש היה בכותרות בלבד ({Words.Headings(docHeadings)}).");
                    _view.ShowMessage(Words.Results(0), "לא נמצאו תוצאות", tips.ToArray(), false);
                }
                _view.SetTabCount(headings, 0);
                return;
            }
            _view.ShowResults(_items, total, FormsText(reply));    // בלי לגעת בסמן במסמך
        }

        static string FormsText(Dictionary<string, object> reply)
        {
            if (!reply.ContainsKey("forms") || !(reply["forms"] is IList forms) || forms.Count < 2) return "";
            var sb = new StringBuilder("נמצא: ");
            int shown = 0;
            foreach (IList f in forms)
            {
                if (shown == 6) { sb.Append(" · …"); break; }
                if (shown > 0) sb.Append(" · ");
                sb.Append(Convert.ToString(f[0])).Append(' ').Append(Convert.ToInt32(f[1]).ToString("N0"));
                shown++;
            }
            return sb.ToString();
        }

        // ================================================================ מעבר לתוצאה במסמך
        /// <summary>רק כשהמשתמש בחר תוצאה: לחיצה עליה / Enter עליה ברשימה, או "הבאה / הקודמת".</summary>
        void Go(int i)
        {
            if (_items.Count == 0) return;
            if (i < 0) i = _items.Count - 1;                     // מתחילים מחדש מהסוף / מההתחלה
            if (i >= _items.Count) i = 0;
            _current = i;
            _view.SetCurrent(i, _items.Count);
            var hit = _items[i];
            try
            {
                // המיקוד נשאר בחלונית (כדי שהקלדה לא תגיע למסמך); לעריכה – לוחצים במסמך
                bool found = FocusGuard.Run(() =>
                {
                    Word.Range rng = _searched?.Locate(_doc, hit.Para, hit.Ranges);
                    if (rng == null) return false;
                    _addin.Preparer.SelectInDocument(() =>
                    {
                        rng.Select();
                        try { _window.ScrollIntoView(rng, true); } catch { }
                    });
                    return true;
                });
                if (!found) throw new Exception("הטקסט השתנה מאז החיפוש – חפשו שוב");
            }
            catch (Exception ex)
            {
                Log.Error("select", ex);
                _view.SetNote("לא ניתן להגיע למקום במסמך: " + ex.Message, true);
            }
        }

        // ================================================================ הצג בחלון נפרד (ניסיוני)
        /// <summary>חלון קטן עם כ-70 מילים סביב התוצאה (35 לפני, 35 אחרי). לא מזיז את הסמן במסמך;
        /// "עבור למקום במסמך" בחלון – כמו לחיצה על התוצאה.</summary>
        void PopOut(int i)
        {
            if (i < 0 || i >= _items.Count || _searched == null) return;
            var hit = _items[i];
            try
            {
                var excerpt = _searched.Around(hit.Para, hit.Ranges, 35, 35);
                if (excerpt == null) return;
                float scale = _view.CurrentMetrics?.Scale ?? Assets.SystemScale;
                var win = new ContextWindow(_view.CurrentTheme, scale, hit.Number, hit.Path, excerpt, () => Go(i));
                win.PlaceNear(Cursor.Position);
                win.Show(new WordOwner(FindForm()?.Handle ?? IntPtr.Zero));
                Log.Write($"pop-out result {hit.Number}: {excerpt.Text.Length} chars");
            }
            catch (Exception ex) { Log.Error("pop-out", ex); }
        }

        /// <summary>הבעלים של החלון: החלון של Word, כדי שיישאר מעליו ולא ייעלם מאחוריו.</summary>
        sealed class WordOwner : IWin32Window
        {
            public WordOwner(IntPtr handle) { Handle = handle != IntPtr.Zero ? handle : System.Diagnostics.Process.GetCurrentProcess().MainWindowHandle; }
            public IntPtr Handle { get; }
        }

        // ================================================================ הגדרות
        static string SettingsPath
        {
            get
            {
                string dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "HebWordSearch");
                Directory.CreateDirectory(dir);
                return Path.Combine(dir, "word-addin.json");
            }
        }

        void LoadSettings()
        {
            _loading = true;
            try
            {
                if (!File.Exists(SettingsPath)) return;
                var s = _json.Deserialize<Dictionary<string, object>>(File.ReadAllText(SettingsPath, Encoding.UTF8));
                int Get(string key, int fallback) => s.ContainsKey(key) ? Convert.ToInt32(s[key]) : fallback;
                bool GetB(string key, bool fallback) => s.ContainsKey(key) ? Convert.ToBoolean(s[key]) : fallback;
                _view.SetOptions(Get("forms", 1), Get("spelling", 0), Get("distance", 0), Get("near", 3), GetB("ordered", true), GetB("headings", false));
                _savedWidth = _lastWidth = _initialWidth = 0;
            }
            catch (Exception e) { Log.Error("settings", e); }
            finally { _loading = false; }
        }

        void SaveSettings()
        {
            try
            {
                var s = new Dictionary<string, object>
                {
                    ["forms"] = _view.Forms,
                    ["spelling"] = _view.Spelling,
                    ["distance"] = _view.Distance,
                    ["near"] = _view.Near,
                    ["ordered"] = _view.Ordered,
                    ["headings"] = _view.HeadingsOnly,
                };
                int logical = SavedWidth();
                if (_initialWidth > 0 && _savedWidth != _initialWidth) logical = (int)Math.Round(_savedWidth / Assets.SystemScale);
                if (logical > 0) s["pane_w"] = logical;
                File.WriteAllText(SettingsPath, _json.Serialize(s), Encoding.UTF8);
            }
            catch { }
        }

        /// <summary>רוחב החלונית שנשמר (בפיקסלים של 100%), או 0.</summary>
        internal static int SavedWidth()
        {
            try
            {
                if (!File.Exists(SettingsPath)) return 0;
                var s = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(File.ReadAllText(SettingsPath, Encoding.UTF8));
                return s.ContainsKey("pane_w") ? Math.Max(240, Math.Min(1200, Convert.ToInt32(s["pane_w"]))) : 0;
            }
            catch { return 0; }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                _headingsRetry.Stop();
                _headingsRetry.Dispose();
                _timer.Stop();
                _timer.Dispose();
                _live.Stop();
                _live.Dispose();
            }
            base.Dispose(disposing);
        }
    }
}
