// חלונית החיפוש – התצוגה בלבד (בלי Word), כדי שאפשר יהיה גם לצייר אותה בבנייה ולבדוק את העיצוב.
//
//   ┌─────────────────────────────────────────┐
//   │ [ חיפוש במסמך                    ✕ 🔍 ] │   שדה החיפוש (כמו ב-Word)
//   │ (מילים: עם אותיות שימוש ⌄) (מרחק: צמודות ⌄) │   אפשרויות (כמו בתוכנה)
//   │ 16 תוצאות · 3 מתוך 16             [⌄][⌃] │   כמו ב-Word
//   │ נמצא: הלכות 5 · ההולך 3 · להלך 1          │   הצורות שנמצאו (כשיש יותר מאחת)
//   │        כותרות 2      תוצאות 16           │   לשוניות (כמו ב-Word)
//   │─────────────────────────────────────────│
//   │ ① הלכות שבת ‹ פרק ב                      │   מספר + הכותרות שמעל
//   │ ההולך **בשבת** ברשות הרבים…              │   הקטע, ההתאמה מודגשת ומסומנת
//   │─────────────────────────────────────────│
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;

namespace HebDocSearch.WordAddin
{
    internal sealed class PaneView : UserControl
    {
        public static readonly string[] FormKeys = { "exact", "prefixes", "all" };
        static readonly string[] FormLabels = { "מדויק", "עם אותיות שימוש", "כל ההטיות" };
        static readonly string[] FormExamples = { "דרך", "בדרך · והדרך", "הלכה · הולכים · ללכת" };
        public static readonly string[] SpellKeys = { "none", "vy", "all" };
        static readonly string[] SpellLabels = { "כפי שהוקלד", "מלא וחסר (ו׳ י׳)", "כל אהו״י" };
        static readonly string[] SpellShort = { "", "מלא וחסר", "כל אהו״י" };
        static readonly string[] SpellExamples = { "שמרה", "שמירה · שומרה", "מילתא · מילתה" };
        public static readonly string[] DistKeys = { "adjacent", "near", "paragraph" };
        static readonly int[] NearChoices = { 1, 2, 3, 5, 10 };

        public readonly SearchBox Search = new SearchBox();
        readonly Chip _words = new Chip { Key = "מילים:" };
        readonly Chip _dist = new Chip { Key = "מרחק:" };
        readonly IconButton _next = new IconButton { Glyph = 'd', Tip = "התוצאה הבאה (Enter / F3)" };
        readonly IconButton _prev = new IconButton { Glyph = 'u', Tip = "התוצאה הקודמת (Shift+Enter / Shift+F3)" };
        readonly TabStrip _tabs = new TabStrip();
        public readonly ResultList List = new ResultList();
        readonly ToolTip _tip = new ToolTip();
        readonly Timer _searchingDelay = new Timer { Interval = 250 };

        Theme _t = Theme.Light;
        Metrics _m;
        Bitmap _logo;
        Rectangle _countRect, _formsRect;
        string _countMain = "", _countSub = "", _forms = "";
        bool _countWarn, _navVisible;

        // ----- האפשרויות -----
        public int Forms = 1, Spelling = 0, Distance = 0, Near = 3;
        public bool Ordered = true;
        public bool HeadingsOnly
        {
            get => _tabs.Selected == 1;
            set => _tabs.Selected = value ? 1 : 0;
        }

        public event Action<bool> SubmitRequested;      // shift
        public event Action<int> NavigateRequested;     // +1 / -1
        public event Action OptionsChanged;             // מילים / מרחק
        public event Action ModeChanged;                // תוצאות / כותרות
        public event Action<int> ResultActivated;
        public event Action QueryCleared;

        public PaneView()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint
                     | ControlStyles.ResizeRedraw, true);
            RightToLeft = RightToLeft.No;          // הכיוון מטופל בציור ובפריסה (מימין לשמאל)
            Controls.AddRange(new Control[] { Search, _words, _dist, _next, _prev, _tabs, List });
            Search.Submit += s => SubmitRequested?.Invoke(s);
            Search.Navigate += d => NavigateRequested?.Invoke(d);
            Search.Cleared += () => QueryCleared?.Invoke();
            Search.Box.TextChanged += (s, e) => UpdateDistanceDim();
            _words.Click += (s, e) => ShowWordsMenu();
            _dist.Click += (s, e) => ShowDistanceMenu();
            _next.Click += (s, e) => NavigateRequested?.Invoke(1);
            _prev.Click += (s, e) => NavigateRequested?.Invoke(-1);
            _tabs.SelectedChanged += () => ModeChanged?.Invoke();
            List.ItemActivated += i => ResultActivated?.Invoke(i);
            _searchingDelay.Tick += (s, e) =>
            {
                _searchingDelay.Stop();
                SetCount("מחפש…", "", false);
            };
            _tip.SetToolTip(_next, _next.Tip);
            _tip.SetToolTip(_prev, _prev.Tip);
            _tip.SetToolTip(_words, "איך למצוא כל מילה: צורות המילה וכתיב");
            _tip.SetToolTip(_dist, "איך המילים קשורות זו לזו: מרחק וסדר (כשמחפשים שתי מילים או יותר)");
            SetNavVisible(false, 0);
            RefreshChips();
        }

        public string Query
        {
            get => Search.Box.Text.Trim();
            set => Search.Box.Text = value ?? "";
        }

        public void FocusSearch()
        {
            Search.Box.Focus();
            Search.Box.SelectAll();
        }

        // ================================================================ ערכת נושא ומידות
        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            ApplyTheme(_t, true);
        }

        protected override void OnDpiChangedAfterParent(EventArgs e)
        {
            base.OnDpiChangedAfterParent(e);
            ApplyTheme(_t, true);
        }

        public Theme CurrentTheme => _t;

        public void ApplyTheme(Theme t, bool newMetrics = false)
        {
            if (t == null) return;
            if (!newMetrics && t == _t && _m != null) return;
            _t = t;
            if (!IsHandleCreated) return;                  // יוחל כשהחלון ייווצר (OnHandleCreated)
            if (newMetrics || _m == null)
            {
                var old = _m;
                _m = new Metrics(Metrics.ScaleOf(this));
                old?.Dispose();
            }
            BackColor = t.PaneBg;
            foreach (Control c in Controls)
                if (c is ThemedControl tc) tc.ApplyTheme(t, _m);
            List.ApplyTheme(t, _m);
            PerformLayout();
            Invalidate();
        }

        // ================================================================ פריסה
        protected override void OnLayout(LayoutEventArgs e)
        {
            base.OnLayout(e);
            if (_m == null) return;
            int pad = _m.S(10), w = ClientSize.Width, y = _m.S(10);
            Search.SetBounds(pad, y, Math.Max(10, w - 2 * pad), Search.PreferredHeight);
            y = Search.Bottom + _m.S(8);

            // שבבים – מימין לשמאל, וגולשים לשורה נוספת כשאין מקום
            int chipH = _m.S(26), x = w - pad, rowTop = y;
            foreach (var chip in new[] { _words, _dist })
            {
                int cw = Math.Min(chip.PreferredWidth, w - 2 * pad);
                if (x - cw < pad && x != w - pad)
                {
                    rowTop += chipH + _m.S(6);
                    x = w - pad;
                }
                chip.SetBounds(x - cw, rowTop, cw, chipH);
                x -= cw + _m.S(6);
            }
            y = rowTop + chipH + _m.S(10);

            // שורת המספר והמעבר בין התוצאות (כמו ב-Word: ⌄ ⌃ משמאל)
            int rowH = _m.S(26), b = _m.S(24);
            _next.SetBounds(pad, y + (rowH - b) / 2, b, b);
            _prev.SetBounds(pad + b + _m.S(4), y + (rowH - b) / 2, b, b);
            int left = _navVisible ? _prev.Right + _m.S(8) : pad;
            _countRect = new Rectangle(left, y, w - pad - left, rowH);
            y += rowH;
            if (_forms.Length > 0)
            {
                _formsRect = new Rectangle(pad, y, w - 2 * pad, _m.S(20));
                y += _m.S(20);
            }
            else _formsRect = Rectangle.Empty;
            y += _m.S(6);

            _tabs.SetBounds(pad, y, w - 2 * pad, _m.S(30));
            y = _tabs.Bottom + _m.S(4);
            List.SetBounds(0, y, w, Math.Max(0, ClientSize.Height - y));
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(_t.PaneBg);
            if (_m == null) return;
            // "16 תוצאות" גדול, ואחריו "· 3 מתוך 16" עמום
            int mw = Draw.Width(_countMain, _m.Count);
            int x = _countRect.Right;
            if (_countMain.Length > 0)
            {
                int w = Math.Min(mw, _countRect.Width);
                Draw.Text(g, _countMain, _m.Count, new Rectangle(x - w, _countRect.Y, w + 1, _countRect.Height), _countWarn ? _t.Warn : _t.Text);
                x -= w;
            }
            if (_countSub.Length > 0 && x - _countRect.Left > _m.S(30))
            {
                string sub = (_countMain.Length > 0 ? "  ·  " : "") + _countSub;
                Draw.Text(g, sub, _m.Body, new Rectangle(_countRect.Left, _countRect.Y, x - _countRect.Left, _countRect.Height), _t.TextDim);
            }
            if (!_formsRect.IsEmpty)
                Draw.Text(g, _forms, _m.Caption, _formsRect, _t.TextFaint);
        }

        // ================================================================ מצבים
        void SetCount(string main, string sub, bool warn)
        {
            _countMain = main ?? "";
            _countSub = sub ?? "";
            _countWarn = warn;
            Invalidate(_countRect);
        }

        void SetForms(string text)
        {
            bool changed = (_forms.Length > 0) != (text.Length > 0);
            _forms = text;
            if (changed) PerformLayout();
            Invalidate();
        }

        void SetNavVisible(bool visible, int count)
        {
            _next.Visible = _prev.Visible = visible;
            _next.Enabled = _prev.Enabled = count > 1;
            if (visible != _navVisible)
            {
                _navVisible = visible;
                PerformLayout();
            }
        }

        /// <summary>לפני חיפוש: מצב המסמך בשורת המספר, ובמקום התוצאות – הסבר קצר.</summary>
        public void ShowIdle(string docStatus)
        {
            _searchingDelay.Stop();
            SetCount("", docStatus, false);
            SetForms("");
            SetNavVisible(false, 0);
            _tabs.SetCount(0, null);
            _tabs.SetCount(1, null);
            List.SetItems(null);
            if (_logo == null) _logo = Assets.Logo(128);   // מוקטן בציור לגודל שמתאים למסך
            List.SetMessage(_logo, "חיפוש עברי במסמך", new[]
            {
                "מקלידים מילה או ביטוי – התוצאות מופיעות תוך כדי הקלדה.",
                "ניקוד, גרשיים ואותיות סופיות לא משנים.",
                "",
                "ביטוי מדויק – במירכאות: \"איסור ייחוד\".",
                "מעבר בין התוצאות: Enter, או החיצים למעלה ולמטה.",
            }, false);
        }

        /// <summary>מצב המסמך כשאין חיפוש פעיל (מתעדכן ברקע: "מכין…" → "מוכן").</summary>
        public void SetDocStatus(string docStatus)
        {
            if (List.Count == 0 && _countMain.Length == 0 && !_searchingDelay.Enabled) SetCount("", docStatus, false);
        }

        public void BeginSearch(bool immediate)
        {
            _searchingDelay.Stop();
            if (immediate) SetCount("מחפש…", "", false);
            else _searchingDelay.Start();                  // חיפוש מהיר לא מהבהב "מחפש…"
        }

        public void ShowResults(List<ResultItem> items, int total, string forms)
        {
            _searchingDelay.Stop();
            List.SetItems(items);
            List.SetMessage(null, "", null, false);
            SetForms(forms ?? "");
            _tabs.SetCount(HeadingsOnly ? 1 : 0, total);
            SetNavVisible(true, items.Count);
            string main = Words.Results(total);
            string sub = items.Count < total ? $"מוצגות {items.Count:N0} הראשונות" : "";
            SetCount(main, sub, false);
        }

        public void ShowMessage(string count, string title, string[] lines, bool warn)
        {
            _searchingDelay.Stop();
            List.SetItems(null);
            List.SetMessage(null, title, lines, warn);
            SetForms("");
            SetNavVisible(false, 0);
            SetCount(count, "", warn);
        }

        public void SetTabCount(bool headings, int? count)
        {
            _tabs.SetCount(headings ? 1 : 0, count);
        }

        /// <summary>התוצאה הנוכחית: מסומנת ברשימה, ו"3 מתוך 16" בשורת המספר.</summary>
        public void SetCurrent(int index, int total)
        {
            List.Select(index);
            if (List.Count > 0 && index >= 0)
                SetCount(_countMain, $"{index + 1:N0} מתוך {List.Count:N0}", false);
        }

        public void SetNote(string note, bool warn)
        {
            SetCount(_countMain, note, warn && _countMain.Length == 0);
        }

        // ================================================================ אפשרויות
        void RefreshChips()
        {
            string words = FormLabels[Forms];
            if (Spelling > 0) words += " · " + SpellShort[Spelling];
            _words.Value = words;
            _words.On = Forms != 1 || Spelling != 0;
            string dist = Distance == 0 ? "צמודות" : Distance == 1 ? "עד " + NearText(Near) : "באותה פסקה";
            if (!Ordered) dist += ", בכל סדר";
            _dist.Value = dist;
            _dist.On = Distance != 0 || !Ordered;
            UpdateDistanceDim();
            PerformLayout();
        }

        static string NearText(int n) => n == 1 ? "מילה אחת" : n + " מילים";

        void UpdateDistanceDim()
        {
            string q = Search.Box.Text.Trim();
            bool quoted = q.StartsWith("\"") && q.EndsWith("\"") && q.Length > 1;
            int words = q.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries).Length;
            _dist.Dim = words < 2 || quoted;
        }

        public void SetOptions(int forms, int spelling, int distance, int near, bool ordered, bool headings)
        {
            Forms = Clamp(forms, 2, 1);
            Spelling = Clamp(spelling, 2, 0);
            Distance = Clamp(distance, 2, 0);
            Near = Math.Max(1, Math.Min(99, near));
            Ordered = ordered;
            HeadingsOnly = headings;
            RefreshChips();
        }

        static int Clamp(int v, int max, int fallback) => v >= 0 && v <= max ? v : fallback;

        ContextMenuStrip NewMenu()
        {
            var menu = new ContextMenuStrip
            {
                RightToLeft = RightToLeft.Yes,
                Renderer = new MenuRenderer(_t),
                ShowImageMargin = false,
                ShowCheckMargin = true,
                Font = _m.Body,
                BackColor = _t.MenuBg,
                ForeColor = _t.MenuText,
            };
            return menu;
        }

        ToolStripMenuItem Header(string text)
        {
            return new ToolStripMenuItem(text) { Enabled = false, Font = _m.CaptionBold };
        }

        ToolStripMenuItem Choice(string text, string example, bool chosen, Action pick)
        {
            var item = new ToolStripMenuItem(text) { Checked = chosen };
            if (!string.IsNullOrEmpty(example))
            {
                item.ShortcutKeyDisplayString = example;
                item.ShowShortcutKeys = true;
            }
            item.Click += (s, e) =>
            {
                pick();
                RefreshChips();
                OptionsChanged?.Invoke();
            };
            return item;
        }

        void Popup(Chip chip, ContextMenuStrip menu)
        {
            _previewMenu = menu;
            chip.Open = true;
            menu.Closed += (s, e) =>
            {
                chip.Open = false;
                BeginInvoke(new Action(menu.Dispose));
            };
            menu.Show(chip, new Point(chip.Width, chip.Height + _m.S(2)), ToolStripDropDownDirection.BelowLeft);
        }

        void ShowWordsMenu()
        {
            var menu = NewMenu();
            menu.Items.Add(Header("צורות המילה"));
            for (int i = 0; i < FormLabels.Length; i++)
            {
                int k = i;
                menu.Items.Add(Choice(FormLabels[i], FormExamples[i], Forms == i, () => Forms = k));
            }
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(Header("כתיב"));
            for (int i = 0; i < SpellLabels.Length; i++)
            {
                int k = i;
                menu.Items.Add(Choice(SpellLabels[i], SpellExamples[i], Spelling == i, () => Spelling = k));
            }
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(new ToolStripMenuItem("ניקוד, גרשיים ואותיות סופיות אף פעם לא משנים") { Enabled = false, Font = _m.Caption });
            Popup(_words, menu);
        }

        void ShowDistanceMenu()
        {
            var menu = NewMenu();
            menu.Items.Add(Header("מרחק בין המילים"));
            menu.Items.Add(Choice("צמודות", "איסור ייחוד", Distance == 0, () => Distance = 0));
            var nears = new List<int>(NearChoices);
            if (!nears.Contains(Near)) { nears.Add(Near); nears.Sort(); }
            foreach (int n in nears)
            {
                int k = n;
                menu.Items.Add(Choice("עד " + NearText(n) + " ביניהן", null, Distance == 1 && Near == n, () => { Distance = 1; Near = k; }));
            }
            menu.Items.Add(Choice("באותה פסקה", null, Distance == 2, () => Distance = 2));
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(Header("סדר המילים"));
            menu.Items.Add(Choice("לפי הסדר שהוקלד", null, Ordered, () => Ordered = true));
            menu.Items.Add(Choice("בכל סדר", null, !Ordered, () => Ordered = false));
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(new ToolStripMenuItem("חל כשמחפשים שתי מילים או יותר; במירכאות – תמיד ביטוי מדויק") { Enabled = false, Font = _m.Caption });
            Popup(_dist, menu);
        }

        // ----- לתצוגה המקדימה בבנייה -----
        ContextMenuStrip _previewMenu;
        internal void OpenMenuForPreview()
        {
            ShowWordsMenu();
        }

        internal void CloseMenuForPreview()
        {
            _previewMenu?.Close();
        }

        // ================================================================ מקלדת
        protected override bool ProcessCmdKey(ref Message msg, Keys keyData)
        {
            if (keyData == Keys.F3) { NavigateRequested?.Invoke(1); return true; }
            if (keyData == (Keys.F3 | Keys.Shift)) { NavigateRequested?.Invoke(-1); return true; }
            return base.ProcessCmdKey(ref msg, keyData);
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                _searchingDelay.Dispose();
                _tip.Dispose();
                _m?.Dispose();
            }
            base.Dispose(disposing);
        }
    }
}
