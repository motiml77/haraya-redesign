// "הצג בחלון נפרד" (ניסיוני): חלון קטן עם כ-70 מילים סביב תוצאה – 35 לפני ו-35 אחרי, וגם מהפסקאות
// הסמוכות כשהפסקה קצרה. המילים שנמצאו במרקר, מעל – מספר התוצאה והכותרות שהיא נמצאת תחתיהן.
// אפשר לפתוח כמה חלונות כאלה (להשוואה), לשנות את הגודל, להעתיק, ולעבור למקום במסמך.
// בלי Word – גם התצוגה המקדימה בבנייה מציירת אותו.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Windows.Forms;

namespace HebDocSearch.WordAddin
{
    internal sealed class ContextWindow : Form
    {
        readonly Theme _t;
        readonly Metrics _m;
        readonly ContextView _view;
        readonly Panel _scroll = new Panel { AutoScroll = true };
        readonly TextButton _go = new TextButton { Text = "עבור למקום במסמך", Primary = true };
        readonly TextButton _copy = new TextButton { Text = "העתקה" };
        readonly TextButton _close = new TextButton { Text = "סגירה" };
        readonly string _number, _path;
        readonly Excerpt _excerpt;

        public ContextWindow(Theme theme, float scale, int number, string[] path, Excerpt excerpt, Action goToResult)
        {
            _t = theme;
            _m = new Metrics(scale);
            _excerpt = excerpt;
            _number = number.ToString("N0");
            _path = path == null || path.Length == 0 ? "" : string.Join("  ‹  ", path);
            Text = $"תוצאה {_number} – חיפוש עברי";
            RightToLeft = RightToLeft.Yes;
            RightToLeftLayout = false;               // הציור והפריסה כאן מימין לשמאל בעצמם
            ShowInTaskbar = false;
            MinimizeBox = false;
            MaximizeBox = false;
            KeyPreview = true;
            StartPosition = FormStartPosition.Manual;
            AutoScaleMode = AutoScaleMode.None;
            BackColor = theme.PaneBg;
            ClientSize = new Size(_m.S(470), _m.S(320));
            MinimumSize = new Size(_m.S(300), _m.S(200));
            try { Icon = Icon.FromHandle(Assets.Logo(32).GetHicon()); } catch { }

            _view = new ContextView(theme, _m, excerpt);
            _scroll.BackColor = theme.PaneBg;
            _scroll.Controls.Add(_view);
            Controls.Add(_scroll);
            foreach (var b in new[] { _go, _copy, _close })
            {
                b.ApplyTheme(theme, _m);
                Controls.Add(b);
            }
            _go.Click += (s, e) => goToResult?.Invoke();
            _copy.Click += (s, e) =>
            {
                try { Clipboard.SetText(_excerpt.Text.Replace("\n", Environment.NewLine)); } catch { }
            };
            _close.Click += (s, e) => Close();
            _go.Visible = goToResult != null;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        }

        int HeaderH => _m.S(_path.Length > 0 ? 58 : 40);
        int FooterH => _m.S(48);

        protected override void OnLayout(LayoutEventArgs e)
        {
            base.OnLayout(e);
            if (_view == null) return;
            int w = ClientSize.Width, h = ClientSize.Height, pad = _m.S(12);
            _scroll.SetBounds(0, HeaderH, w, Math.Max(10, h - HeaderH - FooterH));
            int inner = _scroll.ClientSize.Width;
            _view.Width = Math.Max(_m.S(100), inner - (_view.Height > _scroll.ClientSize.Height ? SystemInformation.VerticalScrollBarWidth : 0));
            _view.Relayout();
            // כפתורים: מימין לשמאל – עבור, העתקה … סגירה בשמאל
            int bh = _m.S(30), by = h - FooterH + (FooterH - bh) / 2;
            int x = w - pad;
            foreach (var b in new[] { _go, _copy })
            {
                if (!b.Visible) continue;
                int bw = b.PreferredWidth;
                b.SetBounds(x - bw, by, bw, bh);
                x -= bw + _m.S(8);
            }
            _close.SetBounds(pad, by, _close.PreferredWidth, bh);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(_t.PaneBg);
            // הכותרת: מספר התוצאה, ומתחתיו הכותרות שמעליה (כמו ברשימה)
            int pad = _m.S(14), top = _m.S(12);
            int badgeH = Draw.Height(_m.CaptionBold) + _m.S(4);
            int bw = Math.Max(badgeH, Draw.Width(_number, _m.CaptionBold, false) + _m.S(12));
            var badge = new Rectangle(ClientSize.Width - pad - bw, top, bw, badgeH);
            Draw.Fill(g, badge, badgeH / 2f, _t.Accent);
            Draw.Text(g, _number, _m.CaptionBold, badge, _t.OnAccent, 'c', false);
            Draw.Text(g, "תוצאה " + _number, _m.BodyBold, new Rectangle(pad, top, badge.Left - _m.S(8) - pad, badgeH), _t.Text);
            if (_path.Length > 0)
                Draw.Text(g, _path, _m.Caption, new Rectangle(pad, top + badgeH + _m.S(4), ClientSize.Width - 2 * pad, Draw.Height(_m.Caption)), _t.Heading);
            using (var pen = new Pen(_t.Separator))
            {
                g.DrawLine(pen, 0, HeaderH - 1, ClientSize.Width, HeaderH - 1);
                g.DrawLine(pen, 0, ClientSize.Height - FooterH, ClientSize.Width, ClientSize.Height - FooterH);
            }
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            base.OnKeyDown(e);
            if (e.KeyCode == Keys.Escape) { e.Handled = true; Close(); }
            else if (e.Control && e.KeyCode == Keys.C) { e.Handled = true; _copy.PerformClick(); }
        }

        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            base.OnFormClosed(e);
            _m.Dispose();
        }

        /// <summary>מקום ליד העכבר, בתוך המסך.</summary>
        public void PlaceNear(Point screen)
        {
            var area = Screen.FromPoint(screen).WorkingArea;
            int x = screen.X - Width - _m.S(16), y = screen.Y - _m.S(40);
            if (x < area.Left) x = screen.X + _m.S(16);
            x = Math.Max(area.Left, Math.Min(area.Right - Width, x));
            y = Math.Max(area.Top, Math.Min(area.Bottom - Height, y));
            Location = new Point(x, y);
        }
    }

    /// <summary>הטקסט של החלון: פסקה מימין לשמאל (מנוע הטקסט של Windows), התאמות במרקר.</summary>
    internal sealed class ContextView : Control
    {
        readonly Theme _t;
        readonly Metrics _m;
        readonly Excerpt _ex;
        readonly Font _font;
        readonly StringFormat _format = new StringFormat(StringFormatFlags.DirectionRightToLeft) { Trimming = StringTrimming.None };
        List<RectangleF> _marks = new List<RectangleF>();
        int _laidWidth = -1;

        public ContextView(Theme t, Metrics m, Excerpt ex)
        {
            _t = t;
            _m = m;
            _ex = ex ?? new Excerpt();
            _font = new Font(Metrics.Family, 15f * m.Scale, FontStyle.Regular, GraphicsUnit.Pixel);
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            BackColor = t.PaneBg;
            RightToLeft = RightToLeft.No;
        }

        int Pad => _m.S(14);

        public void Relayout()
        {
            if (Width == _laidWidth || !IsHandleCreated && Parent == null) return;
            int w = Math.Max(_m.S(60), Width - 2 * Pad);
            using (var bmp = new Bitmap(1, 1))
            using (var g = Graphics.FromImage(bmp))
            {
                g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
                var size = g.MeasureString(_ex.Text.Length == 0 ? " " : _ex.Text, _font, w, _format);
                _marks = new List<RectangleF>();
                var layout = new RectangleF(0, 0, w, size.Height + 2);
                for (int i = 0; i < _ex.Marks.Count; i += 32)
                {
                    int n = Math.Min(32, _ex.Marks.Count - i);
                    var ranges = new CharacterRange[n];
                    for (int k = 0; k < n; k++) ranges[k] = new CharacterRange(_ex.Marks[i + k][0], _ex.Marks[i + k][1]);
                    using (var fmt = (StringFormat)_format.Clone())
                    {
                        fmt.SetMeasurableCharacterRanges(ranges);
                        foreach (var region in g.MeasureCharacterRanges(_ex.Text, _font, layout, fmt))
                        {
                            using (var identity = new Matrix())
                                foreach (var r in region.GetRegionScans(identity))
                                    if (r.Width > 0.5f) _marks.Add(r);
                            region.Dispose();
                        }
                    }
                }
                Height = (int)Math.Ceiling(size.Height) + 2 * Pad;
            }
            _laidWidth = Width;
            Invalidate();
        }

        protected override void OnResize(EventArgs e)
        {
            base.OnResize(e);
            Relayout();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(_t.PaneBg);
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            int w = Math.Max(_m.S(60), Width - 2 * Pad);
            var layout = new RectangleF(Pad, Pad, w, Height);
            float pad = _m.S(2);
            var clips = new List<RectangleF>();
            foreach (var r in _marks)
            {
                clips.Add(new RectangleF(Pad + r.X, Pad + r.Y, r.Width, r.Height));
                Draw.Fill(g, new RectangleF(Pad + r.X - pad, Pad + r.Y + _m.S(1), r.Width + 2 * pad, r.Height - _m.S(1)), _m.S(3), _t.Marker);
            }
            using (var b = new SolidBrush(_t.Text)) g.DrawString(_ex.Text, _font, b, layout, _format);
            if (clips.Count > 0)
            {
                var old = g.Clip;
                using (var region = new Region(RectangleF.Empty))
                {
                    foreach (var c in clips) region.Union(c);
                    g.SetClip(region, CombineMode.Intersect);
                    using (var b = new SolidBrush(_t.MarkerText)) g.DrawString(_ex.Text, _font, b, layout, _format);
                }
                g.Clip = old;
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) { _font.Dispose(); _format.Dispose(); }
            base.Dispose(disposing);
        }
    }
}
