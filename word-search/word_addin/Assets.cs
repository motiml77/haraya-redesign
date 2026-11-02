// הלוגו של התוכנה (אותו סמל כמו של "חיפוש במסמכים"), בכמה גדלים: לכפתור ברצועה ולחלונית.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Reflection;

namespace HebDocSearch.WordAddin
{
    internal static class Assets
    {
        static readonly int[] Sizes = { 32, 48, 64, 96, 128 };
        static readonly Dictionary<int, Bitmap> Cache = new Dictionary<int, Bitmap>();

        /// <summary>הלוגו בגודל px (מהגודל השמור הקרוב שגדול ממנו, מוקטן באיכות גבוהה). עותק חדש בכל קריאה.</summary>
        public static Bitmap Logo(int px)
        {
            px = Math.Max(16, px);
            int source = Sizes[Sizes.Length - 1];
            foreach (int s in Sizes)
                if (s >= px) { source = s; break; }
            Bitmap original = Load(source);
            if (original == null) return new Bitmap(px, px);
            if (source == px) return new Bitmap(original);
            var bmp = new Bitmap(px, px, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
            using (var g = Graphics.FromImage(bmp))
            {
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.CompositingQuality = CompositingQuality.HighQuality;
                g.DrawImage(original, new Rectangle(0, 0, px, px));
            }
            return bmp;
        }

        static Bitmap Load(int size)
        {
            lock (Cache)
            {
                if (Cache.TryGetValue(size, out var b)) return b;
                using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("logo-" + size + ".png"))
                    b = s == null ? null : new Bitmap(s);
                Cache[size] = b;
                return b;
            }
        }

        /// <summary>קנה המידה של המסך הראשי (100% = 1.0).</summary>
        public static float SystemScale
        {
            get
            {
                try
                {
                    using (var g = Graphics.FromHwnd(IntPtr.Zero))
                        return Math.Max(1f, g.DpiX / 96f);
                }
                catch { return 1f; }
            }
        }
    }
}
