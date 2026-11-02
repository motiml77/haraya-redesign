// רשימת התוצאות – בבסיס כמו בחלונית "ניווט" של Word (קווים דקים בין התוצאות, ההתאמה מודגשת),
// ובנוסף: מספר לכל תוצאה, שרשרת הכותרות שהיא נמצאת תחתיהן, והמילים שנמצאו מסומנות במרקר.
//
// מצוירת בקוד ווירטואלית: רק התוצאות שעל המסך מצוירות, והפריסה של כל תוצאה מחושבת פעם אחת
// לכל רוחב (מידות המילים נשמרות) – כך שגם מאות תוצאות מוצגות מיד, בלי לעכב את Word.
//
// הפריסה של הטקסט: פסקה מימין לשמאל; מילים בעברית מימין לשמאל, ורצף מילים באנגלית (עם המספרים
// והפיסוק שביניהן) נשאר רצף משמאל לימין – כמו באלגוריתם הדו-כיווני של Unicode במקרים הנפוצים.
using System;
using System.Collections.Generic;
using System.Drawing;
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
        internal int LayoutWidth = -1, Height, Top, Lines;
        internal List<Piece> Pieces;
    }

    internal struct Piece
    {
        public string Text;
        public int Kind, X, W, Line, Word;
        public bool Rtl;
    }

    internal sealed class ResultList : Control
    {
        Theme _t = Theme.Light;
        Metrics _m;
        List<ResultItem> _items = new List<ResultItem>();
        int _scroll, _contentH, _sel = -1, _hover = -1;
        readonly Dictionary<string, int> _wReg = new Dictionary<string, int>(), _wBold = new Dictionary<string, int>();
        int _space, _resultH, _captionH, _lineH;

        // הודעה כשאין תוצאות (מסך פתיחה / אין תוצאות / שגיאה)
        Bitmap _msgImage;
        string _msgTitle = "";
        string[] _msgLines = new string[0];
        bool _msgWarn;

        // פס הגלילה
        bool _dragging, _thumbHover;
        int _dragStartY, _dragStartScroll;

        public event Action<int> ItemActivated;

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
            _wReg.Clear();
            _wBold.Clear();
            _resultH = Draw.Height(m.Result);
            _captionH = Draw.Height(m.Caption);
            _lineH = (int)Math.Round(_resultH * 1.32);
            _space = Math.Max(1, Draw.Width("א א", m.Result) - 2 * Draw.Width("א", m.Result));
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
            if (index < 0 || index >= _items.Count) return;
            var it = _items[index];
            int margin = _m == null ? 4 : _m.S(4);
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
        int HeaderGap => _m.S(5);
        int TextLeft => Gutter + PadX;
        int TextRight => ClientSize.Width - PadX;
        int TextWidth => Math.Max(_m.S(60), TextRight - TextLeft);

        void Relayout()
        {
            if (_m == null) return;
            int width = TextWidth, top = 0;
            foreach (var it in _items)
            {
                if (it.LayoutWidth != width) LayoutItem(it, width);
                it.Top = top;
                top += it.Height;
            }
            _contentH = top;
            SetScroll(_scroll);
            Invalidate();
        }

        protected override void OnResize(EventArgs e)
        {
            base.OnResize(e);
            Relayout();
            EnsureVisible(_sel);
        }

        // ================================================================ פריסת הטקסט של תוצאה
        static bool IsRtlChar(char c)
        {
            return (c >= '֐' && c <= 'ࣿ') || (c >= 'יִ' && c <= '﷿') || (c >= 'ﹰ' && c <= '﻿');
        }

        const int R = 1, L = 2, EN = 3, N = 0;

        static int StrongOf(string s)
        {
            bool digit = false;
            foreach (char c in s)
            {
                if (IsRtlChar(c)) return R;
                if (char.IsLetter(c)) return L;
                if (char.IsDigit(c)) digit = true;
            }
            return digit ? EN : N;
        }

        int Measure(string text, bool bold)
        {
            var cache = bold ? _wBold : _wReg;
            if (cache.TryGetValue(text, out int w)) return w;
            w = Draw.Width(text, bold ? _m.ResultBold : _m.Result, true);
            if (cache.Count > 20000) cache.Clear();
            cache[text] = w;
            return w;
        }

        bool BoldFor(ResultItem it, int kind) => it.HeadingHit || kind == 1;

        void LayoutItem(ResultItem it, int width)
        {
            // 1. מילים, וכל מילה – חלקים לפי סוג (התאמה יכולה להתחיל או להסתיים באמצע "מילה" עם פיסוק)
            var words = new List<List<KeyValuePair<string, int>>>();
            List<KeyValuePair<string, int>> cur = null;
            var sb = new StringBuilder();
            int kindNow = 0;
            Action flushPiece = () =>
            {
                if (sb.Length == 0) return;
                if (cur == null) cur = new List<KeyValuePair<string, int>>();
                cur.Add(new KeyValuePair<string, int>(sb.ToString(), kindNow));
                sb.Clear();
            };
            Action flushWord = () =>
            {
                flushPiece();
                if (cur != null && cur.Count > 0) words.Add(cur);
                cur = null;
            };
            foreach (var seg in it.Snippet)
            {
                if (seg.Kind == 3)
                {
                    flushWord();
                    words.Add(new List<KeyValuePair<string, int>> { new KeyValuePair<string, int>("¶", 3) });
                    continue;
                }
                foreach (char ch in seg.Text ?? "")
                {
                    if (char.IsWhiteSpace(ch) || ch == ' ') { flushWord(); continue; }
                    if (sb.Length > 0 && kindNow != seg.Kind) flushPiece();
                    kindNow = seg.Kind;
                    sb.Append(ch);
                }
                flushPiece();
            }
            flushWord();

            int n = words.Count;
            var dir = new int[n];
            var wWord = new int[n];
            var pieceW = new List<int[]>(n);
            for (int i = 0; i < n; i++)
            {
                var text = new StringBuilder();
                var ws = new int[words[i].Count];
                for (int k = 0; k < words[i].Count; k++)
                {
                    text.Append(words[i][k].Key);
                    ws[k] = Measure(words[i][k].Key, BoldFor(it, words[i][k].Value));
                    wWord[i] += ws[k];
                }
                pieceW.Add(ws);
                dir[i] = StrongOf(text.ToString());
            }

            // 2. כיוון: מספר אחרי אנגלית – אנגלית; סימן ניטרלי בין שתי מילים באנגלית – אנגלית; אחרת – עברית
            var next = new int[n];
            int strong = R;
            for (int i = n - 1; i >= 0; i--)
            {
                next[i] = strong;
                if (dir[i] == R || dir[i] == L) strong = dir[i];
            }
            strong = R;
            for (int i = 0; i < n; i++)
            {
                if (dir[i] == EN) dir[i] = strong == L ? L : R;
                else if (dir[i] == N) dir[i] = strong == L && next[i] == L ? L : R;
                else strong = dir[i];
            }

            // 3. שבירת שורות
            var line = new int[n];
            int x = 0, ln = 0;
            for (int i = 0; i < n; i++)
            {
                int need = x == 0 ? wWord[i] : x + _space + wWord[i];
                if (need > width && x > 0)
                {
                    ln++;
                    x = wWord[i];
                }
                else x = need;
                line[i] = ln;
            }

            // 4. מיקום: מימין לשמאל, ורצף אנגלית כגוש משמאל לימין
            var wordX = new int[n];
            int idx = 0;
            while (idx < n)
            {
                int l = line[idx], cursor = width, j = idx;
                int end = idx;
                while (end < n && line[end] == l) end++;
                while (j < end)
                {
                    if (dir[j] == R)
                    {
                        wordX[j] = cursor - wWord[j];
                        cursor = wordX[j] - _space;
                        j++;
                    }
                    else
                    {
                        int k = j, runW = 0;
                        while (k < end && dir[k] == L)
                        {
                            runW += wWord[k] + (k > j ? _space : 0);
                            k++;
                        }
                        int left = cursor - runW;
                        for (int q = j; q < k; q++)
                        {
                            wordX[q] = left;
                            left += wWord[q] + _space;
                        }
                        cursor = cursor - runW - _space;
                        j = k;
                    }
                }
                idx = end;
            }

            var pieces = new List<Piece>();
            for (int i = 0; i < n; i++)
            {
                bool rtl = dir[i] == R;
                int px = rtl ? wordX[i] + wWord[i] : wordX[i];
                for (int k = 0; k < words[i].Count; k++)
                {
                    int w = pieceW[i][k];
                    if (rtl) px -= w;
                    pieces.Add(new Piece { Text = words[i][k].Key, Kind = words[i][k].Value, X = px, W = w, Line = line[i], Word = i, Rtl = rtl });
                    if (!rtl) px += w;
                }
            }
            it.Pieces = pieces;
            it.Lines = n == 0 ? 1 : ln + 1;
            it.LayoutWidth = width;
            it.Height = PadTop + HeaderH + HeaderGap + it.Lines * _lineH + PadBottom;
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
                var tr = new Rectangle(TextLeft, top + (HeaderH - BadgeH) / 2, tw, BadgeH);
                Draw.Fill(g, tr, _m.S(4), tagBg);
                Draw.Text(g, tag, _m.Caption, tr, tagFg, 'c');
                limit = tr.Right + _m.S(8);
            }
            PaintPath(g, it, new Rectangle(limit, top, badge.Left - _m.S(8) - limit, HeaderH));

            // ----- הקטע -----
            int textTop = top + HeaderH + HeaderGap;
            int dy = (_lineH - _resultH) / 2;
            var pieces = it.Pieces;
            int pad = _m.S(2);
            for (int i = 0; i < pieces.Count; i++)                   // מרקר מתחת לטקסט, רציף בין מילים צמודות
            {
                var p = pieces[i];
                if (p.Kind != 1) continue;
                int py = textTop + p.Line * _lineH + dy;
                var r = new Rectangle(TextLeft + p.X - pad, py - _m.S(1), p.W + 2 * pad, _resultH + _m.S(2));
                if (i + 1 < pieces.Count)
                {
                    var q = pieces[i + 1];
                    if (q.Kind == 1 && q.Line == p.Line && q.Word != p.Word)
                    {
                        // הרווח שבין שתי מילים מסומנות צמודות (בעברית הבאה משמאל, באנגלית – מימין)
                        int gapL = p.X <= q.X ? p.X + p.W : q.X + q.W;
                        int gapR = p.X <= q.X ? q.X : p.X;
                        if (gapR >= gapL && gapR - gapL <= _space + 2 * pad)
                            using (var mb = new SolidBrush(_t.Marker))
                                g.FillRectangle(mb, new Rectangle(TextLeft + gapL, r.Y, gapR - gapL, r.Height));
                    }
                }
                Draw.Fill(g, r, _m.S(3), _t.Marker);
            }
            foreach (var p in pieces)
            {
                int py = textTop + p.Line * _lineH + dy;
                Color fg = p.Kind == 1 ? _t.MarkerText : p.Kind == 2 ? _t.TextFaint : p.Kind == 3 ? _t.Pilcrow : _t.Text;
                var font = BoldFor(it, p.Kind) ? _m.ResultBold : _m.Result;
                var r = new Rectangle(TextLeft + p.X, py, p.W + 1, _resultH);
                if (r.Right > TextRight + _m.S(2) || r.Left < TextLeft - _m.S(2))
                    r.Intersect(new Rectangle(TextLeft, py, TextWidth, _resultH));
                TextRenderer.DrawText(g, p.Text, font, r, fg, (p.Rtl ? Draw.Rtl | TextFormatFlags.Right : Draw.Plain | TextFormatFlags.Left) | TextFormatFlags.EndEllipsis);
            }

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
            const string sep = "‹";
            int sepW = Draw.Width(sep, _m.Caption, false) + _m.S(10);
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
            Action<string, Font, Color, int, bool> put = (text, font, color, w, rtl) =>
            {
                w = Math.Min(w, xr - area.Left);
                if (w <= 0) return;
                Draw.Text(g, text, font, new Rectangle(xr - w, area.Y, w, area.Height), color, 'r', rtl);
                xr -= w;
            };
            if (start > 0)
            {
                put("…", _m.Caption, _t.TextFaint, ellW, false);
                put(sep, _m.Caption, _t.TextFaint, sepW, false);
            }
            for (int i = start; i < path.Length; i++)
            {
                bool last = i == path.Length - 1;
                put(path[i], last ? _m.CaptionBold : _m.Caption, last ? _t.Heading : _t.TextDim, widths[i] + 1, true);
                if (!last) put(sep, _m.Caption, _t.TextFaint, sepW, false);
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
                g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
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
            if (e.Button != MouseButtons.Left || _m == null) return;
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
                ItemActivated?.Invoke(i);
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
            SetScroll(_scroll - e.Delta * lines * _lineH / 120);
        }

        protected override bool IsInputKey(Keys keyData)
        {
            switch (keyData & Keys.KeyCode)
            {
                case Keys.Up: case Keys.Down: case Keys.PageUp: case Keys.PageDown: case Keys.Home: case Keys.End: case Keys.Enter:
                    return true;
            }
            return base.IsInputKey(keyData);
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            base.OnKeyDown(e);
            if (_items.Count == 0) return;
            int target = _sel;
            switch (e.KeyCode)
            {
                case Keys.Down: target = _sel + 1; break;
                case Keys.Up: target = _sel - 1; break;
                case Keys.Home: target = 0; break;
                case Keys.End: target = _items.Count - 1; break;
                case Keys.PageDown: target = Math.Max(_sel + 1, IndexAt(ClientSize.Height - 2)); break;
                case Keys.PageUp: target = Math.Min(_sel - 1, IndexAt(2)); break;
                case Keys.Enter: target = _sel + (e.Shift ? -1 : 1); break;
                default: return;
            }
            e.Handled = e.SuppressKeyPress = true;
            target = Math.Max(0, Math.Min(_items.Count - 1, target));
            if (target == _sel && e.KeyCode != Keys.Enter) return;
            Select(target);
            ItemActivated?.Invoke(target);
        }

        protected override void OnGotFocus(EventArgs e) { base.OnGotFocus(e); Invalidate(); }
        protected override void OnLostFocus(EventArgs e) { base.OnLostFocus(e); Invalidate(); }
    }
}
