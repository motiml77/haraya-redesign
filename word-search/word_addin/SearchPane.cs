// חלונית החיפוש שבצד המסמך. פקדי חלונות רגילים (ולא דפדפן משובץ – בחלוניות של Office מקשים
// כמו Backspace וחיצים לא תמיד מגיעים אליו). התוצאות מוצגות בתיבת טקסט עשיר: היא מסדרת עברית
// ומספרים נכון, ומסמנת בצהוב את המילים שנמצאו.
//
//   [שדה חיפוש ··········] [חיפוש]
//   מילים [עם אותיות שימוש ⌄]  כתיב [כפי שהוקלד ⌄]
//   מרחק [צמודות ⌄] [3]  ☑ לפי הסדר   ☐ בכותרות בלבד
//   נמצאו 12 תוצאות
//   ┌ תוצאות: הכותרת שמעל + הקטע, המילים בצהוב ┐
//   [‹] 3 מתוך 12 [›]
using System;
using System.Collections;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Word = Microsoft.Office.Interop.Word;

namespace HebDocSearch.WordAddin
{
    public class SearchPane : UserControl
    {
        // צבעים – כמו בתוכנה (hebsearch/gui/theme.py)
        static readonly Color Accent = ColorTranslator.FromHtml("#2563eb");
        static readonly Color AccentSoft = ColorTranslator.FromHtml("#eaf1ff");
        static readonly Color Text1 = ColorTranslator.FromHtml("#1c2330");
        static readonly Color Muted = ColorTranslator.FromHtml("#7b8596");
        static readonly Color Marker = ColorTranslator.FromHtml("#ffe94a");
        static readonly Color Border = ColorTranslator.FromHtml("#e1e5ec");
        static readonly Color Warn = ColorTranslator.FromHtml("#a55a00");

        static readonly string[] FormKeys = { "exact", "prefixes", "all" };
        static readonly string[] FormLabels = { "מדויק", "עם אותיות שימוש", "כל ההטיות" };
        static readonly string[] SpellKeys = { "none", "vy", "all" };
        static readonly string[] SpellLabels = { "כפי שהוקלד", "מלא וחסר (ו׳ י׳)", "כל אהו״י" };
        static readonly string[] DistKeys = { "adjacent", "near", "paragraph" };
        static readonly string[] DistLabels = { "צמודות", "עד N מילים ביניהן", "באותה פסקה" };

        readonly TextBox _query = new TextBox();
        readonly Button _go = new Button();
        readonly ComboBox _forms = new ComboBox();
        readonly ComboBox _spelling = new ComboBox();
        readonly ComboBox _distance = new ComboBox();
        readonly NumericUpDown _near = new NumericUpDown();
        readonly CheckBox _ordered = new CheckBox();
        readonly CheckBox _headings = new CheckBox();
        readonly Label _status = new Label();
        readonly RichTextBox _results = new RichTextBox();
        readonly Button _prev = new Button();
        readonly Button _next = new Button();
        readonly Label _counter = new Label();

        readonly JavaScriptSerializer _json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        readonly ThisAddIn _addin;
        readonly Word.Window _window;
        readonly Word.Document _doc;
        DocText _searched;                                  // הגרסה של המסמך שבה נמצאו התוצאות
        readonly Timer _stateTimer = new Timer { Interval = 500 };
        List<Hit> _hits = new List<Hit>();
        int _current = -1;
        bool _loading, _busy, _again;

        sealed class Hit
        {
            public int Para;
            public List<int[]> Ranges = new List<int[]>();
            public List<int[]> Marks = new List<int[]>();       // מיקומי המרקר הצהוב בתיבת התוצאות
            public int BlockStart, BlockLength;
        }

        internal SearchPane(ThisAddIn addin, Word.Window window, Word.Document doc)
        {
            _addin = addin;
            _window = window;
            _doc = doc;
            RightToLeft = RightToLeft.Yes;
            BackColor = Color.White;
            Font = new Font("Segoe UI", 9.75f);
            Padding = new Padding(8);
            BuildUi();
            LoadSettings();
            _stateTimer.Tick += (s, e) => ShowDocState();
            _stateTimer.Start();
            ShowDocState();
        }

        /// <summary>כל עוד אין תוצאות: האם המסמך כבר מוכן לחיפוש (ההכנה רצה ברקע). בלי גישה ל-Word.</summary>
        void ShowDocState()
        {
            if (_hits.Count > 0 || _lastQuery.Length > 0 || _busy || !Visible || _addin.Preparer == null) return;
            _status.ForeColor = Muted;
            _status.Text = _addin.Preparer.Status(_doc);
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) { _stateTimer.Stop(); _stateTimer.Dispose(); }
            base.Dispose(disposing);
        }

        internal void FocusSearch()
        {
            BeginInvoke(new Action(() => { _query.Focus(); _query.SelectAll(); }));
        }

        // ================================================================ ממשק
        void BuildUi()
        {
            var root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 6, RightToLeft = RightToLeft.Yes };
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            Controls.Add(root);

            // שורת החיפוש
            var row = new TableLayoutPanel { Dock = DockStyle.Top, ColumnCount = 2, AutoSize = true, RightToLeft = RightToLeft.Yes, Margin = new Padding(0, 0, 0, 6) };
            row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            row.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            _query.Dock = DockStyle.Fill;
            _query.Font = new Font("Segoe UI", 11f);
            _query.Margin = new Padding(0, 0, 6, 0);
            _query.KeyDown += QueryKeyDown;
            _go.Text = "חיפוש";
            _go.AutoSize = true;
            _go.FlatStyle = FlatStyle.Flat;
            _go.FlatAppearance.BorderColor = Accent;
            _go.BackColor = Accent;
            _go.ForeColor = Color.White;
            _go.Font = new Font("Segoe UI", 9.75f, FontStyle.Bold);
            _go.Cursor = Cursors.Hand;
            _go.Margin = new Padding(0);
            _go.Click += (s, e) => RunSearch();
            row.Controls.Add(_query, 0, 0);
            row.Controls.Add(_go, 1, 0);
            root.Controls.Add(row, 0, 0);

            // אפשרויות: מילים, כתיב
            var opts1 = Flow();
            opts1.Controls.Add(Caption("מילים:"));
            Combo(_forms, FormLabels, 130);
            opts1.Controls.Add(_forms);
            opts1.Controls.Add(Caption("כתיב:"));
            Combo(_spelling, SpellLabels, 110);
            opts1.Controls.Add(_spelling);
            root.Controls.Add(opts1, 0, 1);

            // מרחק, סדר, כותרות
            var opts2 = Flow();
            opts2.Controls.Add(Caption("מרחק:"));
            Combo(_distance, DistLabels, 130);
            opts2.Controls.Add(_distance);
            _near.Minimum = 1;
            _near.Maximum = 99;
            _near.Value = 3;
            _near.Width = 46;
            _near.Margin = new Padding(2, 3, 2, 3);
            opts2.Controls.Add(_near);
            _ordered.Text = "לפי הסדר";
            _ordered.AutoSize = true;
            _ordered.Checked = true;
            opts2.Controls.Add(_ordered);
            _headings.Text = "בכותרות בלבד";
            _headings.AutoSize = true;
            _headings.Font = new Font("Segoe UI", 9.75f, FontStyle.Bold);
            _headings.ForeColor = Accent;
            opts2.Controls.Add(_headings);
            root.Controls.Add(opts2, 0, 2);

            _status.AutoSize = false;
            _status.Dock = DockStyle.Top;
            _status.Height = 22;
            _status.ForeColor = Muted;
            _status.TextAlign = ContentAlignment.MiddleRight;
            _status.Text = "מקלידים מילה ולוחצים Enter. ניקוד, גרשיים ואותיות סופיות לא משנים.";
            root.Controls.Add(_status, 0, 3);

            _results.Dock = DockStyle.Fill;
            _results.ReadOnly = true;
            _results.BorderStyle = BorderStyle.None;
            _results.BackColor = Color.White;
            _results.RightToLeft = RightToLeft.Yes;
            _results.ScrollBars = RichTextBoxScrollBars.Vertical;
            _results.DetectUrls = false;
            _results.Cursor = Cursors.Hand;
            _results.ShortcutsEnabled = true;
            _results.MouseUp += ResultsMouseUp;
            _results.KeyDown += ResultsKeyDown;
            var frame = new Panel { Dock = DockStyle.Fill, Padding = new Padding(1), BackColor = Border, Margin = new Padding(0, 2, 0, 4) };
            var inner = new Panel { Dock = DockStyle.Fill, BackColor = Color.White, Padding = new Padding(6, 4, 6, 4) };
            inner.Controls.Add(_results);
            frame.Controls.Add(inner);
            root.Controls.Add(frame, 0, 4);

            // מעבר בין התוצאות: בממשק מימין לשמאל "הקודמת" מימין
            var nav = Flow();
            _prev.Text = "›";
            _next.Text = "‹";
            foreach (var b in new[] { _prev, _next })
            {
                b.Width = 34;
                b.FlatStyle = FlatStyle.Flat;
                b.FlatAppearance.BorderColor = Border;
                b.Font = new Font("Segoe UI", 11f, FontStyle.Bold);
                b.Cursor = Cursors.Hand;
            }
            _prev.Click += (s, e) => Go(_current - 1);
            _next.Click += (s, e) => Go(_current + 1);
            _counter.AutoSize = true;
            _counter.Margin = new Padding(6, 9, 6, 0);
            _counter.ForeColor = Text1;
            nav.Controls.Add(_prev);
            nav.Controls.Add(_counter);
            nav.Controls.Add(_next);
            var tips = Caption("Enter – הבאה · Shift+Enter – הקודמת");
            tips.Margin = new Padding(10, 9, 0, 0);
            nav.Controls.Add(tips);
            root.Controls.Add(nav, 0, 5);

            foreach (Control c in new Control[] { _forms, _spelling, _distance, _ordered, _headings })
            {
                if (c is ComboBox cb) cb.SelectedIndexChanged += (s, e) => OptionsChanged();
                if (c is CheckBox ch) ch.CheckedChanged += (s, e) => OptionsChanged();
            }
            _near.ValueChanged += (s, e) => { if (!_loading) { _distance.SelectedIndex = 1; OptionsChanged(); } };
            UpdateNav();
        }

        static FlowLayoutPanel Flow()
        {
            return new FlowLayoutPanel { Dock = DockStyle.Top, AutoSize = true, WrapContents = true, FlowDirection = FlowDirection.RightToLeft, Margin = new Padding(0, 0, 0, 2) };
        }

        static Label Caption(string text)
        {
            return new Label { Text = text, AutoSize = true, ForeColor = Muted, Margin = new Padding(2, 7, 2, 0) };
        }

        static void Combo(ComboBox c, string[] items, int width)
        {
            c.DropDownStyle = ComboBoxStyle.DropDownList;
            c.Items.AddRange(items);
            c.SelectedIndex = 0;
            c.Width = width;
            c.Margin = new Padding(2, 3, 8, 3);
        }

        // ================================================================ מקלדת
        void QueryKeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Enter)
            {
                e.SuppressKeyPress = true;
                if (_hits.Count > 0 && _lastQuery == _query.Text.Trim() && _lastKey == OptionsKey())
                    Go(e.Shift ? _current - 1 : _current + 1);      // Enter נוסף – לתוצאה הבאה, כמו ב-Word
                else
                    RunSearch();
            }
            else if (e.KeyCode == Keys.Down && _hits.Count > 0)
            {
                e.SuppressKeyPress = true;
                Go(_current + 1);
            }
            else if (e.KeyCode == Keys.Up && _hits.Count > 0)
            {
                e.SuppressKeyPress = true;
                Go(_current - 1);
            }
        }

        void ResultsKeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Down || e.KeyCode == Keys.Enter && !e.Shift) { e.SuppressKeyPress = true; Go(_current + 1); }
            else if (e.KeyCode == Keys.Up || e.KeyCode == Keys.Enter && e.Shift) { e.SuppressKeyPress = true; Go(_current - 1); }
        }

        protected override bool ProcessCmdKey(ref Message msg, Keys keyData)
        {
            if (keyData == Keys.F3) { Go(_current + 1); return true; }
            if (keyData == (Keys.F3 | Keys.Shift)) { Go(_current - 1); return true; }
            return base.ProcessCmdKey(ref msg, keyData);
        }

        // ================================================================ חיפוש
        string _lastQuery = "", _lastKey = "";

        string OptionsKey()
        {
            return string.Join("|", _forms.SelectedIndex, _spelling.SelectedIndex, _distance.SelectedIndex, _near.Value, _ordered.Checked, _headings.Checked);
        }

        void OptionsChanged()
        {
            if (_loading) return;
            _near.Enabled = _distance.SelectedIndex == 1;
            SaveSettings();
            if (_query.Text.Trim().Length > 0 && _lastQuery.Length > 0) RunSearch();
        }

        void RunSearch()
        {
            string q = _query.Text.Trim();
            if (q.Length == 0) return;
            if (_busy) { _again = true; return; }              // החיפוש הבא ירוץ כשהנוכחי יסתיים
            _busy = true;
            _again = false;
            string key = OptionsKey();
            Cursor = Cursors.AppStarting;
            _status.ForeColor = Muted;
            _status.Text = "מחפש…";
            var req = new Dictionary<string, object>
            {
                ["query"] = q,
                ["headings_only"] = _headings.Checked,
                ["limit"] = 400,
                ["options"] = new Dictionary<string, object>
                {
                    ["forms"] = FormKeys[_forms.SelectedIndex],
                    ["spelling"] = SpellKeys[_spelling.SelectedIndex],
                    ["distance"] = DistKeys[_distance.SelectedIndex],
                    ["near"] = (int)_near.Value,
                    ["ordered"] = _ordered.Checked,
                },
            };
            try
            {
                _addin.Preparer.Search(_doc, req, (reply, text, error) =>
                {
                    _busy = false;
                    Cursor = Cursors.Default;
                    if (IsDisposed) return;
                    if (_again) { RunSearch(); return; }
                    try
                    {
                        if (error != null) throw error;
                        if (!(reply.ContainsKey("ok") && (bool)reply["ok"]))
                            throw new Exception(reply.ContainsKey("error") ? Convert.ToString(reply["error"]) : "שגיאה בחיפוש");
                        _searched = text;
                        _lastQuery = q;
                        _lastKey = key;
                        ShowResults(reply);
                    }
                    catch (Exception ex) { SearchFailed(ex); }
                });
            }
            catch (Exception ex)
            {
                _busy = false;
                Cursor = Cursors.Default;
                SearchFailed(ex);
            }
        }

        void SearchFailed(Exception ex)
        {
            Log.Error("search", ex);
            _hits.Clear();
            _results.Clear();
            _status.ForeColor = Warn;
            _status.Text = "לא ניתן לחפש: " + ex.Message;
            UpdateNav();
        }

        void ShowResults(Dictionary<string, object> reply)
        {
            int total = Convert.ToInt32(reply["total"]);
            int headings = Convert.ToInt32(reply["headings"]);
            var hits = (IList)reply["hits"];
            _hits = new List<Hit>();
            _current = -1;
            _results.SuspendLayout();
            _results.Clear();
            _status.ForeColor = Text1;
            if (_headings.Checked && headings == 0)
            {
                _status.ForeColor = Warn;
                _status.Text = "אין במסמך כותרות (סגנונות 'כותרת 1' עד 'כותרת 9', או רמת חלוקה לרמות).";
            }
            else if (total == 0)
            {
                _status.Text = _headings.Checked ? $"לא נמצא בכותרות ({headings:N0} כותרות במסמך)" : "לא נמצאו תוצאות במסמך";
            }
            else
            {
                string what = total == 1 ? "תוצאה אחת" : $"{total:N0} תוצאות";
                _status.Text = _headings.Checked ? $"נמצאו {what} ב-{headings:N0} הכותרות" : $"נמצאו {what}";
                if (hits.Count < total) _status.Text += $" (מוצגות {hits.Count:N0})";
            }
            foreach (Dictionary<string, object> h in hits)
            {
                var hit = new Hit { Para = Convert.ToInt32(h["para"]) };
                foreach (IList r in (IList)h["ranges"])
                    hit.Ranges.Add(new[] { Convert.ToInt32(r[0]), Convert.ToInt32(r[1]) });
                hit.BlockStart = _results.TextLength;
                string heading = Convert.ToString(h["heading"]);
                if (heading.Length > 0)
                    Append("◂ " + Shorten(heading, 70) + "\n", Muted, Color.White, 8.5f, false);
                foreach (IList seg in (IList)h["snippet"])
                {
                    string text = Convert.ToString(seg[0]).Replace("\n", " ");
                    int kind = Convert.ToInt32(seg[1]);
                    if (kind == 3) text = " ¶ ";
                    if (kind == 1) hit.Marks.Add(new[] { _results.TextLength, text.Length });
                    Append(text, kind == 2 ? Muted : Text1, kind == 1 ? Marker : Color.White, 10f, false);
                }
                Append("\n", Text1, Color.White, 6f, false);
                hit.BlockLength = _results.TextLength - hit.BlockStart;
                Append("\n", Text1, Color.White, 5f, false);
                _hits.Add(hit);
            }
            _results.Select(0, 0);
            _results.ResumeLayout();
            UpdateNav();
            if (_hits.Count > 0) Go(0, focusDocument: false);
        }

        static string Shorten(string s, int max)
        {
            return s.Length <= max ? s : s.Substring(0, max - 1) + "…";
        }

        void Append(string text, Color fore, Color back, float size, bool bold)
        {
            int start = _results.TextLength;
            _results.AppendText(text);
            _results.Select(start, text.Length);
            _results.SelectionColor = fore;
            _results.SelectionBackColor = back;
            _results.SelectionFont = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular);
        }

        // ================================================================ מעבר לתוצאה במסמך
        void ResultsMouseUp(object sender, MouseEventArgs e)
        {
            int pos = _results.GetCharIndexFromPosition(e.Location);
            for (int i = 0; i < _hits.Count; i++)
            {
                var h = _hits[i];
                if (pos >= h.BlockStart && pos < h.BlockStart + h.BlockLength + 1) { Go(i); return; }
            }
        }

        void Go(int i, bool focusDocument = false)
        {
            if (_hits.Count == 0) return;
            if (i < 0) i = _hits.Count - 1;                     // מתחילים מחדש מהסוף / מההתחלה
            if (i >= _hits.Count) i = 0;
            Shade(_current, Color.White);
            _current = i;
            Shade(_current, AccentSoft);
            var hit = _hits[i];
            _results.Select(hit.BlockStart, 0);
            _results.ScrollToCaret();
            UpdateNav();
            try
            {
                Word.Range rng = _searched?.Locate(_doc, hit.Para, hit.Ranges);
                if (rng == null) throw new Exception("הטקסט השתנה מאז החיפוש – חפשו שוב");
                rng.Select();
                try { _window.ScrollIntoView(rng, true); } catch { }
            }
            catch (Exception ex)
            {
                Log.Error("select", ex);
                _status.ForeColor = Warn;
                _status.Text = "לא ניתן להגיע למקום במסמך: " + ex.Message;
            }
        }

        void Shade(int i, Color back)
        {
            if (i < 0 || i >= _hits.Count) return;
            var h = _hits[i];
            _results.Select(h.BlockStart, h.BlockLength);       // רקע לכל הקטע, ואז המרקר הצהוב בחזרה
            _results.SelectionBackColor = back;
            foreach (var m in h.Marks)
            {
                _results.Select(m[0], m[1]);
                _results.SelectionBackColor = Marker;
            }
            _results.Select(h.BlockStart, 0);
        }

        void UpdateNav()
        {
            _prev.Enabled = _next.Enabled = _hits.Count > 1;
            _counter.Text = _hits.Count == 0 ? "" : $"{_current + 1:N0} מתוך {_hits.Count:N0}";
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
                _forms.SelectedIndex = Clamp(s, "forms", 1);
                _spelling.SelectedIndex = Clamp(s, "spelling", 0);
                _distance.SelectedIndex = Clamp(s, "distance", 0);
                if (s.ContainsKey("near")) _near.Value = Math.Max(1, Math.Min(99, Convert.ToInt32(s["near"])));
                if (s.ContainsKey("ordered")) _ordered.Checked = Convert.ToBoolean(s["ordered"]);
                if (s.ContainsKey("headings")) _headings.Checked = Convert.ToBoolean(s["headings"]);
            }
            catch { }
            finally
            {
                if (_forms.SelectedIndex < 0) _forms.SelectedIndex = 1;
                _near.Enabled = _distance.SelectedIndex == 1;
                _loading = false;
            }
        }

        static int Clamp(Dictionary<string, object> s, string key, int fallback)
        {
            if (!s.ContainsKey(key)) return fallback;
            int v = Convert.ToInt32(s[key]);
            return v >= 0 && v <= 2 ? v : fallback;
        }

        void SaveSettings()
        {
            try
            {
                var s = new Dictionary<string, object>
                {
                    ["forms"] = _forms.SelectedIndex,
                    ["spelling"] = _spelling.SelectedIndex,
                    ["distance"] = _distance.SelectedIndex,
                    ["near"] = (int)_near.Value,
                    ["ordered"] = _ordered.Checked,
                    ["headings"] = _headings.Checked,
                };
                File.WriteAllText(SettingsPath, _json.Serialize(s), Encoding.UTF8);
            }
            catch { }
        }
    }
}
