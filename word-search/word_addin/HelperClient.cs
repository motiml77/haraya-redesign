// רכיב העזר (HebDocSearchHelper.exe, מגיע עם התוכנה): אותו מנוע חיפוש, רץ כתהליך נפרד בלי חלון.
// מדברים איתו בשורת JSON לכל בקשה ותשובה (ראו hebsearch/docsearch.py).
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;

namespace HebDocSearch.WordAddin
{
    internal sealed class HelperClient : IDisposable
    {
        private readonly object _lock = new object();
        private Process _proc;
        private StreamWriter _in;
        private StreamReader _out;

        public static string ExePath
        {
            get
            {
                // התוסף מותקן ב-<תיקיית התוכנה>\word, ורכיב העזר בתיקיית התוכנה עצמה
                string dll = new Uri(Assembly.GetExecutingAssembly().CodeBase).LocalPath;
                string dir = Path.GetDirectoryName(dll);
                string exe = Path.Combine(Path.GetDirectoryName(dir), "HebDocSearchHelper.exe");
                return File.Exists(exe) ? exe : Path.Combine(dir, "HebDocSearchHelper.exe");
            }
        }

        public void WarmUp()
        {
            Task.Run(() => { try { Call("{\"cmd\": \"ping\"}"); } catch { } });
        }

        private void Start()
        {
            var psi = new ProcessStartInfo(ExePath)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                StandardOutputEncoding = new UTF8Encoding(false),
                StandardErrorEncoding = new UTF8Encoding(false),
                WorkingDirectory = Path.GetDirectoryName(ExePath),
            };
            _proc = Process.Start(psi);
            _proc.ErrorDataReceived += (s, e) => { };
            _proc.BeginErrorReadLine();
            _in = new StreamWriter(_proc.StandardInput.BaseStream, new UTF8Encoding(false)) { AutoFlush = true, NewLine = "\n" };
            _out = _proc.StandardOutput;
        }

        /// <summary>שולח בקשה ומחזיר את התשובה. אם התהליך נפל – מפעיל מחדש ומנסה פעם נוספת.</summary>
        public string Call(string json, int timeoutMs = 60000)
        {
            lock (_lock)
            {
                for (int attempt = 0; ; attempt++)
                {
                    try
                    {
                        if (_proc == null || _proc.HasExited) Start();
                        _in.WriteLine(json);
                        Task<string> line = _out.ReadLineAsync();
                        if (!line.Wait(timeoutMs)) throw new TimeoutException("רכיב החיפוש לא ענה בזמן");
                        if (line.Result == null) throw new IOException("רכיב החיפוש נסגר");
                        return line.Result;
                    }
                    catch (Exception) when (attempt == 0)
                    {
                        Kill();
                    }
                }
            }
        }

        private void Kill()
        {
            try { if (_proc != null && !_proc.HasExited) _proc.Kill(); } catch { }
            _proc = null;
        }

        public void Dispose()
        {
            lock (_lock)
            {
                try { _in?.WriteLine("{\"cmd\": \"quit\"}"); } catch { }
                try { if (_proc != null && !_proc.WaitForExit(800)) _proc.Kill(); } catch { }
                _proc = null;
            }
        }
    }
}
