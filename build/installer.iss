; Instalador do EasyBlock (Inno Setup 6) - compile depois de rodar build.bat
#define AppName "EasyBlock"
#define AppVersion "2.0.0"
#define AppExe "EasyBlock.exe"

[Setup]
AppId={{B7C1D2E4-5A63-4F0B-9C1E-0B10C4E2A001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Ivande Coelho
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=EasyBlock-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName} agora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; remove as tarefas agendadas criadas pelo app (iniciar com o Windows e guardiao)
Filename: "schtasks.exe"; Parameters: "/Delete /TN ""Bloqueador-Guardiao"" /F"; Flags: runhidden; RunOnceId: "DelWatchdog"
Filename: "schtasks.exe"; Parameters: "/Delete /TN ""Bloqueador-Inicio"" /F"; Flags: runhidden; RunOnceId: "DelAutostart"
Filename: "taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillApp"
