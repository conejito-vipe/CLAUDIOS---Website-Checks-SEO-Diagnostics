; Inno-Setup-Skript für CLAUDIOS: Installation nur für den aktuellen Benutzer, ohne Admin-Rechte.
; Die Prüfwerkzeuge liegen getrennt in %LOCALAPPDATA%\CLAUDIOS und werden beim ersten Start des Programms eingerichtet.
; Die Funktion "CLAUDIOS deinstallieren" im Programm entfernt sie und startet danach diesen Deinstaller.
; Symbol und Bilder kommen aus installer\art (der Build erzeugt sie mit tools\make_installer_art.py); ohne sie gelten
; die Standardbilder. Die Lizenz wird je Sprache angezeigt (englisch: LICENSE, deutsch: LICENSE.de.txt).
; Die Version kommt vom Build (/DAppVersion=...), sonst gilt der Wert unten. Dieselbe AppId bedeutet: eine vorhandene
; Installation wird aktualisiert (Update über die alte Version).
; Hinweis: SmartScreen zeigt einen Herausgeber nur bei signierten Dateien. Ohne Zertifikat steht dort "Unbekannter Herausgeber".

#define AppFullName "CLAUDIOS - Website-Checks-SEO-Diagnostics"
#define AppShortName "CLAUDIOS"
#define AppExeName "CLAUDIOS.exe"
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
#define AuthorName "conejito-vipe"

#ifexist "art\app.ico"
  #define HasIcon
#endif
#ifexist "art\wizard.bmp"
  #define HasWizard
#endif

[Setup]
AppId={{6E1D2B34-7C59-4C0A-9F3A-2D5B8E41A7C9}
AppName={#AppFullName}
AppVersion={#AppVersion}
AppPublisher=GitHub - {#AuthorName}
AppPublisherURL=https://github.com/{#AuthorName}
AppCopyright=Copyright (c) 2026 {#AuthorName}
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AuthorName}
VersionInfoDescription={#AppFullName}
VersionInfoProductName={#AppShortName}
DefaultDirName={localappdata}\Programs\{#AppShortName}
DefaultGroupName={#AppShortName}
UsePreviousAppDir=yes
CloseApplications=yes
RestartApplications=no
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=Output
OutputBaseFilename=CLAUDIOS-Setup-{#AppVersion}
LicenseFile=..\LICENSE
UninstallDisplayName={#AppFullName}
UninstallDisplayIcon={app}\{#AppExeName}
#ifdef HasIcon
SetupIconFile=art\app.ico
#endif
#ifdef HasWizard
WizardImageFile=art\wizard.bmp
WizardSmallImageFile=art\wizard-small.bmp
#endif

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"; LicenseFile: "..\LICENSE.de.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "..\LICENSE"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "..\dist\CLAUDIOS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE.de.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.de.md"; DestDir: "{app}"; Flags: ignoreversion
#ifdef HasIcon
Source: "art\app.ico"; DestDir: "{app}"; Flags: ignoreversion
#endif

[Icons]
#ifdef HasIcon
Name: "{group}\{#AppShortName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\{#AppShortName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon
#else
Name: "{group}\{#AppShortName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppShortName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
#endif

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppShortName}}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExeName}"; Check: WizardSilent; Flags: nowait

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\CLAUDIOS\tools"
Type: filesandordirs; Name: "{localappdata}\CLAUDIOS\cache"
