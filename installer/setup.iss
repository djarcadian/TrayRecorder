; Inno Setup 6 — packages the PyInstaller bundle into a single TrayRecorder_Setup.exe
; Run after build.ps1 produces dist\TrayRecorder\
; iscc installer\setup.iss

#define MyAppName "TrayRecorder"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Natran"
#define MyAppExeName "TrayRecorder.exe"

[Setup]
AppId={{D3F8A1E4-2B6C-4F89-91A7-5E2C9B0D8F33}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=TrayRecorder_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\src\resources\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "autostart";    Description: "Start {#MyAppName} when Windows starts"; GroupDescription: "Other:"; Flags: unchecked

[Files]
; Bundle every file the PyInstaller output produced
Source: "..\dist\TrayRecorder\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";          Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";    Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Internal Run entry name kept as "NatranScreenRec" so it overwrites the old
; install's autostart value cleanly if you previously had ScreenRec installed.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "NatranScreenRec"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
; Force-kill TrayRecorder.exe if running so files are removable
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM {#MyAppExeName} >nul 2>&1"; Flags: runhidden

[UninstallDelete]
; Clean up app data created at runtime
Type: filesandordirs; Name: "{userappdata}\Natran\ScreenRec"
