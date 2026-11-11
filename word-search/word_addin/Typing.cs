// מתי המשתמש הקליד בפעם האחרונה – רק מקלדת, לא עכבר. ההכנה ברקע עוצרת רק בזמן כתיבה; תזוזת עכבר או
// גלילה לא עוצרות אותה (רק מקצרות את המנות, כדי שהמסך יישאר חלק).
// "וו" (hook) של מקלדת על התהליכון של Word בלבד (WH_KEYBOARD עם מזהה התהליכון) – רואה רק הקשות
// בחלונות של Word ושל החלונית, לא בתוכנות אחרות, ולא עושה בהן כלום חוץ מלרשום את השעה.
using System;
using System.Runtime.InteropServices;

namespace HebDocSearch.WordAddin
{
    internal static class Typing
    {
        delegate IntPtr HookProc(int code, IntPtr wParam, IntPtr lParam);

        const int WH_KEYBOARD = 2;
        static HookProc _proc;                   // נשמר כדי שאוסף הזבל לא ישחרר אותו
        static IntPtr _hook;
        static int _lastKey = Environment.TickCount - 60000;

        public static bool Active => _hook != IntPtr.Zero;

        public static void Start()
        {
            if (_hook != IntPtr.Zero) return;
            try
            {
                _proc = OnKey;
                _hook = SetWindowsHookEx(WH_KEYBOARD, _proc, IntPtr.Zero, GetCurrentThreadId());
                if (_hook == IntPtr.Zero) Log.Write("typing: keyboard hook not available (" + Marshal.GetLastWin32Error() + ") – using all input");
            }
            catch (Exception e)
            {
                Log.Error("typing", e);
            }
        }

        public static void Stop()
        {
            if (_hook == IntPtr.Zero) return;
            try { UnhookWindowsHookEx(_hook); } catch { }
            _hook = IntPtr.Zero;
        }

        static IntPtr OnKey(int code, IntPtr wParam, IntPtr lParam)
        {
            if (code >= 0) _lastKey = Environment.TickCount;
            return CallNextHookEx(_hook, code, wParam, lParam);
        }

        /// <summary>כמה אלפיות שנייה עברו מההקשה האחרונה (ב-Word או בחלונית).</summary>
        public static int IdleMs
        {
            get
            {
                uint idle = unchecked((uint)(Environment.TickCount - _lastKey));
                return idle > int.MaxValue ? int.MaxValue : (int)idle;
            }
        }

        [DllImport("user32.dll", SetLastError = true)]
        static extern IntPtr SetWindowsHookEx(int idHook, HookProc lpfn, IntPtr hMod, uint dwThreadId);

        [DllImport("user32.dll")]
        static extern bool UnhookWindowsHookEx(IntPtr hhk);

        [DllImport("user32.dll")]
        static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);

        [DllImport("kernel32.dll")]
        static extern uint GetCurrentThreadId();
    }
}
