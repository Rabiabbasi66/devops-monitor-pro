; =============================================================================
; DevOps Monitor Pro - Windows Client Installer (Inno Setup 6)
; =============================================================================
; Builds:  agent/dist/DevOpsMonitorAgent-Setup.exe
; Script:  agent/installer/DevOpsMonitorAgent.iss
;
; Build from the agent/ directory with build_windows.ps1 (recommended), or:
;   iscc /DApiUrl="https://your-backend/api" installer\DevOpsMonitorAgent.iss
;
; The installer:
;   1. installs DevOpsMonitorAgent.exe into Program Files
;   2. collects the enrollment token (pasted from the dashboard)
;   3. enrolls this machine via the packaged agent (--enroll-only, which
;      reuses the existing POST /api/agents/enroll flow - no duplicated logic)
;   4. installs a scheduled task so monitoring survives reboot
;   5. starts the agent status window from the Finish page
;   6. uninstalls cleanly (stops monitoring, removes task, deletes credentials)
;
; SECURITY:
;   - The API URL is the public production endpoint from build_config.ps1.
;   - No secrets, tokens or .env files are shipped inside the installer.
;   - The enrollment token is used once, in memory only; the PERMANENT agent
;     token returned by the backend is stored locally (ProgramData) and is
;     never displayed, logged or included in the uninstall log.
; =============================================================================

#define AppName "DevOps Monitor Pro Agent"
#define AppExeName "DevOpsMonitorAgent.exe"
#define AppVersion GetFileVersion(SourcePath + "\..\dist\DevOpsMonitorAgent.exe")
#define AppPublisher "DevOps Monitor Pro"
#define AppURL "https://github.com/Rabiabbasi66/devops-monitor-pro"

; Centralized production API URL (see agent/build_config.ps1).
#ifndef ApiUrl
  #define ApiUrl "https://devops-monitor-pro.vercel.app/api"
#endif

[Setup]
AppId={{B3F7A2C1-9D4E-4B8A-8F2C-1E6D5A7B9C3E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\DevOpsMonitorPro
DefaultGroupName=DevOps Monitor Pro
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=DevOpsMonitorAgent-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start monitoring automatically when this computer restarts (recommended)"; Flags: checkedonce

[Files]
Source: "..\dist\DevOpsMonitorAgent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; DestName: "README.md"; Flags: ignoreversion skipifsourcedoesntexist

[Dirs]
; Shared credential directory: enrolled by the admin user, readable by any
; local user so the agent runs for everyone on the machine.
Name: "{commonappdata}\DevOpsMonitorPro"; Permissions: users-modify

[Icons]
Name: "{group}\DevOps Monitor Pro Agent"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall DevOps Monitor Pro Agent"; Filename: "{uninstallexe}"
Name: "{autodesktop}\DevOps Monitor Pro Agent"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Open the agent status window now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM DevOpsMonitorAgent.exe /F"; Flags: runhidden; RunOnceId: "StopAgent"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN DevOpsMonitorProAgent /F"; Flags: runhidden; RunOnceId: "DelTask"

[Code]
var
  TokenPage: TInputQueryWizardPage;

{ ---------------------------------------------------------------------------
  Enrollment: run the packaged agent's --enroll-only mode (same enrollment
  endpoint as the agent GUI/CLI). The agent writes a plain-text result
  ("OK" or a human-readable error, never a token) so we can show it.
--------------------------------------------------------------------------- }
function TryEnroll(Token: string; out ResultText: string): Boolean;
var
  ExePath, ResultFile, Params: string;
  ResultCode: Integer;
  FileContents: AnsiString;
begin
  Result := False;
  ResultText := '';
  ExePath := ExpandConstant('{app}\{#AppExeName}');
  ResultFile := ExpandConstant('{tmp}\dmagent_enroll_result.txt');
  DeleteFile(ResultFile);

  Params := Format('--enroll-only "%s" --result-file "%s"', [Token, ResultFile]);
  if not Exec(ExePath, Params, ExpandConstant('{app}'), SW_SHOW,
              ewWaitUntilTerminated, ResultCode) then
  begin
    ResultText := 'Could not start the agent to complete enrollment.';
    Exit;
  end;

  if LoadStringFromFile(ResultFile, FileContents) then
    ResultText := Trim(string(FileContents));
  DeleteFile(ResultFile);

  Result := (ResultCode = 0) and (ResultText = 'OK');
end;

{ ---------------------------------------------------------------------------
  Wizard page: enrollment token (client pastes the code from the dashboard).
  Pressing Next connects the agent; an invalid/expired/used code stays on
  this page with a clear error.
--------------------------------------------------------------------------- }
procedure InitializeWizard();
begin
  TokenPage := CreateInputQueryPage(wpSelectTasks,
      'Connect Agent', 'Enter your enrollment code',
      'Paste the one-time enrollment code from your DevOps Monitor Pro dashboard' #13#10 +
      '(Servers - Install Agent - Generate Enrollment Code).' #13#10 #13#10 +
      'The code is valid for 20 minutes and can be used only once. Click Cancel ' #13#10 +
      'if you do not have a code yet - you can generate one in the dashboard.');
  TokenPage.Add('Enrollment code:');
  TokenPage.Values[0] := '';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Token, FailReason: string;
begin
  Result := True;

  if CurPageID <> TokenPage.ID then
    Exit;

  Result := False;
  Token := Trim(TokenPage.Values[0]);
  StringChangeEx(Token, '"', '', True);
  StringChangeEx(Token, '''', '', True);

  if Token = '' then
  begin
    MsgBox('Please paste the enrollment code from your dashboard first.' #13#10 #13#10 +
           'Dashboard: Servers - Install Agent - Generate Enrollment Code.',
           mbError, MB_OK);
    Exit;
  end;

  WizardForm.StatusLabel.Caption := 'Connecting this computer to the monitoring platform...';

  if TryEnroll(Token, FailReason) then
  begin
    Result := True;
    Exit;
  end;

  if FailReason = '' then
    FailReason := 'Enrollment failed. Please check the enrollment code and try again.';

  MsgBox(FailReason, mbError, MB_OK);
end;

{ ---------------------------------------------------------------------------
  Scheduled task: keeps monitoring alive after reboot (no terminal windows).
  Runs as the installing user, only when that user is logged on.
--------------------------------------------------------------------------- }
procedure InstallAutostart();
var
  ResultCode: Integer;
  TaskName, TaskCmd: string;
begin
  TaskName := 'DevOpsMonitorProAgent';
  TaskCmd := Format('"%s" --tray', [ExpandConstant('{app}\{#AppExeName}')]);
  { Idempotent: delete any previous version of the task first. }
  Exec(ExpandConstant('{sys}\schtasks.exe'), Format('/Delete /TN "%s" /F', [TaskName]),
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\schtasks.exe'),
       Format('/Create /TN "%s" /TR "%s" /SC ONLOGON /RL HIGHEST /F', [TaskName, TaskCmd]),
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if IsTaskSelected('autostart') then
      InstallAutostart();
  end;
end;

{ ---------------------------------------------------------------------------
  Uninstall: stop the agent, remove the scheduled task, delete credentials.
--------------------------------------------------------------------------- }
function InitializeUninstall(): Boolean;
begin
  Result := MsgBox('Remove DevOps Monitor Pro Agent from this computer?' #13#10 #13#10 +
                   'Monitoring will stop and locally stored agent credentials will be deleted.',
                   mbConfirmation, MB_YESNO) = IDYES;
end;

[UninstallDelete]
; Delete local agent credentials and any runtime leftovers.
Type: filesandordirs; Name: "{commonappdata}\DevOpsMonitorPro"
Type: filesandordirs; Name: "{userappdata}\DevOpsMonitorPro"
