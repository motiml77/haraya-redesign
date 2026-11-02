// מערכת העיצוב של החלונית.
//
// הבסיס הוא חלונית "ניווט" של Word עצמו – אותם צבעים לכל ערכת נושא של Office (אפור כהה, שחור,
// צבעוני/לבן), כדי שהחלונית תיראה חלק מ-Word. הצבעים של "אפור כהה" נדגמו מהחלונית של Word.
// כל המידות בפיקסלים לוגיים (כמו ב-100%) ומוכפלות בקנה המידה של המסך, והגופנים בפיקסלים
// מאותו קנה מידה – כך שבכל DPI הפרופורציות זהות ושום דבר לא נחתך.
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;
using Microsoft.Win32;

namespace HebDocSearch.WordAddin
{
    internal sealed class Theme
    {
        public string Name;
        public bool Dark;
        public Color PaneBg, Text, TextDim, TextFaint, Heading;
        public Color FieldBg, FieldBorder, FieldHover, FieldFocus, FieldText, FieldHint, FieldIcon;
        public Color Separator, Accent, OnAccent;
        public Color ItemHover, ItemSel, SelBar, BadgeBg, BadgeText;
        public Color BtnBg, BtnBorder, BtnHover, BtnGlyph, BtnGlyphOff;
        public Color ChipBorder, ChipHover, ChipText, ChipKey, ChipOnBg, ChipOnBorder, ChipOnText;
        public Color ScrollTrack, ScrollThumb, ScrollThumbHover;
        public Color Marker, MarkerText, Warn, WarnBg, Pilcrow;
        public Color MenuBg, MenuText, MenuDim, MenuSel, MenuBorder;

        static Color H(string s) => ColorTranslator.FromHtml(s);

        /// <summary>"אפור כהה" – הצבעים של חלונית הניווט של Word בערכה הזו.</summary>
        public static readonly Theme DarkGray = new Theme
        {
            Name = "darkgray", Dark = true,
            PaneBg = H("#525252"), Text = H("#f0f0f0"), TextDim = H("#cfcfcf"), TextFaint = H("#a8a8a8"), Heading = H("#ffffff"),
            FieldBg = H("#d4d4d4"), FieldBorder = H("#ababab"), FieldHover = H("#dcdcdc"), FieldFocus = H("#82abf1"),
            FieldText = H("#262626"), FieldHint = H("#5f5f5f"), FieldIcon = H("#3a3a3a"),
            Separator = H("#ababab"), Accent = H("#82abf1"), OnAccent = H("#1f1f1f"),
            ItemHover = H("#5c5c5c"), ItemSel = H("#686868"), SelBar = H("#82abf1"), BadgeBg = H("#686868"), BadgeText = H("#f0f0f0"),
            BtnBg = H("#d4d4d4"), BtnBorder = H("#ababab"), BtnHover = H("#e4e4e4"), BtnGlyph = H("#303030"), BtnGlyphOff = H("#8c8c8c"),
            ChipBorder = H("#8a8a8a"), ChipHover = H("#5e5e5e"), ChipText = H("#f5f5f5"), ChipKey = H("#cfcfcf"),
            ChipOnBg = H("#4a5a78"), ChipOnBorder = H("#82abf1"), ChipOnText = H("#dce8ff"),
            ScrollTrack = H("#3d3d3d"), ScrollThumb = H("#c7c7c7"), ScrollThumbHover = H("#e2e2e2"),
            Marker = H("#f5d547"), MarkerText = H("#1a1a1a"), Warn = H("#ffd27a"), WarnBg = H("#6a5a33"), Pilcrow = H("#9a9a9a"),
            MenuBg = H("#444444"), MenuText = H("#f0f0f0"), MenuDim = H("#b8b8b8"), MenuSel = H("#5e5e5e"), MenuBorder = H("#6e6e6e"),
        };

        public static readonly Theme Black = new Theme
        {
            Name = "black", Dark = true,
            PaneBg = H("#262626"), Text = H("#f0f0f0"), TextDim = H("#c4c4c4"), TextFaint = H("#949494"), Heading = H("#ffffff"),
            FieldBg = H("#3a3a3a"), FieldBorder = H("#6b6b6b"), FieldHover = H("#424242"), FieldFocus = H("#82abf1"),
            FieldText = H("#f0f0f0"), FieldHint = H("#a6a6a6"), FieldIcon = H("#d6d6d6"),
            Separator = H("#4d4d4d"), Accent = H("#82abf1"), OnAccent = H("#1a1a1a"),
            ItemHover = H("#313131"), ItemSel = H("#3d3d3d"), SelBar = H("#82abf1"), BadgeBg = H("#3d3d3d"), BadgeText = H("#f0f0f0"),
            BtnBg = H("#3a3a3a"), BtnBorder = H("#6b6b6b"), BtnHover = H("#474747"), BtnGlyph = H("#f0f0f0"), BtnGlyphOff = H("#777777"),
            ChipBorder = H("#5c5c5c"), ChipHover = H("#333333"), ChipText = H("#f0f0f0"), ChipKey = H("#bdbdbd"),
            ChipOnBg = H("#22324f"), ChipOnBorder = H("#82abf1"), ChipOnText = H("#cfe0ff"),
            ScrollTrack = H("#1f1f1f"), ScrollThumb = H("#7d7d7d"), ScrollThumbHover = H("#a0a0a0"),
            Marker = H("#f5d547"), MarkerText = H("#1a1a1a"), Warn = H("#ffcf7a"), WarnBg = H("#4a3d1f"), Pilcrow = H("#7a7a7a"),
            MenuBg = H("#2f2f2f"), MenuText = H("#f0f0f0"), MenuDim = H("#a8a8a8"), MenuSel = H("#424242"), MenuBorder = H("#4d4d4d"),
        };

        /// <summary>"צבעוני" ו"לבן" – חלונית בהירה.</summary>
        public static readonly Theme Light = new Theme
        {
            Name = "light", Dark = false,
            PaneBg = H("#ffffff"), Text = H("#262626"), TextDim = H("#5c5c5c"), TextFaint = H("#8a8886"), Heading = H("#1e3a8a"),
            FieldBg = H("#ffffff"), FieldBorder = H("#ababab"), FieldHover = H("#ffffff"), FieldFocus = H("#185abd"),
            FieldText = H("#262626"), FieldHint = H("#6e6e6e"), FieldIcon = H("#444444"),
            Separator = H("#e1dfdd"), Accent = H("#185abd"), OnAccent = H("#ffffff"),
            ItemHover = H("#f5f5f5"), ItemSel = H("#e8f0fc"), SelBar = H("#185abd"), BadgeBg = H("#edebe9"), BadgeText = H("#323130"),
            BtnBg = H("#ffffff"), BtnBorder = H("#c8c6c4"), BtnHover = H("#f3f2f1"), BtnGlyph = H("#323130"), BtnGlyphOff = H("#b3b0ad"),
            ChipBorder = H("#c8c6c4"), ChipHover = H("#f3f2f1"), ChipText = H("#262626"), ChipKey = H("#605e5c"),
            ChipOnBg = H("#e8f0fc"), ChipOnBorder = H("#9cbbe9"), ChipOnText = H("#185abd"),
            ScrollTrack = H("#f3f2f1"), ScrollThumb = H("#c8c6c4"), ScrollThumbHover = H("#a19f9d"),
            Marker = H("#ffe94a"), MarkerText = H("#1c2330"), Warn = H("#a55a00"), WarnBg = H("#fdf0d5"), Pilcrow = H("#b4bcc9"),
            MenuBg = H("#ffffff"), MenuText = H("#262626"), MenuDim = H("#707070"), MenuSel = H("#f0f0f0"), MenuBorder = H("#c8c6c4"),
        };

        /// <summary>ערכת הנושא הנוכחית של Office (קובץ ← חשבון ← ערכת נושא של Office).
        /// 0 צבעוני, 3 אפור כהה, 4 שחור, 5 לבן, 6 לפי הגדרות המערכת.</summary>
        public static Theme Current()
        {
            int value = OfficeThemeValue();
            switch (value)
            {
                case 3: return DarkGray;
                case 4: return Black;
                case 6: return WindowsAppsDark() ? Black : Light;
                default: return Light;
            }
        }

        static int OfficeThemeValue()
        {
            try
            {
                // Microsoft 365 שומר את הבחירה בהגדרות המסונכרנות (מזהה 1186); גרסאות אחרות – ב-Common\UI Theme
                using (var ids = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Office\16.0\Common\Roaming\Identities"))
                {
                    if (ids != null)
                        foreach (string id in ids.GetSubKeyNames())
                            using (var k = ids.OpenSubKey(id + @"\Settings\1186\{00000000-0000-0000-0000-000000000000}"))
                                if (k?.GetValue("Data") is byte[] data && data.Length >= 4)
                                    return BitConverter.ToInt32(data, 0);
                }
                using (var k = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Office\16.0\Common"))
                    if (k?.GetValue("UI Theme") is int v) return v;
            }
            catch { }
            return 0;
        }

        static bool WindowsAppsDark()
        {
            try
            {
                using (var k = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"))
                    return k?.GetValue("AppsUseLightTheme") is int v && v == 0;
            }
            catch { return false; }
        }
    }

    /// <summary>מידות וגופנים לפי קנה מידה. מופע אחד לכל חלונית; נבנה מחדש כשה-DPI משתנה.</summary>
    internal sealed class Metrics : IDisposable
    {
        public const string Family = "Segoe UI";
        public readonly float Scale;
        public readonly Font Caption, CaptionBold, Body, BodyBold, Input, Count, Result, ResultBold, Hero;

        /// <summary>קנה מידה מאולץ (לתצוגה מקדימה בבנייה); 0 = לפי המסך.</summary>
        public static float Override { get; set; }

        public Metrics(float scale)
        {
            Scale = Override > 0 ? Override : Math.Max(1f, scale);
            Caption = F(12);
            CaptionBold = F(12, FontStyle.Bold);
            Body = F(13);
            BodyBold = F(13, FontStyle.Bold);
            Input = F(14);
            Count = F(14);
            Result = F(15);
            ResultBold = F(15, FontStyle.Bold);
            Hero = F(16, FontStyle.Bold);
        }

        Font F(float px, FontStyle style = FontStyle.Regular)
        {
            return new Font(Family, px * Scale, style, GraphicsUnit.Pixel);
        }

        /// <summary>מידה לוגית (פיקסלים ב-100%) → פיקסלים במסך.</summary>
        public int S(float px) => (int)Math.Round(px * Scale);

        public static float ScaleOf(Control c)
        {
            try
            {
                using (var g = c.CreateGraphics())
                    return g.DpiX / 96f;
            }
            catch { return 1f; }
        }

        public void Dispose()
        {
            foreach (var f in new[] { Caption, CaptionBold, Body, BodyBold, Input, Count, Result, ResultBold, Hero })
                f.Dispose();
        }
    }

    /// <summary>ציור: מלבנים מעוגלים, סמלים קטנים וטקסט בכיוון הנכון.</summary>
    internal static class Draw
    {
        public const TextFormatFlags Plain = TextFormatFlags.NoPrefix | TextFormatFlags.NoPadding | TextFormatFlags.SingleLine;
        public const TextFormatFlags Rtl = Plain | TextFormatFlags.RightToLeft;

        public static GraphicsPath Round(RectangleF r, float radius)
        {
            var path = new GraphicsPath();
            float d = Math.Min(radius * 2, Math.Min(r.Width, r.Height));
            if (d <= 1)
            {
                path.AddRectangle(r);
                return path;
            }
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }

        public static void Box(Graphics g, RectangleF r, float radius, Color fill, Color border, float width = 1f)
        {
            var old = g.SmoothingMode;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            var inner = border.A > 0 && width > 0
                ? new RectangleF(r.X + width / 2, r.Y + width / 2, r.Width - width, r.Height - width)
                : r;
            using (var path = Round(inner, radius))
            {
                if (fill.A > 0)
                    using (var b = new SolidBrush(fill)) g.FillPath(b, path);
                if (border.A > 0 && width > 0)
                    using (var p = new Pen(border, width)) g.DrawPath(p, path);
            }
            g.SmoothingMode = old;
        }

        public static void Fill(Graphics g, RectangleF r, float radius, Color fill)
        {
            Box(g, r, radius, fill, Color.Empty, 0);
        }

        static Pen RoundPen(Color color, float stroke)
        {
            return new Pen(color, stroke) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round };
        }

        public static void Magnifier(Graphics g, RectangleF box, Color color, float stroke)
        {
            var old = g.SmoothingMode;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            float s = Math.Min(box.Width, box.Height);
            float r = s * 0.30f;
            float cx = box.X + box.Width / 2 + s * 0.08f, cy = box.Y + box.Height / 2 - s * 0.08f;
            using (var p = RoundPen(color, stroke))
            {
                g.DrawEllipse(p, cx - r, cy - r, 2 * r, 2 * r);
                const float k = 0.7071f;
                g.DrawLine(p, cx - r * k, cy + r * k, cx - s * 0.40f, cy + s * 0.40f);   // ידית לשמאל-למטה, כמו ב-Word בעברית
            }
            g.SmoothingMode = old;
        }

        public static void Cross(Graphics g, RectangleF box, Color color, float stroke)
        {
            var old = g.SmoothingMode;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            float s = Math.Min(box.Width, box.Height) * 0.26f;
            float cx = box.X + box.Width / 2, cy = box.Y + box.Height / 2;
            using (var p = RoundPen(color, stroke))
            {
                g.DrawLine(p, cx - s, cy - s, cx + s, cy + s);
                g.DrawLine(p, cx - s, cy + s, cx + s, cy - s);
            }
            g.SmoothingMode = old;
        }

        /// <summary>חץ קטן: 'd' ⌄, 'u' ⌃, 'l' ‹, 'r' ›.</summary>
        public static void Chevron(Graphics g, RectangleF box, Color color, float stroke, char dir)
        {
            var old = g.SmoothingMode;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            float s = Math.Min(box.Width, box.Height) * 0.24f;
            float cx = box.X + box.Width / 2, cy = box.Y + box.Height / 2;
            PointF[] pts;
            switch (dir)
            {
                case 'd': pts = new[] { new PointF(cx - s, cy - s / 2), new PointF(cx, cy + s / 2), new PointF(cx + s, cy - s / 2) }; break;
                case 'u': pts = new[] { new PointF(cx - s, cy + s / 2), new PointF(cx, cy - s / 2), new PointF(cx + s, cy + s / 2) }; break;
                case 'l': pts = new[] { new PointF(cx + s / 2, cy - s), new PointF(cx - s / 2, cy), new PointF(cx + s / 2, cy + s) }; break;
                default: pts = new[] { new PointF(cx - s / 2, cy - s), new PointF(cx + s / 2, cy), new PointF(cx - s / 2, cy + s) }; break;
            }
            using (var p = RoundPen(color, stroke))
                g.DrawLines(p, pts);
            g.SmoothingMode = old;
        }

        public static void Check(Graphics g, RectangleF box, Color color, float stroke)
        {
            var old = g.SmoothingMode;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            float w = box.Width, h = box.Height;
            var pts = new[]
            {
                new PointF(box.X + w * 0.20f, box.Y + h * 0.52f),
                new PointF(box.X + w * 0.42f, box.Y + h * 0.74f),
                new PointF(box.X + w * 0.80f, box.Y + h * 0.28f),
            };
            using (var p = RoundPen(color, stroke))
                g.DrawLines(p, pts);
            g.SmoothingMode = old;
        }

        /// <summary>טקסט בשורה אחת בתוך מלבן, מיושר לימין (או לשמאל / למרכז), עם … כשאין מקום.</summary>
        public static void Text(Graphics g, string text, Font font, Rectangle r, Color color, char align = 'r', bool rtl = true)
        {
            var flags = (rtl ? Rtl : Plain) | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis;
            flags |= align == 'l' ? TextFormatFlags.Left : align == 'c' ? TextFormatFlags.HorizontalCenter : TextFormatFlags.Right;
            TextRenderer.DrawText(g, text, font, r, color, flags);
        }

        public static int Width(string text, Font font, bool rtl = true)
        {
            if (string.IsNullOrEmpty(text)) return 0;
            return TextRenderer.MeasureText(text, font, new Size(int.MaxValue, int.MaxValue), rtl ? Rtl : Plain).Width;
        }

        public static int Height(Font font)
        {
            return TextRenderer.MeasureText("אבג Ag", font, new Size(int.MaxValue, int.MaxValue), Plain).Height;
        }

        public static Color Mix(Color a, Color b, float t)
        {
            return Color.FromArgb(
                (int)Math.Round(a.R + (b.R - a.R) * t),
                (int)Math.Round(a.G + (b.G - a.G) * t),
                (int)Math.Round(a.B + (b.B - a.B) * t));
        }
    }

    internal static class Words
    {
        public static string Count(int n, string one, string many)
        {
            return n == 1 ? one : n.ToString("N0") + " " + many;
        }

        public static string Paragraphs(int n) => n == 0 ? "אין פסקאות" : Count(n, "פסקה אחת", "פסקאות");
        public static string Headings(int n) => n == 0 ? "אין כותרות" : Count(n, "כותרת אחת", "כותרות");
        public static string Results(int n) => n == 0 ? "אין תוצאות" : Count(n, "תוצאה אחת", "תוצאות");
    }
}
