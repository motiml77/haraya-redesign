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
hebrew.KeepData=להשאיר את מפת החיפוש והסלים במחשב (מומלץ אם מתקינים שוב)?
english.KeepData=Keep the search index and baskets on this computer?

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; Flags: checkedonce

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

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
