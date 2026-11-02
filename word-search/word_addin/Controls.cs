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

        public event Action<bool> Submit;          // Enter (shift = הקודמת)
        public event Action<int> Navigate;         // חצים למעלה/למטה
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
        public readonly string[] Labels = { "תוצאות", "כותרות" };
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
