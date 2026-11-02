// הכפתור "חיפוש עברי" בכרטיסייה "בית", ליד "עריכה" (Ribbon XML – ribbon.xml).
using System;
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

        public void OnTogglePane(Office.IRibbonControl control)
        {
            try { _addin.TogglePane(); }
            catch (Exception e) { Log.Error("ribbon", e); }
        }
    }
}
