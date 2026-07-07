#define MyAppName "VC"
#define MyAppFullName "VC - Version Controller"
#define MyAppVersion "0.1.2"
#define MyAppPublisher "marin"
#define MyAppURL "https://github.com/RongMarin99/vc-panel"
#define MyAppExeName "VC.exe"
#define MyBuildDir "build\exe.win-amd64-3.13"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppFullName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppFullName}
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=dist
OutputBaseFilename=VC-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayName={#MyAppFullName}
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableProgramGroupPage=yes
SetupIconFile=assets\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; Main exe
Source: "{#MyBuildDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; All root DLLs
Source: "{#MyBuildDir}\*.dll"; DestDir: "{app}"; Flags: ignoreversion

; lib folder (Python packages + PyQt6 pyd files)
Source: "{#MyBuildDir}\lib\*"; DestDir: "{app}\lib"; Flags: ignoreversion recursesubdirs createallsubdirs

; assets
Source: "{#MyBuildDir}\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; PyQt6 uic widget plugins (if present)
Source: "{#MyBuildDir}\PyQt6.uic.widget-plugins\*"; DestDir: "{app}\PyQt6.uic.widget-plugins"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; frozen_application_license etc
Source: "{#MyBuildDir}\*.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppFullName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppFullName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppFullName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppFullName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove app data on uninstall (optional — comment out to keep user data)
; Type: filesandordirs; Name: "{localappdata}\VC"
