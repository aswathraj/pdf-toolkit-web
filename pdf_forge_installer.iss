#define MyAppName "PDF Forge"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "PDF Forge"
#define MyAppExeName "PDFForge.exe"

[Setup]
AppId={{E1D9A0C8-89B5-4D0E-8A9D-B5C51BBD0D44}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\PDF Forge
DefaultGroupName=PDF Forge
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
OutputDir=installer_output
OutputBaseFilename=PDFForgeSetup
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\PDFForge.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\PDF Forge"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\PDF Forge"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PDF Forge"; Flags: nowait postinstall skipifsilent
