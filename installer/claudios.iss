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
  #define AppVersion "1.1.1"
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

[InstallDelete]
; Programmdateien der alten Version entfernen (Reste verhindern); Einstellungen und Berichte liegen außerhalb und bleiben erhalten.
Type: filesandordirs; Name: "{app}\_internal"

; Was beim Deinstallieren aus den Programmdaten gelöscht wird, wählt der Nutzer im Code unten (Standard: Werkzeuge,
; Zwischenspeicher und Protokolle ja, Einstellungen, Verlauf und Berichte nein; still: nur der Standard).

[CustomMessages]
german.UpdateAsk={#AppShortName} %1 ist bereits installiert. Die neue Version ist %2.%nSoll auf %2 aktualisiert werden? Deine Einstellungen und Berichte bleiben erhalten.
english.UpdateAsk={#AppShortName} %1 is already installed. The new version is %2.%nUpdate to %2? Your settings and reports are kept.
german.SameAsk={#AppShortName} %1 ist bereits installiert.%nSoll sie neu installiert (repariert) werden? Deine Daten bleiben erhalten.
english.SameAsk={#AppShortName} %1 is already installed.%nReinstall (repair) it? Your data is kept.
german.UniTitle=Was soll gelöscht werden?
english.UniTitle=What should be deleted?
german.UniHint=Angehakte Einträge werden gelöscht. Deine eigenen Daten sind nicht vorgewählt. Gespeicherte API-Schlüssel entfernst du im Programm über den Papierkorb-Knopf.
english.UniHint=Ticked items will be deleted. Your own data is not preselected. Remove stored API keys in the program with the trash button.
german.UniTools=Prüfwerkzeuge und Zwischenspeicher (werden bei Bedarf neu geladen)
english.UniTools=Check tools and cache (downloaded again on demand)
german.UniLogs=Protokolldateien
english.UniLogs=Log files
german.UniConfig=Einstellungen (deine Daten)
english.UniConfig=Settings (your data)
german.UniHistory=Verlauf der Scans (deine Daten)
english.UniHistory=Scan history (your data)
german.UniReports=Gespeicherte Berichte (deine Daten)
english.UniReports=Saved reports (your data)
german.OlderAsk=Es ist bereits eine NEUERE Version (%1) installiert als diese (%2).%nTrotzdem auf %2 zurückstellen? Deine Daten bleiben erhalten.
english.OlderAsk=A NEWER version (%1) is already installed than this one (%2).%nDowngrade to %2 anyway? Your data is kept.

[Code]
const
  UninstKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6E1D2B34-7C59-4C0A-9F3A-2D5B8E41A7C9}_is1';

function VerPart(var S: String): Integer;
var P: Integer;
begin
  P := Pos('.', S);
  if P = 0 then begin Result := StrToIntDef(S, 0); S := ''; end
  else begin Result := StrToIntDef(Copy(S, 1, P - 1), 0); Delete(S, 1, P); end;
end;

function CompareVer(A, B: String): Integer;
var I, X, Y: Integer;
begin
  Result := 0;
  for I := 1 to 4 do
  begin
    X := VerPart(A); Y := VerPart(B);
    if X < Y then begin Result := -1; Exit; end;
    if X > Y then begin Result := 1; Exit; end;
  end;
end;

{ Stille Aktualisierung (Update im Programm: /SILENT) fragt nie nach. }
function InitializeSetup(): Boolean;
var Old, Msg: String; C: Integer;
begin
  Result := True;
  if not (RegQueryStringValue(HKCU, UninstKey, 'DisplayVersion', Old) or
          RegQueryStringValue(HKLM, UninstKey, 'DisplayVersion', Old)) then Exit;
  if WizardSilent then Exit;
  C := CompareVer(Old, '{#AppVersion}');
  if C < 0 then Msg := FmtMessage(CustomMessage('UpdateAsk'), [Old, '{#AppVersion}'])
  else if C = 0 then Msg := FmtMessage(CustomMessage('SameAsk'), [Old])
  else Msg := FmtMessage(CustomMessage('OlderAsk'), [Old, '{#AppVersion}']);
  Result := MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES;
end;

{ ---- Deinstallation: Auswahl, was aus den Programmdaten gelöscht wird ---- }
var
  DelTools, DelLogs, DelConfig, DelHistory, DelReports: Boolean;

function InitializeUninstall(): Boolean;
var
  Form: TSetupForm;
  List: TNewCheckListBox;
  Hint: TNewStaticText;
  OkBtn, CancelBtn: TNewButton;
begin
  Result := True;
  DelTools := True; DelLogs := True; DelConfig := False; DelHistory := False; DelReports := False;
  if UninstallSilent then Exit;
  Form := CreateCustomForm(ScaleX(440), ScaleY(300), False, True);
  try
    Form.Caption := CustomMessage('UniTitle');
    Form.Position := poScreenCenter;
    Hint := TNewStaticText.Create(Form);
    Hint.Parent := Form;
    Hint.Left := ScaleX(12); Hint.Top := ScaleY(10); Hint.Width := Form.ClientWidth - ScaleX(24);
    Hint.AutoSize := False; Hint.WordWrap := True; Hint.Height := ScaleY(48);
    Hint.Caption := CustomMessage('UniHint');
    List := TNewCheckListBox.Create(Form);
    List.Parent := Form;
    List.Left := ScaleX(12); List.Top := ScaleY(62); List.Width := Form.ClientWidth - ScaleX(24); List.Height := ScaleY(170);
    List.AddCheckBox(CustomMessage('UniTools'), '', 0, True, True, False, True, nil);
    List.AddCheckBox(CustomMessage('UniLogs'), '', 0, True, True, False, True, nil);
    List.AddCheckBox(CustomMessage('UniConfig'), '', 0, False, True, False, True, nil);
    List.AddCheckBox(CustomMessage('UniHistory'), '', 0, False, True, False, True, nil);
    List.AddCheckBox(CustomMessage('UniReports'), '', 0, False, True, False, True, nil);
    OkBtn := TNewButton.Create(Form);
    OkBtn.Parent := Form; OkBtn.Caption := SetupMessage(msgButtonOK); OkBtn.ModalResult := mrOk; OkBtn.Default := True;
    OkBtn.Left := Form.ClientWidth - ScaleX(180); OkBtn.Top := ScaleY(250); OkBtn.Width := ScaleX(80); OkBtn.Height := ScaleY(26);
    CancelBtn := TNewButton.Create(Form);
    CancelBtn.Parent := Form; CancelBtn.Caption := SetupMessage(msgButtonCancel); CancelBtn.ModalResult := mrCancel;
    CancelBtn.Cancel := True;
    CancelBtn.Left := Form.ClientWidth - ScaleX(92); CancelBtn.Top := ScaleY(250); CancelBtn.Width := ScaleX(80); CancelBtn.Height := ScaleY(26);
    if Form.ShowModal() = mrOk then
    begin
      DelTools := List.Checked[0]; DelLogs := List.Checked[1]; DelConfig := List.Checked[2];
      DelHistory := List.Checked[3]; DelReports := List.Checked[4];
    end
    else
      Result := False;
  finally
    Form.Free();
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Base: String;
begin
  if CurUninstallStep <> usPostUninstall then Exit;
  Base := ExpandConstant('{localappdata}\CLAUDIOS');
  if DelTools then begin
    DelTree(Base + '\tools', True, True, True);
    DelTree(Base + '\cache', True, True, True);
  end;
  if DelLogs then DelTree(Base + '\logs', True, True, True);
  if DelConfig then DelTree(Base + '\config', True, True, True);
  if DelHistory then DelTree(Base + '\history', True, True, True);
  if DelReports then DelTree(ExpandConstant('{userdocs}\CLAUDIOS\Reports'), True, True, True);
end;
