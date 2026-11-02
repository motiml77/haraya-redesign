// הפקדים הקטנים של החלונית, מצוירים בקוד לפי ערכת הנושא של Office:
//   SearchBox – שדה החיפוש (כמו ב-Word: שדה עם × לניקוי, ולחצן חיפוש)
//   Chip      – שבב של אפשרות: "מילים: עם אותיות שימוש ⌄" (כמו בתוכנה)
//   IconButton – לחצני ⌃ ⌄ למעבר בין התוצאות (כמו ב-Word)
//   TabStrip  – הלשוניות "תוצאות | כותרות" (כמו "כותרות | עמודים | תוצאות" של Word)
using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace HebDocSearch.WordAddin
{
    internal abstract class ThemedControl : Control
    {
        protected Theme T = Theme.Light;
        protected Metrics M;
        protected bool Hover;

        protected ThemedControl()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint
                     | ControlStyles.ResizeRedraw | ControlStyles.SupportsTransparentBackColor, true);
        }

        public virtual void ApplyTheme(Theme t, Metrics m)
        {
            T = t;
            M = m;
            BackColor = t.PaneBg;
            Invalidate();
        }

        protected override void OnMouseEnter(EventArgs e) { base.OnMouseEnter(e); Hover = true; Invalidate(); }
        protected override void OnMouseLeave(EventArgs e) { base.OnMouseLeave(e); Hover = false; Invalidate(); }
        protected override void OnEnabledChanged(EventArgs e) { base.OnEnabledChanged(e); Invalidate(); }
    }

    // ==================================================================== שדה החיפוש
    internal sealed class SearchBox : ThemedControl
    {
        public readonly TextBox Box = new TextBox();
        Rectangle _searchBtn, _clearBtn;
        int _hoverBtn;              // 1 חיפוש, 2 ניקוי

        public event Action<bool> Submit;          // Enter – חיפוש
        public event Action<int> Navigate;         // חץ למטה – מעבר לרשימה
        public event Action Cleared;

        const string Cue = "חיפוש במסמך";

        public SearchBox()
        {
            Box.BorderStyle = BorderStyle.None;
            Box.RightToLeft = RightToLeft.Yes;
            Box.TextChanged += (s, e) => Invalidate();
            Box.GotFocus += (s, e) => Invalidate();
            Box.LostFocus += (s, e) => Invalidate();
            Box.KeyDown += BoxKeyDown;
            Box.MouseEnter += (s, e) => { Hover = true; Invalidate(); };
            Box.MouseLeave += (s, e) => { Hover = ClientRectangle.Contains(PointToClient(MousePosition)); Invalidate(); };
            Controls.Add(Box);
            Cursor = Cursors.IBeam;
        }

        public override void ApplyTheme(Theme t, Metrics m)
        {
            base.ApplyTheme(t, m);
            Box.BackColor = t.FieldBg;
            Box.ForeColor = t.FieldText;
            Box.Font = m.Input;
            SetCue();
            PerformLayout();
        }

        public int PreferredHeight => M == null ? 34 : M.S(34);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, string lParam);

        void SetCue()
        {
            if (Box.IsHandleCreated) SendMessage(Box.Handle, 0x1501 /* EM_SETCUEBANNER */, (IntPtr)1, Cue);
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            Box.HandleCreated += (s, a) => SetCue();
            SetCue();
        }

        protected override void OnLayout(LayoutEventArgs e)
        {
            base.OnLayout(e);
            if (M == null) return;
            int inset = M.S(3), b = Height - 2 * inset;
            _searchBtn = new Rectangle(inset, inset, b, b);
            _clearBtn = new Rectangle(_searchBtn.Right, inset, b, b);
            int left = _clearBtn.Right + M.S(2), right = Width - M.S(10);
            Box.SetBounds(left, (Height - Box.PreferredHeight) / 2 + M.S(1), Math.Max(10, right - left), Box.PreferredHeight);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(T.PaneBg);
            if (M == null) return;
            bool focus = Box.Focused;
            var r = new Rectangle(0, 0, Width, Height);
            Draw.Box(g, r, M.S(3), Hover && !focus ? T.FieldHover : T.FieldBg,
                     focus ? T.FieldFocus : T.FieldBorder, focus ? Math.Max(1.5f, M.Scale * 1.5f) : 1f);
            if (_hoverBtn == 1)
                Draw.Fill(g, Rectangle.Inflate(_searchBtn, -M.S(2), -M.S(2)), M.S(3), Draw.Mix(T.FieldBg, T.FieldBorder, 0.45f));
            Draw.Magnifier(g, Rectangle.Inflate(_searchBtn, -M.S(7), -M.S(7)), T.FieldIcon, Math.Max(1.4f, M.Scale * 1.6f));
            if (Box.TextLength > 0)
            {
                if (_hoverBtn == 2)
                    Draw.Fill(g, Rectangle.Inflate(_clearBtn, -M.S(2), -M.S(2)), M.S(3), Draw.Mix(T.FieldBg, T.FieldBorder, 0.45f));
                Draw.Cross(g, Rectangle.Inflate(_clearBtn, -M.S(6), -M.S(6)), T.FieldIcon, Math.Max(1.3f, M.Scale * 1.4f));
            }
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            int h = _searchBtn.Contains(e.Location) ? 1 : Box.TextLength > 0 && _clearBtn.Contains(e.Location) ? 2 : 0;
            if (h != _hoverBtn) { _hoverBtn = h; Invalidate(); }
            Cursor = h != 0 ? Cursors.Hand : Cursors.IBeam;
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            _hoverBtn = 0;
            base.OnMouseLeave(e);
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            if (_searchBtn.Contains(e.Location)) Submit?.Invoke(false);
            else if (Box.TextLength > 0 && _clearBtn.Contains(e.Location))
            {
                Box.Clear();
                Cleared?.Invoke();
            }
            Box.Focus();
        }

        void BoxKeyDown(object sender, KeyEventArgs e)
        {
            switch (e.KeyCode)
            {
                case Keys.Enter:
                    e.SuppressKeyPress = true;
                    Submit?.Invoke(e.Shift);
                    break;
                case Keys.Down:
                    e.SuppressKeyPress = true;
                    Navigate?.Invoke(1);
                    break;
                case Keys.Up:
                    e.SuppressKeyPress = true;
                    Navigate?.Invoke(-1);
                    break;
                case Keys.Escape:
                    if (Box.TextLength > 0)
                    {
                        e.SuppressKeyPress = true;
                        Box.Clear();
                        Cleared?.Invoke();
                    }
                    break;
            }
        }
    }

    // ==================================================================== שבב אפשרות
    internal sealed class Chip : ThemedControl
    {
        string _key = "", _value = "";
        bool _on, _dim, _open;

        public Chip()
        {
            Cursor = Cursors.Hand;
            TabStop = true;
        }

        public string Key { get => _key; set { _key = value ?? ""; Invalidate(); } }
        public string Value { get => _value; set { _value = value ?? ""; Invalidate(); } }
        public bool On { get => _on; set { _on = value; Invalidate(); } }
        public bool Dim { get => _dim; set { _dim = value; Invalidate(); } }
        public bool Open { get => _open; set { _open = value; Invalidate(); } }

        public int PreferredWidth
        {
            get
            {
                if (M == null) return 100;
                return M.S(10) + Draw.Width(_key, M.Body) + M.S(4) + Draw.Width(_value, M.BodyBold) + M.S(6) + M.S(12) + M.S(6);
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(T.PaneBg);
            if (M == null) return;
            Color bg = _on ? T.ChipOnBg : T.PaneBg, border = _on ? T.ChipOnBorder : T.ChipBorder;
            Color key = T.ChipKey, val = _on ? T.ChipOnText : T.ChipText;
            if (Hover || _open) bg = _on ? Draw.Mix(T.ChipOnBg, T.ChipOnBorder, 0.25f) : T.ChipHover;
            if (_open || Focused) border = T.Accent;
            if (_dim && !_open && !Hover)
            {
                key = Draw.Mix(key, T.PaneBg, 0.45f);
                val = Draw.Mix(val, T.PaneBg, 0.45f);
                border = Draw.Mix(border, T.PaneBg, 0.45f);
            }
            Draw.Box(g, new Rectangle(0, 0, Width, Height), M.S(6), bg, border, 1f);
            int x = Width - M.S(10);
            int kw = Draw.Width(_key, M.Body);
            Draw.Text(g, _key, M.Body, new Rectangle(x - kw, 0, kw + 1, Height), key);
            x -= kw + M.S(4);
            int arrow = M.S(12);
            int vw = Math.Min(Draw.Width(_value, M.BodyBold), x - M.S(6) - arrow - M.S(4));
            Draw.Text(g, _value, M.BodyBold, new Rectangle(x - vw, 0, vw + 1, Height), val);
            Draw.Chevron(g, new RectangleF(M.S(6), (Height - arrow) / 2f, arrow, arrow), val, Math.Max(1.3f, M.Scale * 1.4f), 'd');
        }

        protected override void OnGotFocus(EventArgs e) { base.OnGotFocus(e); Invalidate(); }
        protected override void OnLostFocus(EventArgs e) { base.OnLostFocus(e); Invalidate(); }

        protected override bool IsInputKey(Keys keyData)
        {
            return (keyData & Keys.KeyCode) == Keys.Enter || (keyData & Keys.KeyCode) == Keys.Space || base.IsInputKey(keyData);
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            base.OnKeyDown(e);
            if (e.KeyCode == Keys.Enter || e.KeyCode == Keys.Space || e.KeyCode == Keys.Down)
            {
                e.Handled = e.SuppressKeyPress = true;
                OnClick(EventArgs.Empty);
            }
        }
    }

    // ==================================================================== לחצן ⌃ / ⌄
    internal sealed class IconButton : ThemedControl
    {
        public char Glyph = 'd';
        public string Tip = "";

        public IconButton()
        {
            Cursor = Cursors.Hand;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(T.PaneBg);
            if (M == null) return;
            Color bg = !Enabled ? T.BtnBg : Hover ? T.BtnHover : T.BtnBg;
            Draw.Box(g, new Rectangle(0, 0, Width, Height), M.S(2), bg, T.BtnBorder, 1f);
            float s = Width * 0.62f;
            Draw.Chevron(g, new RectangleF((Width - s) / 2, (Height - s) / 2, s, s), Enabled ? T.BtnGlyph : T.BtnGlyphOff,
                         Math.Max(1.4f, M.Scale * 1.5f), Glyph);
        }
    }

    // ==================================================================== לשוניות
    internal sealed class TabStrip : ThemedControl
    {
        public readonly string[] Labels = { "תוצאות", "חיפוש בכותרות" };
        public readonly int?[] Counts = { null, null };
        public readonly string[] Tips = { "חיפוש בכל הטקסט של המסמך", "חיפוש רק בכותרות (סגנונות 'כותרת 1' עד 'כותרת 9')" };
        int _selected, _hoverTab = -1;
        Rectangle[] _rects = new Rectangle[2];
        readonly ToolTip _tip = new ToolTip();

        public event Action SelectedChanged;

        public TabStrip()
        {
            Cursor = Cursors.Hand;
        }

        public int Selected
        {
            get => _selected;
            set
            {
                if (value == _selected) return;
                _selected = value;
                Invalidate();
            }
        }

        public void SetCount(int tab, int? count)
        {
            Counts[tab] = count;
            Invalidate();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(T.PaneBg);
            if (M == null) return;
            int x = Width - M.S(2);
            int underline = Math.Max(2, M.S(2.5f));
            for (int i = 0; i < Labels.Length; i++)
            {
                bool sel = i == _selected;
                var font = sel ? M.BodyBold : M.Body;
                int lw = Draw.Width(Labels[i], M.BodyBold);       // רוחב קבוע, כדי שהלשונית לא תזוז כשנבחרת
                string count = Counts[i].HasValue ? Counts[i].Value.ToString("N0") : null;
                int cw = count == null ? 0 : Math.Max(M.S(18), Draw.Width(count, M.Caption, false) + M.S(10));
                int w = lw + (count == null ? 0 : M.S(6) + cw);
                var tab = new Rectangle(x - w, 0, w, Height);
                _rects[i] = Rectangle.Inflate(tab, M.S(8), 0);
                int textH = Height - underline - M.S(4);
                Color fg = sel ? (T.Dark ? Color.White : T.Text) : (i == _hoverTab ? T.Text : T.TextDim);
                Draw.Text(g, Labels[i], font, new Rectangle(tab.Right - lw, 0, lw, textH), fg, 'c');
                if (count != null)
                {
                    int bh = Draw.Height(M.Caption) + M.S(2);
                    var b = new Rectangle(tab.Left, (textH - bh) / 2, cw, bh);
                    Draw.Fill(g, b, bh / 2f, sel ? T.Accent : T.BadgeBg);
                    Draw.Text(g, count, M.Caption, b, sel ? T.OnAccent : T.BadgeText, 'c', false);
                }
                if (sel)
                    Draw.Fill(g, new Rectangle(tab.Left - M.S(2), Height - underline - M.S(1), tab.Width + M.S(4), underline), underline / 2f, T.Accent);
                x = tab.Left - M.S(24);
            }
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            int h = Array.FindIndex(_rects, r => r.Contains(e.Location));
            if (h != _hoverTab)
            {
                _hoverTab = h;
                _tip.SetToolTip(this, h >= 0 ? Tips[h] : "");
                Invalidate();
            }
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            _hoverTab = -1;
            base.OnMouseLeave(e);
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            int h = Array.FindIndex(_rects, r => r.Contains(e.Location));
            if (h >= 0 && h != _selected)
            {
                Selected = h;
                SelectedChanged?.Invoke();
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) _tip.Dispose();
            base.Dispose(disposing);
        }
    }

    // ==================================================================== תפריטים לפי ערכת הנושא
    internal sealed class MenuRenderer : ToolStripProfessionalRenderer
    {
        readonly Theme _t;

        public MenuRenderer(Theme t) : base(new MenuColors(t))
        {
            _t = t;
            RoundedEdges = false;
        }

        protected override void OnRenderItemText(ToolStripItemTextRenderEventArgs e)
        {
            var item = e.Item as ToolStripMenuItem;
            if (item != null && !string.IsNullOrEmpty(item.ShortcutKeyDisplayString) && e.Text == item.ShortcutKeyDisplayString)
                e.TextColor = _t.MenuDim;                   // דוגמאות בצד השני של הפריט
            else
                e.TextColor = e.Item.Enabled ? _t.MenuText : _t.MenuDim;
            base.OnRenderItemText(e);
        }

        protected override void OnRenderItemCheck(ToolStripItemImageRenderEventArgs e)
        {
            var r = e.ImageRectangle;
            r.Inflate(-1, -1);
            Draw.Check(e.Graphics, r, _t.Accent, Math.Max(1.6f, r.Width / 8f));
        }

        protected override void OnRenderMenuItemBackground(ToolStripItemRenderEventArgs e)
        {
            if (!e.Item.Selected || !e.Item.Enabled) return;
            var r = new Rectangle(2, 0, e.Item.Width - 4, e.Item.Height);
            Draw.Fill(e.Graphics, r, 3, _t.MenuSel);
        }

        sealed class MenuColors : ProfessionalColorTable
        {
            readonly Theme t;
            public MenuColors(Theme theme) { t = theme; UseSystemColors = false; }
            public override Color ToolStripDropDownBackground => t.MenuBg;
            public override Color ImageMarginGradientBegin => t.MenuBg;
            public override Color ImageMarginGradientMiddle => t.MenuBg;
            public override Color ImageMarginGradientEnd => t.MenuBg;
            public override Color MenuBorder => t.MenuBorder;
            public override Color MenuItemBorder => t.MenuSel;
            public override Color MenuItemSelected => t.MenuSel;
            public override Color SeparatorDark => t.MenuBorder;
            public override Color SeparatorLight => t.MenuBg;
            public override Color CheckBackground => t.MenuBg;
            public override Color CheckSelectedBackground => t.MenuSel;
            public override Color CheckPressedBackground => t.MenuSel;
        }
    }
}

namespace HebDocSearch.WordAddin
{
    // ==================================================================== בורר המרחק
    /// <summary>חלונית קטנה ל"מרחק": צמודות / עד [− N +] מילים ביניהן / באותה פסקה, וסדר המילים.
    /// כל שינוי חל מיד; החלונית נשארת פתוחה עד לחיצה מחוץ לה (או Esc / Enter).</summary>
    internal sealed class DistancePanel : Control
    {
        readonly Theme _t;
        readonly Metrics _m;
        public int Distance, Near;
        public bool Ordered;
        public event Action Changed;
        public event Action CloseRequested;

        Rectangle[] _rows = new Rectangle[5];      // 0 צמודות, 1 עד N, 2 באותה פסקה, 3 לפי הסדר, 4 בכל סדר
        Rectangle _minus, _plus, _number;
        int _hoverRow = -1, _hoverBtn;
        int _rowH, _headH, _w;

        public DistancePanel(Theme t, Metrics m, int distance, int near, bool ordered)
        {
            _t = t;
            _m = m;
            Distance = distance;
            Near = Math.Max(1, Math.Min(99, near));
            Ordered = ordered;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint
                     | ControlStyles.ResizeRedraw | ControlStyles.Selectable, true);
            _rowH = m.S(30);
            _headH = m.S(26);
            _w = Math.Max(m.S(250), Draw.Width("עד  מילים ביניהן", m.Body) + m.S(150));
            int h = m.S(6) + _headH + 3 * _rowH + m.S(9) + _headH + 2 * _rowH + m.S(8);
            Size = new Size(_w, h);
            int y = m.S(6) + _headH;
            for (int i = 0; i < 3; i++) { _rows[i] = new Rectangle(m.S(4), y, _w - m.S(8), _rowH); y += _rowH; }
            y += m.S(9) + _headH;
            for (int i = 3; i < 5; i++) { _rows[i] = new Rectangle(m.S(4), y, _w - m.S(8), _rowH); y += _rowH; }
            BackColor = t.MenuBg;
        }

        int RadioX => _w - _m.S(14) - _m.S(16);       // העיגול – מימין

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(_t.MenuBg);
            int textRight = RadioX - _m.S(8);
            Draw.Text(g, "מרחק בין המילים", _m.CaptionBold, new Rectangle(_m.S(10), _m.S(6), _w - _m.S(24), _headH), _t.MenuDim);
            int sepY = _rows[2].Bottom + _m.S(4);
            using (var p = new Pen(_t.MenuBorder)) g.DrawLine(p, _m.S(10), sepY, _w - _m.S(10), sepY);
            Draw.Text(g, "סדר המילים", _m.CaptionBold, new Rectangle(_m.S(10), _rows[3].Top - _headH, _w - _m.S(24), _headH), _t.MenuDim);

            for (int i = 0; i < 5; i++)
            {
                var r = _rows[i];
                if (i == _hoverRow) Draw.Fill(g, r, _m.S(3), _t.MenuSel);
                bool on = i < 3 ? Distance == i : (i == 3) == Ordered;
                Radio(g, new Rectangle(RadioX, r.Y + (r.Height - _m.S(16)) / 2, _m.S(16), _m.S(16)), on);
                string label = i == 0 ? "צמודות" : i == 2 ? "באותה פסקה" : i == 3 ? "לפי הסדר שהוקלד" : i == 4 ? "בכל סדר" : null;
                if (label != null)
                {
                    Draw.Text(g, label, _m.Body, new Rectangle(r.Left + _m.S(6), r.Y, textRight - r.Left - _m.S(6), r.Height), _t.MenuText);
                    continue;
                }
                // "עד [− N +] מילים ביניהן"
                int x = textRight;
                int w1 = Draw.Width("עד", _m.Body);
                Draw.Text(g, "עד", _m.Body, new Rectangle(x - w1, r.Y, w1 + 1, r.Height), _t.MenuText);
                x -= w1 + _m.S(8);
                int bh = _m.S(24), bw = _m.S(22), nw = _m.S(30);
                int by = r.Y + (r.Height - bh) / 2;
                _plus = new Rectangle(x - bw, by, bw, bh);                      // מימין לשמאל: + מספר −
                _number = new Rectangle(_plus.Left - nw, by, nw, bh);
                _minus = new Rectangle(_number.Left - bw, by, bw, bh);
                var box = Rectangle.Union(_minus, _plus);
                Draw.Box(g, box, _m.S(4), _t.FieldBg, Distance == 1 ? _t.Accent : _t.FieldBorder, 1f);
                if (_hoverBtn == 1) Draw.Fill(g, Rectangle.Inflate(_minus, -_m.S(2), -_m.S(2)), _m.S(3), Draw.Mix(_t.FieldBg, _t.FieldBorder, 0.5f));
                if (_hoverBtn == 2) Draw.Fill(g, Rectangle.Inflate(_plus, -_m.S(2), -_m.S(2)), _m.S(3), Draw.Mix(_t.FieldBg, _t.FieldBorder, 0.5f));
                float stroke = Math.Max(1.4f, _m.Scale * 1.5f), arm = _m.S(4.5f);
                using (var p = new Pen(Near > 1 ? _t.FieldIcon : Draw.Mix(_t.FieldIcon, _t.FieldBg, 0.6f), stroke))
                {
                    float cx = _minus.X + _minus.Width / 2f, cy = _minus.Y + _minus.Height / 2f;
                    g.DrawLine(p, cx - arm, cy, cx + arm, cy);
                }
                using (var p = new Pen(Near < 99 ? _t.FieldIcon : Draw.Mix(_t.FieldIcon, _t.FieldBg, 0.6f), stroke))
                {
                    float cx = _plus.X + _plus.Width / 2f, cy = _plus.Y + _plus.Height / 2f;
                    g.DrawLine(p, cx - arm, cy, cx + arm, cy);
                    g.DrawLine(p, cx, cy - arm, cx, cy + arm);
                }
                using (var p = new Pen(_t.FieldBorder))
                {
                    g.DrawLine(p, _number.Left, by + _m.S(4), _number.Left, by + bh - _m.S(4));
                    g.DrawLine(p, _number.Right, by + _m.S(4), _number.Right, by + bh - _m.S(4));
                }
                Draw.Text(g, Near.ToString(), _m.BodyBold, _number, _t.FieldText, 'c', false);
                x = _minus.Left - _m.S(8);
                Draw.Text(g, "מילים ביניהן", _m.Body, new Rectangle(r.Left + _m.S(6), r.Y, x - r.Left - _m.S(6), r.Height), _t.MenuText);
            }
        }

        void Radio(Graphics g, Rectangle r, bool on)
        {
            var old = g.SmoothingMode;
            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            using (var p = new Pen(on ? _t.Accent : _t.MenuDim, Math.Max(1.2f, _m.Scale * 1.3f)))
                g.DrawEllipse(p, r.X + 1, r.Y + 1, r.Width - 2, r.Height - 2);
            if (on)
                using (var b = new SolidBrush(_t.Accent))
                {
                    float d = r.Width * 0.5f;
                    g.FillEllipse(b, r.X + (r.Width - d) / 2f, r.Y + (r.Height - d) / 2f, d, d);
                }
            g.SmoothingMode = old;
        }

        void Set(int distance, int near, bool ordered)
        {
            near = Math.Max(1, Math.Min(99, near));
            if (distance == Distance && near == Near && ordered == Ordered) return;
            Distance = distance;
            Near = near;
            Ordered = ordered;
            Invalidate();
            Changed?.Invoke();
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            int row = Array.FindIndex(_rows, r => r.Contains(e.Location));
            int btn = _minus.Contains(e.Location) ? 1 : _plus.Contains(e.Location) ? 2 : 0;
            if (row != _hoverRow || btn != _hoverBtn) { _hoverRow = row; _hoverBtn = btn; Invalidate(); }
            Cursor = row >= 0 ? Cursors.Hand : Cursors.Default;
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            base.OnMouseLeave(e);
            _hoverRow = -1;
            _hoverBtn = 0;
            Invalidate();
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            if (e.Button != MouseButtons.Left) return;
            if (_minus.Contains(e.Location)) { Set(1, Near - 1, Ordered); return; }
            if (_plus.Contains(e.Location)) { Set(1, Near + 1, Ordered); return; }
            int row = Array.FindIndex(_rows, r => r.Contains(e.Location));
            if (row >= 0 && row < 3) Set(row, Near, Ordered);
            else if (row == 3) Set(Distance, Near, true);
            else if (row == 4) Set(Distance, Near, false);
        }

        protected override void OnMouseWheel(MouseEventArgs e)
        {
            base.OnMouseWheel(e);
            if (_rows[1].Contains(e.Location)) Set(1, Near + Math.Sign(e.Delta), Ordered);
        }

        protected override bool IsInputKey(Keys keyData)
        {
            switch (keyData & Keys.KeyCode)
            {
                case Keys.Up: case Keys.Down: case Keys.Left: case Keys.Right: case Keys.Enter: case Keys.Escape:
                case Keys.Add: case Keys.Subtract: case Keys.Oemplus: case Keys.OemMinus:
                    return true;
            }
            return base.IsInputKey(keyData);
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            base.OnKeyDown(e);
            switch (e.KeyCode)
            {
                case Keys.Up: Set(Math.Max(0, Distance - 1), Near, Ordered); break;
                case Keys.Down: Set(Math.Min(2, Distance + 1), Near, Ordered); break;
                case Keys.Add: case Keys.Oemplus: case Keys.Left: Set(1, Near + 1, Ordered); break;       // בעברית "קדימה" שמאלה
                case Keys.Subtract: case Keys.OemMinus: case Keys.Right: Set(1, Near - 1, Ordered); break;
                case Keys.Enter: case Keys.Escape: CloseRequested?.Invoke(); break;
                default: return;
            }
            e.Handled = e.SuppressKeyPress = true;
        }
    }
}
