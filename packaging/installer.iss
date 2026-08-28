; Inno Setup script for FocusGuard.
;
; Build with:
;   iscc /DAppVersion=1.0.0 packaging\installer.iss
;
; build.ps1 passes AppVersion from core/version.py so it cannot drift.
;
; Installs per-user (no admin prompt), which matters twice over: the app only
; ever writes to %LOCALAPPDATA%, and an installer that demands elevation for a
; utility like this is one more reason for someone to cancel.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName        "FocusGuard"
#define AppPublisher   "FocusGuard"
#define AppExeName     "FocusGuard.exe"
#define AppURL         "https://focusguard.app"

[Setup]
; Generated once and never changed: Windows uses it to recognise upgrades of
; the same product. A new GUID here means every update installs alongside the
; old version instead of replacing it.
AppId={{7B3F2C14-8E5A-4D91-A6B2-3C9F1E4D7A08}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
VersionInfoVersion={#AppVersion}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\PRIVACY.md
OutputDir=..\dist\installer
OutputBaseFilename={#AppName}-{#AppVersion}-setup
SetupIconFile=..\FocusGuard.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; Per-user install: no UAC prompt, no admin rights needed.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; \
  GroupDescription: "Additional shortcuts:"
Name: "startupicon"; Description: "Start {#AppName} when I sign in"; \
  GroupDescription: "Startup:"; Flags: unchecked

[Files]
; The whole PyInstaller folder build.
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
  Tasks: desktopicon

[Registry]
; Start-with-Windows entry. uninsdeletevalue is what makes uninstall actually
; clean: without it the Run key survives and Windows keeps trying to launch a
; program that is no longer there.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
{ FocusGuard may be running from the tray when an upgrade or uninstall starts.
  Left running, its files are locked and the install silently half-fails. }
function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec(ExpandConstant('{cmd}'),
          '/C tasklist /FI "IMAGENAME eq {#AppExeName}" | find /I "{#AppExeName}"',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
end;

procedure StopApp();
var
  ResultCode: Integer;
begin
  if IsAppRunning() then
  begin
    Exec(ExpandConstant('{cmd}'), '/C taskkill /IM "{#AppExeName}" /F',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1200);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopApp();
  Result := '';
end;

{ On uninstall, offer to remove the user's recorded data too.

  Asked rather than assumed, in both directions: deleting someone's usage
  history without asking is destructive, and leaving it behind after they
  uninstalled is the "uninstall does not really uninstall" complaint. The
  default is to keep it, because reinstalling and finding your history intact
  is the friendlier surprise. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usUninstall then
    StopApp();

  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\{#AppName}');
    if DirExists(DataDir) then
    begin
      if MsgBox('Also delete your FocusGuard data?' + #13#10#13#10 +
                'This removes your usage history, tracked app list, settings ' +
                'and logs from:' + #13#10 + DataDir + #13#10#13#10 +
                'Choose No to keep them for a future reinstall.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
