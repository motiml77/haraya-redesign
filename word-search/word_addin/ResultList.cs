// רשימת התוצאות – בבסיס כמו בחלונית "ניווט" של Word (קווים דקים בין התוצאות, ההתאמה בולטת),
// ובנוסף: מספר לכל תוצאה, שרשרת הכותרות שהיא נמצאת תחתיהן, והמילים שנמצאו מסומנות במרקר.
//
// מצוירת בקוד ווירטואלית: רק התוצאות שעל המסך מצוירות, והפריסה של כל תוצאה מחושבת פעם אחת
// לכל רוחב – כך שגם מאות תוצאות מוצגות מיד, בלי לעכב את Word.
//
// הטקסט של כל תוצאה נפרס כפסקה אחת על-ידי מנוע הטקסט של Windows (GDI+, מימין לשמאל) – אותו
// טיפול דו-כיווני כמו ב-Word לאנגלית, מספרים ופיסוק בתוך עברית, ורווחים טבעיים. מקום המרקר
// נמדד על אותה פריסה (MeasureCharacterRanges), והטקסט שבתוכו נצבע מחדש בדיו כהה.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Text;
using System.Windows.Forms;

namespace HebDocSearch.WordAddin
{
    internal sealed class Seg
    {
        public string Text;
        public int Kind;          // 0 רגיל, 1 התאמה, 2 השמטה (…), 3 סוף פסקה
    }

    internal sealed class ResultItem
    {
        public int Number;
        public int Para;
        public int Level;
        public int Covered, Terms;
        public bool HeadingHit;                       // חיפוש בכותרות בלבד: התוצאה היא הכותרת עצמה
        public string NoPathText = "";                // מה לכתוב כשאין כותרת מעל
        public List<int[]> Ranges = new List<int[]>();
        public string[] Path = new string[0];
        public List<Seg> Snippet = new List<Seg>();

        // פריסה (לפי רוחב)
        internal int LayoutWidth = -1, Height, Top, TextHeight;
        internal string Text = "";
        internal List<RectangleF> Marks = new List<RectangleF>();     // יחסית לפינת הטקסט
    }

    internal sealed class ResultList : Control
    {
        Theme _t = Theme.Light;
        Metrics _m;
        List<ResultItem> _items = new List<ResultItem>();
        int _scroll, _contentH, _sel = -1, _hover = -1;
        int _captionH;
        readonly StringFormat _format = new StringFormat(StringFormatFlags.DirectionRightToLeft)
        {
            Alignment = StringAlignment.Near,          // בכיוון מימין לשמאל: מיושר לימין
            Trimming = StringTrimming.None,
        };

        // הודעה כשאין תוצאות (מסך פתיחה / אין תוצאות / שגיאה)
        Bitmap _msgImage;
        string _msgTitle = "";
        string[] _msgLines = new string[0];
        bool _msgWarn;

        // פס הגלילה
        bool _dragging, _thumbHover;
        int _dragStartY, _dragStartScroll;

        public event Action<int> ItemActivated;
        public event Action<int, Point> ItemContextMenu;         // לחיצה ימנית (מיקום במסך): "הצג בחלון נפרד"

        public ResultList()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint
                     | ControlStyles.ResizeRedraw | ControlStyles.Selectable, true);
            TabStop = true;
        }

        public void ApplyTheme(Theme t, Metrics m)
        {
            _t = t;
            _m = m;
            _captionH = Draw.Height(m.Caption);
            foreach (var it in _items) it.LayoutWidth = -1;
            Relayout();
        }

        // ================================================================ נתונים
        public int Count => _items.Count;
        public int SelectedIndex => _sel;

        public void SetItems(List<ResultItem> items)
        {
            _items = items ?? new List<ResultItem>();
            _sel = -1;
            _hover = -1;
            _scroll = 0;
            Relayout();
        }

        public void SetMessage(Bitmap image, string title, string[] lines, bool warn)
        {
            _msgImage = image;
            _msgTitle = title ?? "";
            _msgLines = lines ?? new string[0];
            _msgWarn = warn;
            Invalidate();
        }

        public void Select(int index, bool ensureVisible = true)
        {
            if (_items.Count == 0) { _sel = -1; Invalidate(); return; }
            index = Math.Max(0, Math.Min(_items.Count - 1, index));
            if (index != _sel)
            {
                _sel = index;
                Invalidate();
            }
            if (ensureVisible) EnsureVisible(index);
        }

        void EnsureVisible(int index)
        {
            if (index < 0 || index >= _items.Count || _m == null) return;
            var it = _items[index];
            int margin = _m.S(4);
            if (it.Top < _scroll) SetScroll(it.Top - margin);
            else if (it.Top + it.Height > _scroll + ClientSize.Height) SetScroll(it.Top + it.Height - ClientSize.Height + margin);
        }

        void SetScroll(int value)
        {
            int max = Math.Max(0, _contentH - ClientSize.Height);
            value = Math.Max(0, Math.Min(max, value));
            if (value != _scroll)
            {
                _scroll = value;
                Invalidate();
            }
        }

        // ================================================================ מידות
        int Gutter => _m.S(14);                        // פס הגלילה משמאל
        int PadX => _m.S(12);
        int PadTop => _m.S(9);
        int PadBottom => _m.S(10);
        int BadgeH => _captionH + _m.S(4);
        int HeaderH => Math.Max(_captionH, BadgeH);
        int HeaderGap => _m.S(4);
        int TextLeft => Gutter + PadX;
        int TextRight => ClientSize.Width - PadX;
        int TextWidth => Math.Max(_m.S(60), TextRight - TextLeft);

        Font TextFont(ResultItem it) => it.HeadingHit ? _m.ResultBold : _m.Result;

        void Relayout()
        {
            if (_m == null || !IsHandleCreated) { Invalidate(); return; }
            int width = TextWidth, top = 0;
            using (var g = CreateGraphics())
            {
                g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
                foreach (var it in _items)
                {
                    if (it.LayoutWidth != width) LayoutItem(g, it, width);
                    it.Top = top;
                    top += it.Height;
                }
            }
            _contentH = top;
            SetScroll(_scroll);
            Invalidate();
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            Relayout();
        }

        protected override void OnResize(EventArgs e)
        {
            base.OnResize(e);
            Relayout();
            EnsureVisible(_sel);
        }

        // ================================================================ פריסת הטקסט של תוצאה
        void LayoutItem(Graphics g, ResultItem it, int width)
        {
            // הטקסט כמחרוזת אחת, ומקומות ההתאמות בתוכה (התאמות צמודות – מרקר רציף אחד)
            var sb = new StringBuilder();
            var marks = new List<CharacterRange>();
            foreach (var seg in it.Snippet)
            {
                if (seg.Kind == 3)                         // סוף פסקה – בלי סימן ¶
                {
                    sb.Append("  ");
                    continue;
                }
                string text = (seg.Text ?? "").Replace('\r', ' ').Replace('\n', ' ').Replace('\t', ' ');
                if (seg.Kind == 1 && text.Length > 0)
                {
                    int start = sb.Length;
                    if (marks.Count > 0)
                    {
                        var last = marks[marks.Count - 1];
                        int end = last.First + last.Length;
                        if (sb.ToString(end, start - end).Trim().Length == 0)
                        {
                            marks[marks.Count - 1] = new CharacterRange(last.First, start + text.Length - last.First);
                            sb.Append(text);
                            continue;
                        }
                    }
                    marks.Add(new CharacterRange(start, text.Length));
                }
                sb.Append(text);
            }
            it.Text = sb.ToString();
            var font = TextFont(it);
            var size = g.MeasureString(it.Text.Length == 0 ? " " : it.Text, font, width, _format);
            it.TextHeight = (int)Math.Ceiling(size.Height);

            it.Marks = new List<RectangleF>();
            var layout = new RectangleF(0, 0, width, it.TextHeight + 2);
            for (int i = 0; i < marks.Count; i += 32)                       // עד 32 טווחים בכל מדידה
            {
                int n = Math.Min(32, marks.Count - i);
                var ranges = marks.GetRange(i, n).ToArray();
                using (var fmt = (StringFormat)_format.Clone())
                {
                    fmt.SetMeasurableCharacterRanges(ranges);
                    var regions = g.MeasureCharacterRanges(it.Text, font, layout, fmt);
                    using (var identity = new Matrix())
                        foreach (var region in regions)
                        {
                            foreach (var r in region.GetRegionScans(identity))      // התאמה שגולשת לשורה הבאה – כמה מלבנים
                                if (r.Width > 0.5f) it.Marks.Add(r);
                            region.Dispose();
                        }
                }
            }
            it.LayoutWidth = width;
            it.Height = PadTop + HeaderH + HeaderGap + it.TextHeight + PadBottom;
        }

        // ================================================================ ציור
        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.Clear(_t.PaneBg);
            if (_m == null) return;
            if (_items.Count == 0)
            {
                PaintMessage(g);
                return;
            }
            if (_items.Count > 0 && _items[0].LayoutWidth != TextWidth) Relayout();
            int h = ClientSize.Height;
            foreach (var it in FindVisible(_scroll, _scroll + h))
                PaintItem(g, it, it.Top - _scroll);
            PaintScrollbar(g);
        }

        IEnumerable<ResultItem> FindVisible(int top, int bottom)
        {
            // חיפוש בינארי של הראשונה שנראית
            int lo = 0, hi = _items.Count - 1, first = _items.Count;
            while (lo <= hi)
            {
                int mid = (lo + hi) / 2;
                if (_items[mid].Top + _items[mid].Height > top) { first = mid; hi = mid - 1; }
                else lo = mid + 1;
            }
            for (int i = first; i < _items.Count && _items[i].Top < bottom; i++)
                yield return _items[i];
        }

        void PaintItem(Graphics g, ResultItem it, int y)
        {
            int index = it.Number - 1;
            bool selected = index == _sel, hover = index == _hover;
            var row = new Rectangle(Gutter, y, ClientSize.Width - Gutter, it.Height - 1);
            if (selected || hover)
                using (var b = new SolidBrush(selected ? _t.ItemSel : _t.ItemHover)) g.FillRectangle(b, row);
            if (selected)
                using (var b = new SolidBrush(_t.SelBar)) g.FillRectangle(b, new Rectangle(ClientSize.Width - _m.S(3), y, _m.S(3), it.Height - 1));

            // ----- שורת הכותרת: מספר, שרשרת הכותרות, תגית -----
            int top = y + PadTop;
            string num = it.Number.ToString("N0");
            int badgeW = Math.Max(BadgeH, Draw.Width(num, _m.CaptionBold, false) + _m.S(10));
            var badge = new Rectangle(TextRight - badgeW, top + (HeaderH - BadgeH) / 2, badgeW, BadgeH);
            Draw.Fill(g, badge, BadgeH / 2f, selected ? _t.Accent : _t.BadgeBg);
            Draw.Text(g, num, _m.CaptionBold, badge, selected ? _t.OnAccent : _t.BadgeText, 'c', false);

            int limit = TextLeft;
            string tag = null;
            Color tagFg = _t.BadgeText, tagBg = _t.BadgeBg;
            if (it.HeadingHit && it.Level > 0) tag = "כותרת " + it.Level;
            else if (it.Terms > 1 && it.Covered < it.Terms)
            {
                tag = $"{it.Covered} מתוך {it.Terms} מילים";
                tagFg = _t.Warn;
                tagBg = _t.WarnBg;
            }
            if (tag != null)
            {
                int tw = Draw.Width(tag, _m.Caption) + _m.S(12);
                var tr = new Rectangle(limit, top + (HeaderH - BadgeH) / 2, tw, BadgeH);
                Draw.Fill(g, tr, _m.S(4), tagBg);
                Draw.Text(g, tag, _m.Caption, tr, tagFg, 'c');
                limit = tr.Right + _m.S(8);
            }
            PaintPath(g, it, new Rectangle(limit, top, badge.Left - _m.S(8) - limit, HeaderH));

            // ----- הקטע: מרקר, טקסט, ובתוך המרקר – הטקסט שוב בדיו כהה -----
            float tx = TextLeft, ty = top + HeaderH + HeaderGap;
            var layout = new RectangleF(tx, ty, TextWidth, it.TextHeight + 2);
            var font = TextFont(it);
            var oldHint = g.TextRenderingHint;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            var marks = new List<RectangleF>(it.Marks.Count);          // רק האותיות שנמצאו (בלי השוליים של המרקר)
            float pad = _m.S(2);
            foreach (var r in it.Marks)
            {
                marks.Add(new RectangleF(tx + r.X, ty + r.Y, r.Width, r.Height));
                Draw.Fill(g, new RectangleF(tx + r.X - pad, ty + r.Y + _m.S(1), r.Width + 2 * pad, r.Height - _m.S(1)), _m.S(3), _t.Marker);
            }
            using (var b = new SolidBrush(_t.Text))
                g.DrawString(it.Text, font, b, layout, _format);
            if (marks.Count > 0)
            {
                var oldClip = g.Clip;
                using (var region = new Region(RectangleF.Empty))
                {
                    foreach (var m in marks) region.Union(m);
                    g.SetClip(region, CombineMode.Intersect);
                    using (var b = new SolidBrush(_t.MarkerText))
                        g.DrawString(it.Text, font, b, layout, _format);
                }
                g.Clip = oldClip;
            }
            g.TextRenderingHint = oldHint;

            // קו דק בין התוצאות, כמו ב-Word
            using (var pen = new Pen(_t.Separator))
                g.DrawLine(pen, Gutter, y + it.Height - 1, ClientSize.Width, y + it.Height - 1);
        }

        void PaintPath(Graphics g, ResultItem it, Rectangle area)
        {
            if (area.Width < _m.S(20)) return;
            var path = it.Path;
            if (path.Length == 0)
            {
                if (it.NoPathText.Length > 0) Draw.Text(g, it.NoPathText, _m.Caption, area, _t.TextFaint);
                return;
            }
            int sepW = _m.S(14);
            int ellW = Draw.Width("…", _m.Caption, false) + _m.S(2);
            var widths = new int[path.Length];
            for (int i = 0; i < path.Length; i++)
                widths[i] = Draw.Width(path[i], i == path.Length - 1 ? _m.CaptionBold : _m.Caption);
            int start = 0;
            Func<int> total = () =>
            {
                int t = start > 0 ? ellW + sepW : 0;
                for (int i = start; i < path.Length; i++) t += widths[i] + (i < path.Length - 1 ? sepW : 0);
                return t;
            };
            while (start < path.Length - 1 && total() > area.Width) start++;   // מוותרים קודם על הכותרות העליונות

            int xr = area.Right;
            Action separator = () =>                    // ‹ – מצויר, כדי שלא יתהפך בטקסט מימין לשמאל
            {
                if (xr - area.Left < sepW) { xr = area.Left; return; }
                float s = _m.S(9);
                Draw.Chevron(g, new RectangleF(xr - sepW + (sepW - s) / 2f, area.Y + (area.Height - s) / 2f, s, s), _t.TextFaint,
                             Math.Max(1.1f, _m.Scale * 1.2f), 'l');
                xr -= sepW;
            };
            Action<string, Font, Color, int> put = (text, font, color, w) =>
            {
                w = Math.Min(w, xr - area.Left);
                if (w <= 0) return;
                Draw.Text(g, text, font, new Rectangle(xr - w, area.Y, w, area.Height), color);
                xr -= w;
            };
            if (start > 0)
            {
                put("…", _m.Caption, _t.TextFaint, ellW);
                separator();
            }
            for (int i = start; i < path.Length; i++)
            {
                bool last = i == path.Length - 1;
                put(path[i], last ? _m.CaptionBold : _m.Caption, last ? _t.Heading : _t.TextDim, widths[i] + 1);
                if (!last) separator();
            }
        }

        void PaintMessage(Graphics g)
        {
            int w = ClientSize.Width - 2 * _m.S(24);
            if (w < _m.S(60)) return;
            int y = _m.S(28);
            int cx = ClientSize.Width / 2;
            if (_msgImage != null)
            {
                int s = _m.S(48);
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.DrawImage(_msgImage, new Rectangle(cx - s / 2, y, s, s));
                y += s + _m.S(14);
            }
            var flags = TextFormatFlags.NoPrefix | TextFormatFlags.WordBreak | TextFormatFlags.HorizontalCenter | TextFormatFlags.RightToLeft;
            if (_msgTitle.Length > 0)
            {
                var size = TextRenderer.MeasureText(g, _msgTitle, _m.Hero, new Size(w, int.MaxValue), flags);
                TextRenderer.DrawText(g, _msgTitle, _m.Hero, new Rectangle(_m.S(24), y, w, size.Height), _msgWarn ? _t.Warn : _t.Text, flags);
                y += size.Height + _m.S(8);
            }
            foreach (string line in _msgLines)
            {
                if (string.IsNullOrEmpty(line)) { y += _m.S(8); continue; }
                var size = TextRenderer.MeasureText(g, line, _m.Body, new Size(w, int.MaxValue), flags);
                TextRenderer.DrawText(g, line, _m.Body, new Rectangle(_m.S(24), y, w, size.Height), _t.TextDim, flags);
                y += size.Height + _m.S(4);
            }
        }

        // ================================================================ פס גלילה דק (כמו ב-Word)
        Rectangle TrackRect => new Rectangle(_m.S(3), _m.S(2), _m.S(8), ClientSize.Height - _m.S(4));

        Rectangle ThumbRect
        {
            get
            {
                var tr = TrackRect;
                int h = ClientSize.Height;
                if (_contentH <= h) return Rectangle.Empty;
                int th = Math.Max(_m.S(28), (int)((long)tr.Height * h / _contentH));
                int max = _contentH - h;
                int ty = tr.Y + (int)((long)(tr.Height - th) * _scroll / Math.Max(1, max));
                return new Rectangle(tr.X + _m.S(1), ty, tr.Width - _m.S(2), th);
            }
        }

        void PaintScrollbar(Graphics g)
        {
            if (_contentH <= ClientSize.Height) return;
            var tr = TrackRect;
            Draw.Fill(g, tr, tr.Width / 2f, _t.ScrollTrack);
            var th = ThumbRect;
            Draw.Fill(g, th, th.Width / 2f, _thumbHover || _dragging ? _t.ScrollThumbHover : _t.ScrollThumb);
        }

        // ================================================================ עכבר ומקלדת
        int IndexAt(int y)
        {
            int cy = y + _scroll;
            foreach (var it in FindVisible(cy, cy + 1))
                return it.Number - 1;
            return -1;
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            Focus();
            if (_m == null) return;
            if (e.Button == MouseButtons.Right)
            {
                int ri = e.X < Gutter ? -1 : IndexAt(e.Y);
                if (ri >= 0)
                {
                    Select(ri, false);
                    ItemContextMenu?.Invoke(ri, PointToScreen(e.Location));
                }
                return;
            }
            if (e.Button != MouseButtons.Left) return;
            if (_contentH > ClientSize.Height && e.X < Gutter)
            {
                var th = ThumbRect;
                if (th.Contains(e.X, e.Y) || (e.X >= TrackRect.X - _m.S(2) && e.Y >= th.Top && e.Y <= th.Bottom))
                {
                    _dragging = true;
                    _dragStartY = e.Y;
                    _dragStartScroll = _scroll;
                    Capture = true;
                }
                else SetScroll(_scroll + (e.Y < th.Top ? -1 : 1) * (ClientSize.Height - _m.S(20)));
                Invalidate();
                return;
            }
            int i = IndexAt(e.Y);
            if (i >= 0)
            {
                Select(i);
                ItemActivated?.Invoke(i);                         // לחיצה – ישר למקום במסמך
            }
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            if (_m == null) return;
            if (_dragging)
            {
                var tr = TrackRect;
                int th = ThumbRect.Height;
                int max = _contentH - ClientSize.Height;
                int delta = e.Y - _dragStartY;
                SetScroll(_dragStartScroll + (int)((long)delta * max / Math.Max(1, tr.Height - th)));
                return;
            }
            bool overThumb = ThumbRect.Contains(e.Location);
            if (overThumb != _thumbHover) { _thumbHover = overThumb; Invalidate(); }
            int i = e.X < Gutter ? -1 : IndexAt(e.Y);
            if (i != _hover)
            {
                _hover = i;
                Invalidate();
            }
            Cursor = i >= 0 ? Cursors.Hand : Cursors.Default;
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            base.OnMouseUp(e);
            if (_dragging)
            {
                _dragging = false;
                Capture = false;
                Invalidate();
            }
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            base.OnMouseLeave(e);
            _hover = -1;
            _thumbHover = false;
            Invalidate();
        }

        protected override void OnMouseWheel(MouseEventArgs e)
        {
            base.OnMouseWheel(e);
            if (_m == null) return;
            int lines = Math.Max(1, SystemInformation.MouseWheelScrollLines);
            SetScroll(_scroll - e.Delta * lines * _m.S(20) / 120);
        }

        protected override bool IsInputKey(Keys keyData)
        {
            switch (keyData & Keys.KeyCode)
            {
                case Keys.Up: case Keys.Down: case Keys.PageUp: case Keys.PageDown: case Keys.Home: case Keys.End: case Keys.Enter: case Keys.Space:
                case Keys.Apps:
                    return true;
            }
            return base.IsInputKey(keyData);
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            base.OnKeyDown(e);
            if (_items.Count == 0) return;
            // מקש התפריט / Shift+F10 – אותו תפריט כמו לחיצה ימנית, ליד התוצאה המסומנת
            if (e.KeyCode == Keys.Apps || (e.KeyCode == Keys.F10 && e.Shift))
            {
                e.Handled = e.SuppressKeyPress = true;
                if (_sel < 0) Select(0);
                var it = _items[_sel];
                ItemContextMenu?.Invoke(_sel, PointToScreen(new Point(TextRight - _m.S(60), it.Top - _scroll + _m.S(24))));
                return;
            }
            // חיצים – רק מסמנים תוצאה ברשימה; Enter (או רווח) – עוברים אליה במסמך, כמו לחיצה
            if (e.KeyCode == Keys.Enter || e.KeyCode == Keys.Space)
            {
                e.Handled = e.SuppressKeyPress = true;
                if (_sel < 0) Select(0);
                ItemActivated?.Invoke(_sel);
                return;
            }
            int target;
            switch (e.KeyCode)
            {
                case Keys.Down: target = _sel + 1; break;
                case Keys.Up: target = _sel < 0 ? 0 : _sel - 1; break;
                case Keys.Home: target = 0; break;
                case Keys.End: target = _items.Count - 1; break;
                case Keys.PageDown: target = Math.Max(_sel + 1, IndexAt(ClientSize.Height - 2)); break;
                case Keys.PageUp: target = Math.Min(_sel - 1, IndexAt(2)); break;
                default: return;
            }
            e.Handled = e.SuppressKeyPress = true;
            Select(Math.Max(0, Math.Min(_items.Count - 1, target)));
        }

        protected override void OnGotFocus(EventArgs e) { base.OnGotFocus(e); Invalidate(); }
        protected override void OnLostFocus(EventArgs e) { base.OnLostFocus(e); Invalidate(); }

        protected override void Dispose(bool disposing)
        {
            if (disposing) _format.Dispose();
            base.Dispose(disposing);
        }
    }
}
