// מה שנשמר בדיסק לכל מסמך, כדי שבפתיחה הבאה לא יהיה צריך לקרוא את הכותרות מחדש:
//   %LOCALAPPDATA%\HebWordSearch\cache\<טביעת אצבע של נתיב המסמך>.hws
// לכל פסקה – טביעת אצבע של הטקסט (לא הטקסט עצמו) ורמת הכותרת, וההפרשים במיקום שנלמדו.
// כשהמסמך נפתח שוב: אם הקובץ לא השתנה מאז (אותו גודל וזמן שינוי, אותו טקסט) – הכותרות מוכנות מיד.
// אם השתנה – הרמות עוברות לפסקאות שלא השתנו, ורק השאר נבדק במסמך.
// אין כאן שום גישה ל-Word.
using System;
using System.IO;
using System.Text;

namespace HebDocSearch.WordAddin
{
    internal sealed class CacheEntry
    {
        public DocSnapshot Snap;
        public long FileTicks, FileSize;     // הקובץ בדיסק כשנשמר המטמון
        public bool Verified;                // הרמות נקראו מהמסמך כשהוא היה זהה לקובץ הזה בדיסק
    }

    internal static class HeadingCache
    {
        const int Magic = 0x31535748;        // "HWS1"
        const int Version = 2;
        const int KeepFiles = 300;

        public static string Dir
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "HebWordSearch", "cache");
            }
        }

        /// <summary>מסמך שנשמר במחשב (לא מסמך חדש בלי שם, ולא כתובת בענן).</summary>
        public static bool IsLocalFile(string docPath)
        {
            try
            {
                return !string.IsNullOrEmpty(docPath) && docPath.IndexOf("://", StringComparison.Ordinal) < 0
                       && Path.IsPathRooted(docPath) && File.Exists(docPath);
            }
            catch { return false; }
        }

        /// <summary>האם יש למסמך מקום קבוע שאפשר לשמור לפיו (נתיב או כתובת; לא "מסמך1").</summary>
        public static bool HasIdentity(string docPath)
        {
            return !string.IsNullOrEmpty(docPath) && (docPath.IndexOf("://", StringComparison.Ordinal) > 0 || docPath.IndexOfAny(new[] { '\\', '/' }) >= 0);
        }

        public static bool FileStamp(string docPath, out long ticks, out long size)
        {
            ticks = size = 0;
            try
            {
                if (!IsLocalFile(docPath)) return false;
                var info = new FileInfo(docPath);
                ticks = info.LastWriteTimeUtc.Ticks;
                size = info.Length;
                return true;
            }
            catch { return false; }
        }

        static string FileFor(string docPath)
        {
            return Path.Combine(Dir, DocText.Fnv64(docPath.ToLowerInvariant()).ToString("x16") + ".hws");
        }

        public static CacheEntry Load(string docPath)
        {
            if (!HasIdentity(docPath)) return null;
            try
            {
                string file = FileFor(docPath);
                if (!File.Exists(file)) return null;
                using (var stream = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    CacheEntry e = Read(stream, docPath);
                    if (e != null)
                        try { File.SetLastWriteTimeUtc(file, DateTime.UtcNow); } catch { }     // "נעשה בו שימוש" – לניקוי הישנים
                    return e;
                }
            }
            catch (Exception ex)
            {
                Log.Write("cache: cannot read – " + ex.Message);
                return null;
            }
        }

        public static void Save(string docPath, CacheEntry entry)
        {
            if (!HasIdentity(docPath) || entry == null || entry.Snap == null) return;
            try
            {
                Directory.CreateDirectory(Dir);
                string file = FileFor(docPath);
                string temp = file + "." + Guid.NewGuid().ToString("N").Substring(0, 8) + ".tmp";
                using (var stream = new FileStream(temp, FileMode.Create, FileAccess.Write, FileShare.None))
                    Write(stream, docPath, entry);
                try
                {
                    if (File.Exists(file)) File.Delete(file);
                    File.Move(temp, file);
                }
                catch
                {
                    try { File.Delete(temp); } catch { }
                    throw;
                }
                Cleanup();
            }
            catch (Exception ex)
            {
                Log.Write("cache: cannot save – " + ex.Message);
            }
        }

        /// <summary>משאירים את KeepFiles המסמכים האחרונים שנעשה בהם שימוש.</summary>
        static void Cleanup()
        {
            try
            {
                var files = new DirectoryInfo(Dir).GetFiles("*.hws");
                if (files.Length <= KeepFiles) return;
                Array.Sort(files, (a, b) => b.LastWriteTimeUtc.CompareTo(a.LastWriteTimeUtc));
                for (int i = KeepFiles; i < files.Length; i++)
                    try { files[i].Delete(); } catch { }
                foreach (var stale in new DirectoryInfo(Dir).GetFiles("*.tmp"))
                    if (stale.LastWriteTimeUtc < DateTime.UtcNow.AddHours(-1))
                        try { stale.Delete(); } catch { }
            }
            catch { }
        }

        // ================================================================ הקובץ עצמו
        internal static void Write(Stream stream, string docPath, CacheEntry e)
        {
            var w = new BinaryWriter(stream, Encoding.UTF8);
            DocSnapshot s = e.Snap;
            int n = s.Hashes.Length;
            w.Write(Magic);
            w.Write(Version);
            w.Write(docPath ?? "");
            w.Write(e.FileTicks);
            w.Write(e.FileSize);
            w.Write(e.Verified);
            w.Write(s.TextHash ?? "");
            w.Write(n);
            w.Write(s.Levels, 0, n);
            var bytes = new byte[n * 8];
            Buffer.BlockCopy(s.Hashes, 0, bytes, 0, bytes.Length);
            w.Write(bytes);
            int drift = s.DriftKeys == null ? 0 : s.DriftKeys.Length;
            w.Write(drift);
            for (int i = 0; i < drift; i++)
            {
                w.Write(s.DriftKeys[i]);
                w.Write(s.DriftValues[i]);
            }
            w.Write(Magic);                  // סימן שהקובץ נכתב עד הסוף
            w.Flush();
        }

        /// <summary>null אם הקובץ לא שלם, מגרסה אחרת, או של מסמך אחר (שתי כתובות עם אותה טביעת אצבע).</summary>
        internal static CacheEntry Read(Stream stream, string docPath)
        {
            var r = new BinaryReader(stream, Encoding.UTF8);
            if (r.ReadInt32() != Magic || r.ReadInt32() != Version) return null;
            string path = r.ReadString();
            if (docPath != null && !string.Equals(path, docPath, StringComparison.OrdinalIgnoreCase)) return null;
            var e = new CacheEntry { FileTicks = r.ReadInt64(), FileSize = r.ReadInt64(), Verified = r.ReadBoolean() };
            var s = new DocSnapshot { TextHash = r.ReadString() };
            int n = r.ReadInt32();
            if (n < 0 || n > 20_000_000) return null;
            s.Levels = r.ReadBytes(n);
            byte[] bytes = r.ReadBytes(n * 8);
            if (s.Levels.Length != n || bytes.Length != n * 8) return null;
            s.Hashes = new ulong[n];
            Buffer.BlockCopy(bytes, 0, s.Hashes, 0, bytes.Length);
            int drift = r.ReadInt32();
            if (drift < 0 || drift > n + 1) return null;
            s.DriftKeys = new int[drift];
            s.DriftValues = new int[drift];
            for (int i = 0; i < drift; i++)
            {
                s.DriftKeys[i] = r.ReadInt32();
                s.DriftValues[i] = r.ReadInt32();
            }
            if (r.ReadInt32() != Magic) return null;
            e.Snap = s;
            return e;
        }
    }
}
