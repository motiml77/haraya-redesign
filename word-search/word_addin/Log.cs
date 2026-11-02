// יומן קצר של מה שהתוסף עושה (כדי לאבחן בעיות בלי דיבאגר):
//   %LOCALAPPDATA%\HebWordSearch\word-addin.log  (עד ~1MB, אחר כך מתחיל מחדש)
using System;
using System.IO;
using System.Text;

namespace HebDocSearch.WordAddin
{
    internal static class Log
    {
        static readonly object Lock = new object();

        public static string Path
        {
            get
            {
                string dir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "HebWordSearch");
                Directory.CreateDirectory(dir);
                return System.IO.Path.Combine(dir, "word-addin.log");
            }
        }

        public static void Write(string message)
        {
            try
            {
                lock (Lock)
                {
                    string path = Path;
                    var info = new FileInfo(path);
                    if (info.Exists && info.Length > 1_000_000) info.Delete();
                    File.AppendAllText(path, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + "  " + message + Environment.NewLine,
                                       Encoding.UTF8);
                }
            }
            catch { }
        }

        public static void Error(string where, Exception e)
        {
            Write("ERROR " + where + ": " + e.GetType().Name + ": " + e.Message + " | " + (e.StackTrace ?? "").Replace(Environment.NewLine, " / "));
        }
    }
}
