// מצייר את חלונית התוסף (PaneView) עם תוצאות לדוגמה לתמונות PNG – בלי Word.
//   PanePreview.exe <תיקיית פלט>
// לכל ערכת נושא (אפור כהה / בהיר / שחור) ולכל גודל (100%, 200%): פתיחה, תוצאות, כותרות בלבד,
// אין תוצאות, ותפריט אפשרויות פתוח.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Windows.Forms;

namespace HebDocSearch.WordAddin
{
    static class Preview
    {
        static string _out;

        [STAThread]
        static int Main(string[] args)
        {
            _out = args.Length > 0 ? args[0] : "preview";
            Directory.CreateDirectory(_out);
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            try
            {
                foreach (var (theme, scales) in new[] { (Theme.DarkGray, new[] { 1f, 2f }), (Theme.Light, new[] { 1f }), (Theme.Black, new[] { 1f }) })
                    foreach (float scale in scales)
                    {
                        Metrics.Override = scale;
                        string tag = $"{theme.Name}-{(int)(scale * 100)}";
                        Render(tag + "-1-idle", theme, scale, v => v.ShowIdle("המסמך מוכן לחיפוש · 1,234 פסקאות · 56 כותרות"));
                        Render(tag + "-2-results", theme, scale, v =>
                        {
                            v.Query = "קלתה";
                            v.ShowResults(Sample(false), 16, "נמצא: קלתה 9 · בקלתה 5 · הקלתה 2");
                            v.SetTabCount(true, 2);
                            v.SetCurrent(1, 8);
                        });
                        Render(tag + "-3-headings", theme, scale, v =>
                        {
                            v.Query = "הלכות";
                            v.HeadingsOnly = true;
                            v.ShowResults(Sample(true), 3, "");
                            v.SetTabCount(false, 41);
                            v.SetCurrent(0, 3);
                        });
                        Render(tag + "-4-empty", theme, scale, v =>
                        {
                            v.Query = "איסור ייחוד";
                            v.SetOptions(0, 0, 0, 3, true, false);
                            v.ShowMessage(Words.Results(0), "לא נמצאו תוצאות", new[]
                            {
                                "אפשר להרחיב: מילים ← כל ההטיות.", "או: מילים ← כתיב מלא וחסר.", "או: מרחק ← באותה פסקה.",
                            }, false);
                        });
                        Render(tag + "-5-menu", theme, scale, v =>
                        {
                            v.Query = "הולך בדרך";
                            v.ShowIdle("המסמך מוכן לחיפוש · 1,234 פסקאות · 56 כותרות");
                        }, menu: true);
                        RenderWindow(tag + "-7-window", theme, scale);
                        Render(tag + "-6-distance", theme, scale, v =>
                        {
                            v.Query = "הולך בדרך";
                            v.SetOptions(1, 0, 1, 3, true, false);
                            v.ShowIdle("המסמך מוכן לחיפוש · 1,234 פסקאות · 56 כותרות");
                        }, menu: true, distance: true);
                    }
                return 0;
            }
            catch (Exception e)
            {
                File.WriteAllText(Path.Combine(_out, "error.txt"), e.ToString());
                Console.Error.WriteLine(e);
                return 1;
            }
        }

        static void Render(string name, Theme theme, float scale, Action<PaneView> setup, bool menu = false, bool distance = false)
        {
            int w = (int)(400 * scale), h = (int)(860 * scale);
            using (var form = new BigForm
            {
                FormBorderStyle = FormBorderStyle.None,
                StartPosition = FormStartPosition.Manual,
                Location = menu ? new Point(0, 0) : new Point(-10000, -10000),
                ClientSize = new Size(w, h),
                ShowInTaskbar = false,
                TopMost = menu,
            })
            {
                var view = new PaneView { Dock = DockStyle.Fill };
                form.Controls.Add(view);
                form.Show();
                form.ClientSize = new Size(w, h);
                view.ApplyTheme(theme, true);
                setup(view);
                Pump();
                using (var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb))
                {
                    view.DrawToBitmap(bmp, new Rectangle(0, 0, w, h));
                    bmp.Save(Path.Combine(_out, name + ".png"), ImageFormat.Png);
                }
                if (menu)
                {
                    // התפריט הוא חלון נפרד – מצלמים את המסך (אם יש שולחן עבודה גלוי)
                    view.OpenMenuForPreview(distance);
                    Pump();
                    try
                    {
                        using (var bmp = new Bitmap(w, h))
                        using (var g = Graphics.FromImage(bmp))
                        {
                            g.CopyFromScreen(form.Location, Point.Empty, new Size(w, h));
                            bmp.Save(Path.Combine(_out, name + "-screen.png"), ImageFormat.Png);
                        }
                    }
                    catch (Exception e) { File.WriteAllText(Path.Combine(_out, name + "-screen.txt"), e.Message); }
                    view.CloseMenuForPreview();
                    Pump();
                }
                form.Close();
            }
        }

        /// <summary>חלון שמותר לו להיות גדול מהמסך (במכונת הבנייה המסך קטן), כדי לצלם את כל החלונית.</summary>
        sealed class BigForm : Form
        {
            protected override void WndProc(ref Message m)
            {
                base.WndProc(ref m);
                if (m.Msg == 0x0024)          // WM_GETMINMAXINFO
                {
                    var info = (MINMAXINFO)System.Runtime.InteropServices.Marshal.PtrToStructure(m.LParam, typeof(MINMAXINFO));
                    info.ptMaxSize = info.ptMaxTrackSize = new POINT { X = 8000, Y = 8000 };
                    System.Runtime.InteropServices.Marshal.StructureToPtr(info, m.LParam, false);
                }
            }

            [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
            struct POINT { public int X, Y; }

            [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
            struct MINMAXINFO { public POINT ptReserved, ptMaxSize, ptMaxPosition, ptMinTrackSize, ptMaxTrackSize; }
        }

        /// <summary>"הצג בחלון נפרד": החלון עם כ-70 מילים סביב תוצאה (מפסקה ארוכה וקצרות סביבה).</summary>
        static void RenderWindow(string name, Theme theme, float scale)
        {
            var texts = new List<string>
            {
                "פרק ג – כתובות",
                "ובמשנה (כתובות ע\"ב ע\"א) מנו את הדברים שבהם אשה עוברת על דת משה ודת יהודית ויוצאת שלא בכתובה.",
                "ברה\"ר – אם יצאה בקלתה מפסדת כתובתה, כי עברה על 'דת יהודית'. במבוי – אם יצאה ב'קלתה' לא עברה אפילו על דת יהודית – משמע שמותר, ובחצר אין בזה שום חשש כלל, כמבואר בגמרא ובראשונים שם, ועיין עוד בשולחן ערוך אבן העזר סימן קט\"ו.",
                "ראה במהדורת Microsoft Word 2016, עמ' 120–125.",
            };
            string p = texts[2];
            int a = p.IndexOf("קלתה");
            var ex = Excerpt.Build(texts, 2, new List<int[]> { new[] { a, a + 4 } }, 35, 35);
            Metrics.Override = scale;
            using (var win = new ContextWindow(theme, scale, 3, new[] { "פרק ג – כתובות", "דת יהודית" }, ex, () => { }))
            {
                win.Location = new Point(-10000, -10000);
                win.Show();
                Pump();
                using (var bmp = new Bitmap(win.Width, win.Height, PixelFormat.Format32bppArgb))
                {
                    win.DrawToBitmap(bmp, new Rectangle(0, 0, win.Width, win.Height));
                    bmp.Save(Path.Combine(_out, name + ".png"), ImageFormat.Png);
                }
                win.Close();
            }
        }

        static void Pump()
        {
            for (int i = 0; i < 20; i++)
            {
                Application.DoEvents();
                System.Threading.Thread.Sleep(15);
            }
        }

        static ResultItem Item(int n, string[] path, params object[] parts)
        {
            var it = new ResultItem { Number = n, Path = path, Terms = 1, Covered = 1, NoPathText = "לפני הכותרת הראשונה" };
            for (int i = 0; i < parts.Length; i += 2)
                it.Snippet.Add(new Seg { Text = (string)parts[i], Kind = (int)parts[i + 1] });
            return it;
        }

        static List<ResultItem> Sample(bool headings)
        {
            if (headings)
            {
                var h = new List<ResultItem>
                {
                    Item(1, new string[0], "", 0, "הלכות", 1, " שבת", 0),
                    Item(2, new[] { "הלכות שבת" }, "מ", 0, "הלכות", 1, " יום טוב ודיני מוקצה", 0),
                    Item(3, new[] { "הלכות שבת", "מהלכות יום טוב ודיני מוקצה" }, "סיכום ה", 0, "הלכות", 1, " – טבלה (Table 3)", 0),
                };
                h[0].Level = 1; h[1].Level = 2; h[2].Level = 3;
                foreach (var it in h) { it.HeadingHit = true; it.NoPathText = ""; }
                return h;
            }
            var items = new List<ResultItem>
            {
                Item(1, new[] { "פרק ג – כתובות", "דת יהודית" },
                     "ברה\"ר – אם יצאה ב", 0, "קלתה", 1, " מפסדת כתובתה, כי עברה על 'דת יהודית'. במבוי – אם יצאה ב'", 0, "קלתה", 1, "' לא עברה אפילו", 0),
                Item(2, new[] { "פרק ג – כתובות", "דת יהודית" },
                     "…כי עברה על 'דת יהודית'. במבוי – אם יצאה ב'", 0, "קלתה", 1, "' לא עברה אפילו על דת יהודית – משמע שמותר", 0),
                Item(3, new[] { "פרק ג – כתובות", "מנהג המקום" },
                     "מנהג 'דת יהודית' יכול להשתנות שגם ברה\"ר לא צריך ", 0, "קלתה", 1, "? ר\"י מלוניל: \"דת יהודית, דברים שאינן אסורין", 0),
                Item(4, new[] { "חלק ב", "פרק ד – שיטות הראשונים בפירוש הסוגיא", "שיטת הרמב\"ם", "פירוש המילה" },
                     "ח: \"ומדברי הרמב\"ם (אישות פכ\"ד הי\"ב) נראה דפירש ", 0, "קלתה", 1, " היא מטפחת שיש בה נקבים כנקבי הסל כמו הסבכות.\"", 0),
                Item(5, new[] { "נספחים" },
                     "ראה במהדורת Microsoft Word 2016, עמ' 120–125, שם מובא ", 0, "בקלתה", 1, " בשם ה-Oxford English Dictionary (מהדורה 2).", 0),
                Item(6, new string[0], "בהקדמה: ", 0, "איסור", 1, " ", 0, "ייחוד", 1, " נזכר כאן בקצרה", 0, " ¶ ", 3, "ובפסקה הבאה נדון בו בהרחבה.", 0),
                Item(7, new[] { "פרק ה" }, "מבוי דמשום בני מבוי איכא משום פריעת ראש ואי ", 0, "קלתה", 1, " בראשה שפיר דמי שהרי אינה שוה כלום ואין", 0),
                Item(8, new[] { "פרק ה", "סיכום" }, "וּבְ", 0, "קַלְתָּהּ", 1, " – בניקוד מלא, כמו בכתבי יד.", 0),
            };
            items[5].Terms = 2; items[5].Covered = 2;
            items[6].Terms = 2; items[6].Covered = 1;
            return items;
        }
    }
}
