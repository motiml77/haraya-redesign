// מתי המשתמש הקליד בפעם האחרונה – רק מקלדת, לא עכבר. ההכנה ברקע עוצרת רק בזמן כתיבה; תזוזת עכבר או
// גלילה לא עוצרות אותה (רק מקצרות את המנות, כדי שהמסך יישאר חלק).
//
// בנוסף – EditKeys: כמה הקשות שיכולות לשנות טקסט (לא חצים, לא Ctrl/Shift/Alt לבדם, לא F1–F24) היו במסמך
// (כלומר כשהמיקוד לא בחלונית שלנו). כך יודעים אם המסמך אולי נערך – בלי לקרוא אותו מחדש בכל לחיצה בעכבר.
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
        static int _editKeys;

        /// <summary>מונה של הקשות שאולי ערכו את המסמך (עולה בכל הקשה כזו; משווים לערך הקודם).</summary>
        public static int EditKeys => _editKeys;

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
            if (code >= 0)
            {
                _lastKey = Environment.TickCount;
                bool down = ((long)lParam & 0x80000000L) == 0;
                if (down && CanEdit((int)wParam) && !FocusGuard.InAddIn) unchecked { _editKeys++; }
            }
            return CallNextHookEx(_hook, code, wParam, lParam);
        }

        /// <summary>מקש שיכול לשנות טקסט (גם Ctrl+V / Ctrl+Z / Delete נספרים – עדיף לקרוא פעם מיותרת).</summary>
        static bool CanEdit(int vk)
        {
            // Ctrl+אות (בלי Alt) הוא פקודה: רק הדבקה, גזירה, ביטול/חזרה ומחיקות משנים טקסט (לא Ctrl+C / Ctrl+S / Ctrl+F)
            if (GetKeyState(0x11) < 0 && GetKeyState(0x12) >= 0)
                return vk == 0x56 || vk == 0x58 || vk == 0x5A || vk == 0x59 || vk == 0x0D || vk == 0x08 || vk == 0x2E;
            if (vk >= 0x21 && vk <= 0x28) return false;          // PageUp/Down, End, Home, חצים
            if (vk >= 0x10 && vk <= 0x12) return false;          // Shift, Ctrl, Alt
            if (vk >= 0xA0 && vk <= 0xA5) return false;          // Shift/Ctrl/Alt ימני ושמאלי
            if (vk >= 0x70 && vk <= 0x87) return false;          // F1–F24
            switch (vk)
            {
                case 0x14: case 0x90: case 0x91:                  // Caps / Num / Scroll Lock
                case 0x1B: case 0x5B: case 0x5C: case 0x5D:       // Esc, Windows, תפריט
                case 0x2C: case 0x13:                             // PrintScreen, Pause
                    return false;
            }
            return true;
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

        [DllImport("user32.dll")]
        static extern short GetKeyState(int vKey);
    }
}
