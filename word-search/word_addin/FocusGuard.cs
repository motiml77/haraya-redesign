// שמירה על המיקוד: חלק מהפעולות במודל של Word (חיפוש Find, קריאת טקסט, בחירה) מעבירות את המיקוד של
// המקלדת מהחלונית חזרה למסמך – ואז מה שהמשתמש מקליד בשדה החיפוש נכתב בתוך המסמך.
// כל פעולה כזו עטופה כאן: אם המיקוד היה באחד הפקדים של התוסף – הוא מוחזר אליו מיד, לפני שהמקשים
// הבאים מטופלים.
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
            bool ours = before != IntPtr.Zero && Control.FromChildHandle(before) != null;
            try { action(); }
            finally
            {
                if (ours && GetFocus() != before)
                {
                    SetFocus(before);
                    Log.Write("focus returned to the pane");
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
