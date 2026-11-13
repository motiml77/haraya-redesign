// התוסף ל-Word: חיפוש עברי (אותו מנוע של התוכנה "חיפוש במסמכים") בתוך המסמך הפתוח.
//
// בנוי כתוסף VSTO, לפי ההנחיות של Microsoft:
//   * רץ בסביבה מבודדת משלו (AppDomain), ולא ב-mscoree המשותף לכל התוספים;
//   * ההפעלה מהירה: ב-Startup רק נרשמים לאירועים. שום קריאה של מסמך בזמן הפתיחה;
//   * חלונית הצד – CustomTaskPane לכל חלון מסמך, ונסגרת עם המסמך;
//   * הכפתור ברצועה – Ribbon XML (CreateRibbonExtensibilityObject).
using System;
using System.Collections.Generic;
using Microsoft.Office.Tools;
using Word = Microsoft.Office.Interop.Word;

namespace HebDocSearch.WordAddin
{
    public partial class ThisAddIn
    {
        internal HelperClient Helper { get; private set; }
        internal Preparer Preparer { get; private set; }

        readonly Dictionary<CustomTaskPane, Word.Document> _panes = new Dictionary<CustomTaskPane, Word.Document>();

        private void ThisAddIn_Startup(object sender, EventArgs e)
        {
            try
            {
                Helper = new HelperClient();
                Preparer = new Preparer(this, Helper);
                var events = (Word.ApplicationEvents4_Event)Application;
                events.DocumentOpen += OnDocumentOpen;
                events.DocumentBeforeClose += OnDocumentBeforeClose;
                events.DocumentBeforeSave += OnDocumentBeforeSave;
                events.WindowSelectionChange += OnSelectionChange;
                Log.Write("startup");
            }
            catch (Exception ex)
            {
                Log.Error("startup", ex);
            }
        }

        private void ThisAddIn_Shutdown(object sender, EventArgs e)
        {
            try
            {
                Preparer?.Dispose();
                Helper?.Dispose();
            }
            catch { }
        }

        protected override Microsoft.Office.Core.IRibbonExtensibility CreateRibbonExtensibilityObject()
        {
            return new Ribbon(this);
        }

        // ================================================================ אירועים
        void OnDocumentOpen(Word.Document doc)
        {
            // רק רושמים. הקריאה תתבצע אחרי שהפתיחה הסתיימה ו-Word פנוי
            try { Preparer.Enqueue(doc, 2500); }
            catch (Exception ex) { Log.Error("open", ex); }
        }

        // הסמן זז (קורה בכל הקלדה) – רק נרשם איפה (בשביל בדיקת כותרות במקום הזה בחיפוש הבא)
        void OnSelectionChange(Word.Selection sel)
        {
            Preparer?.OnSelectionChange(sel);
        }

        void OnDocumentBeforeSave(Word.Document doc, ref bool saveAsUI, ref bool cancel)
        {
            try { Preparer?.OnBeforeSave(doc); }
            catch (Exception ex) { Log.Error("save", ex); }
        }

        void OnDocumentBeforeClose(Word.Document doc, ref bool cancel)
        {
            try
            {
                Preparer.Forget(doc);
                var gone = new List<CustomTaskPane>();
                foreach (var kv in _panes)
                    if (ReferenceEquals(kv.Value, doc)) gone.Add(kv.Key);
                foreach (var pane in gone) RemovePane(pane);
            }
            catch (Exception ex) { Log.Error("close", ex); }
        }

        // ================================================================ חלונית החיפוש
        internal void TogglePane()
        {
            try
            {
                Word.Window win = Application.ActiveWindow;
                Word.Document doc = win.Document;
                CustomTaskPane pane = PaneFor(win);
                if (pane == null)
                {
                    var control = new SearchPane(this, win, doc);
                    pane = CustomTaskPanes.Add(control, "חיפוש עברי", win);
                    // ברירת מחדל 342 (בפיקסלים של 100%, כפול קנה המידה של המסך), או הרוחב שהמשתמש גרר בפעם הקודמת
                    int logical = SearchPane.SavedWidth();
                    pane.Width = (int)Math.Round((logical > 0 ? logical : 342) * Assets.SystemScale);
                    pane.VisibleChanged += (s, e) =>
                    {
                        if (((CustomTaskPane)s).Visible) control.FocusSearch();
                    };
                    _panes[pane] = doc;
                    pane.Visible = true;
                    control.FocusSearch();
                }
                else
                {
                    pane.Visible = !pane.Visible;
                }
                if (pane.Visible)
                {
                    Preparer.Enqueue(doc, 0);
                    Log.Write("pane opened: " + Preparer.Status(doc));
                }
            }
            catch (Exception ex)
            {
                Log.Error("pane", ex);
                System.Windows.Forms.MessageBox.Show("לא ניתן לפתוח את חלונית החיפוש:\n" + ex.Message, "חיפוש עברי",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning,
                    System.Windows.Forms.MessageBoxDefaultButton.Button1,
                    System.Windows.Forms.MessageBoxOptions.RtlReading | System.Windows.Forms.MessageBoxOptions.RightAlign);
            }
        }

        CustomTaskPane PaneFor(Word.Window win)
        {
            foreach (var pane in CustomTaskPanes)
            {
                try
                {
                    if (ReferenceEquals(pane.Window, win) || ((Word.Window)pane.Window).Hwnd == win.Hwnd) return pane;
                }
                catch { }
            }
            return null;
        }

        void RemovePane(CustomTaskPane pane)
        {
            _panes.Remove(pane);
            try
            {
                var control = pane.Control;
                CustomTaskPanes.Remove(pane);
                control?.Dispose();
            }
            catch (Exception ex) { Log.Error("remove pane", ex); }
        }

        #region VSTO generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InternalStartup()
        {
            this.Startup += new System.EventHandler(ThisAddIn_Startup);
            this.Shutdown += new System.EventHandler(ThisAddIn_Shutdown);
        }

        #endregion
    }
}
