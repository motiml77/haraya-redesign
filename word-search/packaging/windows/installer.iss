; אשף ההתקנה לחלונות (Inno Setup 6). נבנה על-ידי packaging/build.py
; ISCC /DAppVersion=1.0.0 /DSourceDir=...\dist\HebDocSearch /DOutputDir=...\dist installer.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\HebDocSearch"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

#define AppName "חיפוש במסמכים"
#define AppExe "HebDocSearch.exe"

[Setup]
AppId={{6B0F3C2E-8E54-4C7B-9C1D-2F4A8D5E7B31}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=HebDocSearch
DefaultDirName={autopf}\HebDocSearch
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=HebDocSearch-Setup-{#AppVersion}
SetupIconFile=..\..\hebsearch\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; התקנה למשתמש הנוכחי בלי הרשאות מנהל, או לכל המשתמשים – לבחירה בתחילת האשף
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
ShowLanguageDialog=auto

[Languages]
Name: "hebrew"; MessagesFile: "compiler:Languages\Hebrew.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
hebrew.DesktopIcon=קיצור דרך בשולחן העבודה
english.DesktopIcon=Desktop shortcut
hebrew.LaunchApp=הפעל את {#AppName}
english.LaunchApp=Launch {#AppName}
hebrew.WordAddin=תוסף "חיפוש עברי" ל-Word (כפתור בכרטיסייה "בית")
english.WordAddin=Word add-in "Hebrew search" (button on the Home tab)
hebrew.KeepData=להשאיר את מפת החיפוש והאוספים במחשב (מומלץ אם מתקינים שוב)?
english.KeepData=Keep the search index and baskets on this computer?

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; Flags: checkedonce
Name: "wordaddin"; Description: "{cm:WordAddin}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs


[Registry]
; התוסף ל-Word: שתי מחלקות COM של ‎.NET (התוסף וחלונית החיפוש) ורישום התוסף ב-Word.
; נרשם בשתי התצוגות של הרישום, כדי שיעבוד גם ב-Word של 32 ביט וגם של 64 ביט.
Root: HKA64; Subkey: "Software\Classes\HebDocSearch.WordAddin"; ValueType: string; ValueData: "HebDocSearch.WordAddin"; Flags: uninsdeletekey; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\HebDocSearch.WordAddin\CLSID"; ValueType: string; ValueData: "{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}"; ValueType: string; ValueData: "HebDocSearch.WordAddin"; Flags: uninsdeletekey; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\ProgId"; ValueType: string; ValueData: "HebDocSearch.WordAddin"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\Implemented Categories\{{62C8FE65-4EBB-45e7-B440-6E39B2CDBF29}"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueData: "mscoree.dll"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Both"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "Class"; ValueData: "HebDocSearch.WordAddin.Connect"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "Assembly"; ValueData: "HebDocSearch.WordAddin, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "RuntimeVersion"; ValueData: "v4.0.30319"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "CodeBase"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.dll"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "Class"; ValueData: "HebDocSearch.WordAddin.Connect"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "Assembly"; ValueData: "HebDocSearch.WordAddin, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "RuntimeVersion"; ValueData: "v4.0.30319"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "CodeBase"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.dll"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\HebDocSearch.WordPane"; ValueType: string; ValueData: "HebDocSearch.WordPane"; Flags: uninsdeletekey; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\HebDocSearch.WordPane\CLSID"; ValueType: string; ValueData: "{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}"; ValueType: string; ValueData: "HebDocSearch.WordPane"; Flags: uninsdeletekey; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\ProgId"; ValueType: string; ValueData: "HebDocSearch.WordPane"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\Implemented Categories\{{62C8FE65-4EBB-45e7-B440-6E39B2CDBF29}"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueData: "mscoree.dll"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Both"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "Class"; ValueData: "HebDocSearch.WordAddin.SearchPane"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "Assembly"; ValueData: "HebDocSearch.WordAddin, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "RuntimeVersion"; ValueData: "v4.0.30319"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "CodeBase"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.dll"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "Class"; ValueData: "HebDocSearch.WordAddin.SearchPane"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "Assembly"; ValueData: "HebDocSearch.WordAddin, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "RuntimeVersion"; ValueData: "v4.0.30319"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "CodeBase"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.dll"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "FriendlyName"; ValueData: "חיפוש עברי"; Flags: uninsdeletekey; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "Description"; ValueData: "חיפוש עברי במסמך – מתוך חיפוש במסמכים"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: dword; ValueName: "LoadBehavior"; ValueData: 3; Tasks: wordaddin; Check: IsWin64
Root: HKA32; Subkey: "Software\Classes\HebDocSearch.WordAddin"; ValueType: string; ValueData: "HebDocSearch.WordAddin"; Flags: uninsdeletekey; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\HebDocSearch.WordAddin\CLSID"; ValueType: string; ValueData: "{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}"; ValueType: string; ValueData: "HebDocSearch.WordAddin"; Flags: uninsdeletekey; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\ProgId"; ValueType: string; ValueData: "HebDocSearch.WordAddin"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\Implemented Categories\{{62C8FE65-4EBB-45e7-B440-6E39B2CDBF29}"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueData: "mscoree.dll"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Both"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "Class"; ValueData: "HebDocSearch.WordAddin.Connect"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "Assembly"; ValueData: "HebDocSearch.WordAddin, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "RuntimeVersion"; ValueData: "v4.0.30319"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32"; ValueType: string; ValueName: "CodeBase"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.dll"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "Class"; ValueData: "HebDocSearch.WordAddin.Connect"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "Assembly"; ValueData: "HebDocSearch.WordAddin, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "RuntimeVersion"; ValueData: "v4.0.30319"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{DF1B493C-5ACC-441F-A018-0D2D8670A71E}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "CodeBase"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.dll"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\HebDocSearch.WordPane"; ValueType: string; ValueData: "HebDocSearch.WordPane"; Flags: uninsdeletekey; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\HebDocSearch.WordPane\CLSID"; ValueType: string; ValueData: "{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}"; ValueType: string; ValueData: "HebDocSearch.WordPane"; Flags: uninsdeletekey; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\ProgId"; ValueType: string; ValueData: "HebDocSearch.WordPane"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\Implemented Categories\{{62C8FE65-4EBB-45e7-B440-6E39B2CDBF29}"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueData: "mscoree.dll"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "ThreadingModel"; ValueData: "Both"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "Class"; ValueData: "HebDocSearch.WordAddin.SearchPane"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "Assembly"; ValueData: "HebDocSearch.WordAddin, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "RuntimeVersion"; ValueData: "v4.0.30319"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32"; ValueType: string; ValueName: "CodeBase"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.dll"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "Class"; ValueData: "HebDocSearch.WordAddin.SearchPane"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "Assembly"; ValueData: "HebDocSearch.WordAddin, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "RuntimeVersion"; ValueData: "v4.0.30319"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Classes\CLSID\{{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}\InprocServer32\1.0.0.0"; ValueType: string; ValueName: "CodeBase"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.dll"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "FriendlyName"; ValueData: "חיפוש עברי"; Flags: uninsdeletekey; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "Description"; ValueData: "חיפוש עברי במסמך – מתוך חיפוש במסמכים"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: dword; ValueName: "LoadBehavior"; ValueData: 3; Tasks: wordaddin

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\HebWordSearch');
    if DirExists(DataDir) and not UninstallSilent() then
      if MsgBox(CustomMessage('KeepData'), mbConfirmation, MB_YESNO) = IDNO then
        DelTree(DataDir, True, True, True);
  end;
end;
