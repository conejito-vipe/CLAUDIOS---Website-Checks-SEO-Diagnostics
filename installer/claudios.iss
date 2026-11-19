; Inno-Setup-Skript für CLAUDIOS: Installation nur für den aktuellen Benutzer, ohne Admin-Rechte.
; Die Prüfwerkzeuge liegen getrennt in %LOCALAPPDATA%\Claudios und werden beim ersten Start des Programms eingerichtet.
; Die Funktion "CLAUDIOS deinstallieren" im Programm entfernt sie und startet danach diesen Deinstaller.
; Das Symbol kommt aus assets\claudios.ico (Build erzeugt sie, falls sie fehlt); ohne diese Datei gilt das Standardsymbol.
; Die Lizenz wird je Sprache angezeigt (englisch: LICENSE, deutsch: LICENSE.de.txt).

#define AppFullName "CLAUDIOS - Website-Checks-SEO-Diagnostics"
#define AppShortName "CLAUDIOS"
#define AppExeName "Claudios.exe"
#define AppVersion "0.1.0"
; Autorenname: früher der Platzhalter [AUTHOR_NAME], jetzt fest gesetzt. Hier ändern, falls er sich wieder ändert.
#define AuthorName "conejito-vipe"

#ifexist "..\assets\claudios.ico"
  #define HasIcon
#endif

[Setup]
AppId={{6E1D2B34-7C59-4C0A-9F3A-2D5B8E41A7C9}
AppName={#AppFullName}
AppVersion={#AppVersion}
AppPublisher=GitHub - {#AuthorName}
DefaultDirName={localappdata}\Programs\{#AppShortName}
DefaultGroupName={#AppShortName}
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=Output
OutputBaseFilename=Claudios-Setup-{#AppVersion}
LicenseFile=..\LICENSE
UninstallDisplayName={#AppFullName}
#ifdef HasIcon
SetupIconFile=..\assets\claudios.ico
UninstallDisplayIcon={app}\claudios.ico
#else
UninstallDisplayIcon={app}\{#AppExeName}
#endif

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"; LicenseFile: "..\LICENSE.de.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "..\LICENSE"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "..\dist\Claudios\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE.de.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.de.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\claudios.ico"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
#ifdef HasIcon
Name: "{group}\{#AppShortName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\claudios.ico"
Name: "{autodesktop}\{#AppShortName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\claudios.ico"; Tasks: desktopicon
#else
Name: "{group}\{#AppShortName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppShortName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
#endif

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppShortName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Claudios\tools"
Type: filesandordirs; Name: "{localappdata}\Claudios\cache"
