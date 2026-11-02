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

; המפתח הציבורי של תעודת החתימה של התוסף ל-Word (נוצר ב-build.py)
#ifdef VstoKeyFile
  #include VstoKeyFile
#endif
#ifndef VstoPublicKey
  #define VstoPublicKey ""
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
hebrew.VstoRuntime=כדי שהתוסף ל-Word יעבוד צריך את רכיב Microsoft "Visual Studio 2010 Tools for Office Runtime", והוא לא נמצא במחשב.%n%nלפתוח עכשיו את דף ההורדה הרשמי של Microsoft?
english.VstoRuntime=The Word add-in needs Microsoft "Visual Studio 2010 Tools for Office Runtime", which was not found.%n%nOpen the official Microsoft download page now?
hebrew.KeepData=להשאיר את מפת החיפוש והאוספים במחשב (מומלץ אם מתקינים שוב)?
english.KeepData=Keep the search index and baskets on this computer?

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; Flags: checkedonce
Name: "wordaddin"; Description: "{cm:WordAddin}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs


[Registry]
; התוסף ל-Word (VSTO) – רישום לפי "Registry entries for VSTO Add-ins" של Microsoft:
; FriendlyName, Description, LoadBehavior=3 (נטען בהפעלת Word), Manifest=<נתיב ה-.vsto>|vstolocal
; (vstolocal – רץ ישירות מתיקיית ההתקנה, בלי מטמון ClickOnce). בשתי תצוגות הרישום – ל-Word של 32 ושל 64 ביט.
Root: HKA64; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "FriendlyName"; ValueData: "חיפוש עברי"; Flags: uninsdeletekey; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "Description"; ValueData: "חיפוש עברי במסמך – מתוך חיפוש במסמכים"; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: dword; ValueName: "LoadBehavior"; ValueData: 3; Tasks: wordaddin; Check: IsWin64
Root: HKA64; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "Manifest"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.vsto|vstolocal"; Tasks: wordaddin; Check: IsWin64
Root: HKA32; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "FriendlyName"; ValueData: "חיפוש עברי"; Flags: uninsdeletekey; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "Description"; ValueData: "חיפוש עברי במסמך – מתוך חיפוש במסמכים"; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: dword; ValueName: "LoadBehavior"; ValueData: 3; Tasks: wordaddin
Root: HKA32; Subkey: "Software\Microsoft\Office\Word\Addins\HebDocSearch.WordAddin"; ValueType: string; ValueName: "Manifest"; ValueData: "file:///{app}\word\HebDocSearch.WordAddin.vsto|vstolocal"; Tasks: wordaddin

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[Code]
const
  // רשימת הפתרונות המהימנים של VSTO (Inclusion List) למשתמש הנוכחי – כדי ש-Word יטען את התוסף
  // בלי לשאול. שתי רשומות: הכתובת עם רווחים ועם %20 (תלוי איך VSTO מנרמל את הנתיב).
  InclusionRoot = 'Software\Microsoft\VSTO\Security\Inclusion\';
  InclusionA = '{8C3F6A2E-4B1D-4E7A-9F5C-2D6B8E1A3C70}';
  InclusionB = '{8C3F6A2E-4B1D-4E7A-9F5C-2D6B8E1A3C71}';
  OldAddinClass = 'Software\Classes\CLSID\{DF1B493C-5ACC-441F-A018-0D2D8670A71E}';
  OldPaneClass = 'Software\Classes\CLSID\{164C9487-E4CD-4C40-8687-9EC7C9FC3A84}';
  VstoRuntimePage = 'https://www.microsoft.com/download/details.aspx?id=105671';

function VstoUrl(Encoded: Boolean): String;
var
  S: String;
begin
  S := ExpandConstant('{app}\word\HebDocSearch.WordAddin.vsto');
  StringChangeEx(S, '\', '/', True);
  if Encoded then
    StringChangeEx(S, ' ', '%20', True);
  Result := 'file:///' + S;
end;

procedure TrustAddin;
var
  Key: String;
begin
  Key := '{#VstoPublicKey}';
  if Key = '' then
    Exit;
  RegWriteStringValue(HKCU, InclusionRoot + InclusionA, 'Url', VstoUrl(False));
  RegWriteStringValue(HKCU, InclusionRoot + InclusionA, 'PublicKey', Key);
  RegWriteStringValue(HKCU, InclusionRoot + InclusionB, 'Url', VstoUrl(True));
  RegWriteStringValue(HKCU, InclusionRoot + InclusionB, 'PublicKey', Key);
end;

procedure UntrustAddin;
begin
  RegDeleteKeyIncludingSubkeys(HKCU, InclusionRoot + InclusionA);
  RegDeleteKeyIncludingSubkeys(HKCU, InclusionRoot + InclusionB);
end;

// גרסת ניסיון קודמת של התוסף נרשמה כתוסף COM – מוחקים את הרישום הישן
procedure RemoveOldComAddin;
var
  Roots: array of Integer;
  I: Integer;
begin
  SetArrayLength(Roots, 4);
  Roots[0] := HKCU64; Roots[1] := HKCU32; Roots[2] := HKLM64; Roots[3] := HKLM32;
  for I := 0 to 3 do
  begin
    if (I >= 2) and not IsAdminInstallMode() then
      Break;
    RegDeleteKeyIncludingSubkeys(Roots[I], OldAddinClass);
    RegDeleteKeyIncludingSubkeys(Roots[I], OldPaneClass);
    RegDeleteKeyIncludingSubkeys(Roots[I], 'Software\Classes\HebDocSearch.WordAddin');
    RegDeleteKeyIncludingSubkeys(Roots[I], 'Software\Classes\HebDocSearch.WordPane');
  end;
end;

function VstoRuntimeInstalled: Boolean;
begin
  Result := RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\VSTO Runtime Setup\v4R')
         or RegKeyExists(HKLM32, 'SOFTWARE\Microsoft\VSTO Runtime Setup\v4R')
         or RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\VSTO Runtime Setup\v4')
         or RegKeyExists(HKLM32, 'SOFTWARE\Microsoft\VSTO Runtime Setup\v4');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
begin
  if CurStep = ssInstall then
    RemoveOldComAddin;
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('wordaddin') then
  begin
    TrustAddin;
    if not VstoRuntimeInstalled() and not WizardSilent() then
      if MsgBox(CustomMessage('VstoRuntime'), mbInformation, MB_YESNO) = IDYES then
        ShellExec('open', VstoRuntimePage, '', '', SW_SHOWNORMAL, ewNoWait, Code);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usUninstall then
    UntrustAddin;
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\HebWordSearch');
    if DirExists(DataDir) and not UninstallSilent() then
      if MsgBox(CustomMessage('KeepData'), mbConfirmation, MB_YESNO) = IDNO then
        DelTree(DataDir, True, True, True);
  end;
end;
