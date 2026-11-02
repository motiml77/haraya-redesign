// ממשקי COM של Office שהתוסף מממש. מוגדרים כאן (עם ה-GUID המקוריים) במקום לגרור את ספריות ה-PIA,
// כדי שהתוסף ייבנה בלי Office מותקן ויעבוד עם כל גרסה של Word (2013 ומעלה, 32 ו-64 ביט).
using System;
using System.Runtime.InteropServices;

namespace HebDocSearch.WordAddin
{
    public enum ext_ConnectMode { ext_cm_AfterStartup = 0, ext_cm_Startup = 1, ext_cm_External = 2, ext_cm_CommandLine = 3 }
    public enum ext_DisconnectMode { ext_dm_HostShutdown = 0, ext_dm_UserClosed = 1 }

    [ComImport, Guid("B65AD801-ABAF-11D0-BB8B-00A0C90F2744"), InterfaceType(ComInterfaceType.InterfaceIsDual)]
    public interface IDTExtensibility2
    {
        [DispId(1)] void OnConnection([MarshalAs(UnmanagedType.IDispatch)] object Application, ext_ConnectMode ConnectMode,
                                      [MarshalAs(UnmanagedType.IDispatch)] object AddInInst, ref Array custom);
        [DispId(2)] void OnDisconnection(ext_DisconnectMode RemoveMode, ref Array custom);
        [DispId(3)] void OnAddInsUpdate(ref Array custom);
        [DispId(4)] void OnStartupComplete(ref Array custom);
        [DispId(5)] void OnBeginShutdown(ref Array custom);
    }

    [ComImport, Guid("000C0396-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsDual)]
    public interface IRibbonExtensibility
    {
        [DispId(1)] string GetCustomUI(string RibbonID);
    }

    [ComImport, Guid("000C033E-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsDual)]
    public interface ICustomTaskPaneConsumer
    {
        [DispId(1)] void CTPFactoryAvailable([MarshalAs(UnmanagedType.IDispatch)] object CTPFactoryInst);
    }
}
