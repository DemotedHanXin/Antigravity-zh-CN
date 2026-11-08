#define AppName "Antigravity 中文助手"
#define AppVersion "0.1.0"
#define AppExeName "AntigravityZhCN.exe"

[Setup]
AppId={{7E373AAF-0B86-4C72-A4E9-10A85F60EFD1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Antigravity-zh Contributors
DefaultDirName={localappdata}\Programs\AntigravityZhCN
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=AntigravityZhCN-{#AppVersion}-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; Flags: unchecked

[Files]
Source: "..\dist\AntigravityZhCN\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

; Deliberately no UninstallDelete and no installation-changing Run commands.
; User dictionaries/settings and the target Antigravity installation are preserved.
