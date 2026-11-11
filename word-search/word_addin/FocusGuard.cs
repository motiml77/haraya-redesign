// שמירה על המיקוד: חלק מהפעולות במודל של Word (קריאת טקסט, בחירה) עלולות להעביר את המיקוד של המקלדת
// למסמך – ואז מה שהמשתמש מקליד בשדה החיפוש נכתב בתוך המסמך.
// כל פעולה כזו עטופה כאן: אם המיקוד זז בזמן הפעולה – הוא מוחזר מיד למקום שבו היה, לפני שהמקשים הבאים
// מטופלים. זה חל על כל חלון של Word, לא רק על החלונית שלנו – גם על שדה החיפוש של Word עצמו (חלונית
// הניווט), כדי שעבודה ברקע לא תפריע לחיפוש שהמשתמש עושה שם.
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace HebDocSearch.WordAddin
{
    internal static class FocusGuard
    {
        [DllImport("user32.dll")]
        static extern IntPtr GetFocus();

        [DllImport("user32.dll")]
        static extern IntPtr SetFocus(IntPtr hWnd);

        [DllImport("user32.dll")]
        static extern bool IsWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        static extern bool IsWindowVisible(IntPtr hWnd);

        /// <summary>האם המיקוד כרגע באחד הפקדים של התוסף (שדה החיפוש, הרשימה…).</summary>
        public static bool InAddIn
        {
            get
            {
                IntPtr f = GetFocus();
                return f != IntPtr.Zero && Control.FromChildHandle(f) != null;
            }
        }

        public static void Run(Action action)
        {
            IntPtr before = GetFocus();
            try { action(); }
            finally
            {
                if (before != IntPtr.Zero && GetFocus() != before && IsWindow(before) && IsWindowVisible(before))
                {
                    SetFocus(before);
                    Log.Write(Control.FromChildHandle(before) != null ? "focus returned to the pane" : "focus returned to Word");
                }
            }
        }

        public static T Run<T>(Func<T> func)
        {
            T result = default(T);
            Run(() => { result = func(); });
            return result;
        }
    }
}
