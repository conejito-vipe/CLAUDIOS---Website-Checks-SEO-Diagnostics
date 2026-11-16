; Inno-Setup-Skript für Claudios: Installation nur für den aktuellen Benutzer, ohne Admin-Rechte.
; Die Prüfwerkzeuge liegen getrennt in %LOCALAPPDATA%\Claudios und werden im Programm unter "Komponenten"
; installiert und mit der Funktion "Entfernen" wieder gelöscht (vorher, falls gewünscht).
#define AppName "Claudios"
#define AppVersion "0.1.0"

[Setup]
AppId={{6E1D2B34-7C59-4C0A-9F3A-2D5B8E41A7C9}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=fuhfux
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=Output
OutputBaseFilename=Claudios-Setup-{#AppVersion}
LicenseFile=..\LICENSE
UninstallDisplayName={#AppName}

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "..\dist\Claudios\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Claudios.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Claudios.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Claudios.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent