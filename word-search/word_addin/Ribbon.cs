// הכפתור "חיפוש עברי" בכרטיסייה "בית", ליד "עריכה" (Ribbon XML – ribbon.xml), עם הלוגו של התוכנה.
using System;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using Office = Microsoft.Office.Core;

namespace HebDocSearch.WordAddin
{
    [ComVisible(true)]
    public class Ribbon : Office.IRibbonExtensibility
    {
        private readonly ThisAddIn _addin;

        internal Ribbon(ThisAddIn addin)
        {
            _addin = addin;
        }

        public string GetCustomUI(string ribbonID)
        {
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("ribbon.xml"))
            using (var r = new StreamReader(s))
                return r.ReadToEnd();
        }

        /// <summary>הלוגו לכפתור הגדול (32 נקודות), בחדות של המסך: 32px ב-100%, 64px ב-200%.</summary>
        public Bitmap GetLogo(Office.IRibbonControl control)
        {
            try { return Assets.Logo((int)Math.Round(32 * Assets.SystemScale)); }
            catch (Exception e) { Log.Error("ribbon image", e); return null; }
        }

        public void OnTogglePane(Office.IRibbonControl control)
        {
            try { _addin.TogglePane(); }
            catch (Exception e) { Log.Error("ribbon", e); }
        }
    }
}
