// התוסף עצמו: Word טוען אותו בהפעלה (LoadBehavior=3), הוא מוסיף כפתור "חיפוש עברי" לכרטיסייה
// "בית", וכל לחיצה פותחת או סוגרת את חלונית החיפוש של החלון הנוכחי (חלונית לכל מסמך).
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

namespace HebDocSearch.WordAddin
{
    [ComVisible(true)]
    [Guid(Connect.ClassId)]
    [ProgId(Connect.ProgIdName)]
    [ClassInterface(ClassInterfaceType.AutoDispatch)]
    public class Connect : IDTExtensibility2, IRibbonExtensibility, ICustomTaskPaneConsumer
    {
        public const string ClassId = "DF1B493C-5ACC-441F-A018-0D2D8670A71E";
        public const string ProgIdName = "HebDocSearch.WordAddin";
        public const string Title = "חיפוש עברי";

        private dynamic _app;
        private dynamic _factory;
        private readonly List<dynamic> _panes = new List<dynamic>();

        internal static HelperClient Helper { get; } = new HelperClient();
        internal static DocIndexer Indexer { get; private set; }

        // ----- IDTExtensibility2 -----
        public void OnConnection(object Application, ext_ConnectMode ConnectMode, object AddInInst, ref Array custom)
        {
            _app = Application;
            Log.Write("connect: mode=" + ConnectMode + " clr=" + Environment.Version + " 64bit=" + Environment.Is64BitProcess);
            Indexer = new DocIndexer(_app);
            // נטען אחרי ש-Word כבר פעל (למשל הופעל מחדש מהגדרות התוספים) – OnStartupComplete לא ייקרא
            if (ConnectMode == ext_ConnectMode.ext_cm_AfterStartup) Indexer.Start();
        }

        public void OnDisconnection(ext_DisconnectMode RemoveMode, ref Array custom)
        {
            foreach (var pane in _panes)
            {
                try { pane.Delete(); } catch { }
            }
            _panes.Clear();
            Indexer?.Dispose();
            Indexer = null;
            Helper.Dispose();
            _app = null;
        }

        public void OnAddInsUpdate(ref Array custom) { }
        public void OnStartupComplete(ref Array custom)
        {
            Indexer?.Start();                        // הכנת המסמכים לחיפוש מתחילה רק אחרי ש-Word עלה לגמרי
        }

        public void OnBeginShutdown(ref Array custom)
        {
            Indexer?.Dispose();
            Helper.Dispose();
        }

        // ----- IRibbonExtensibility -----
        public string GetCustomUI(string RibbonID)
        {
            return Resource("ribbon.xml");
        }

        // ----- ICustomTaskPaneConsumer -----
        public void CTPFactoryAvailable(object CTPFactoryInst)
        {
            _factory = CTPFactoryInst;
        }

        // ----- כפתור בסרגל -----
        public void OnTogglePane(object control)
        {
            try
            {
                dynamic window = _app.ActiveWindow;
                dynamic pane = FindPane(window);
                if (pane != null)
                {
                    pane.Visible = !(bool)pane.Visible;
                    if ((bool)pane.Visible) ((SearchPane)pane.ContentControl).FocusSearch();
                    return;
                }
                pane = _factory.CreateCTP(SearchPane.ProgIdName, Title, window);
                pane.Width = 360;
                var content = (SearchPane)pane.ContentControl;
                content.Attach(_app, window, pane);
                _panes.Add(pane);
                pane.Visible = true;
                content.FocusSearch();
                Helper.WarmUp();                     // רכיב העזר עולה ברקע, כדי שהחיפוש הראשון יהיה מהיר
            }
            catch (Exception e)
            {
                Log.Error("toggle pane", e);
                System.Windows.Forms.MessageBox.Show("לא ניתן לפתוח את חלונית החיפוש:\n" + e.Message, Title);
            }
        }

        private dynamic FindPane(dynamic window)
        {
            for (int i = _panes.Count - 1; i >= 0; i--)
            {
                dynamic pane = _panes[i];
                try
                {
                    if (SameWindow(pane.Window, window)) return pane;
                }
                catch
                {
                    _panes.RemoveAt(i);              // החלון נסגר
                }
            }
            return null;
        }

        private static bool SameWindow(dynamic a, dynamic b)
        {
            try { return (int)a.Hwnd == (int)b.Hwnd; }
            catch { return ReferenceEquals(a, b); }
        }

        internal static string Resource(string name)
        {
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            using (var r = new StreamReader(s, System.Text.Encoding.UTF8))
                return r.ReadToEnd();
        }
    }
}
