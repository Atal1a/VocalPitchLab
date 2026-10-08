function WinGetFileAttributes(Name: String): LongWord;
  external 'GetFileAttributesW@kernel32.dll stdcall';

var
  Checks, Changes, Removed: TArrayOfString;
  BackupDir: String;
  Prepared, Committed, UpdateFailed: Boolean;
  FailureText: String;
  Progress: TOutputProgressWizardPage;

function IsPackageValidation: Boolean;
begin
  Result := ExpandConstant('{param:PACKAGEVALIDATION|0}') = '1';
end;

function Field(const Line: String; Index: Integer): String;
var S: String; P, I: Integer;
begin
  S := Line;
  for I := 0 to Index - 1 do begin
    P := Pos(#9, S);
    if P = 0 then begin Result := ''; Exit; end;
    Delete(S, 1, P);
  end;
  P := Pos(#9, S);
  if P > 0 then S := Copy(S, 1, P - 1);
  Result := S;
end;

function AppFile(const RelativeName: String): String;
var S: String;
begin
  S := RelativeName; StringChangeEx(S, '/', '\', True);
  Result := AddBackslash(ExpandConstant('{app}')) + S;
end;

function Hash(const Name: String): String;
begin
  Result := '-';
  if FileExists(Name) then Result := Lowercase(GetSHA256OfFile(Name));
end;

function SafeTree(const Name: String): Boolean;
var S, Parent: String; Attr: LongWord;
begin
  Result := False; S := Name;
  while Length(S) > 3 do begin
    Attr := WinGetFileAttributes(S);
    if (Attr <> $FFFFFFFF) and ((Attr and $400) <> 0) then Exit;
    Parent := ExtractFileDir(S);
    if Parent = S then Break;
    S := Parent;
  end;
  Result := True;
end;

procedure ClearBackup;
var I: Integer; F: String;
begin
  for I := 0 to GetArrayLength(Changes)-1 do begin
    F := BackupDir + '\' + IntToStr(I);
    DeleteFile(F); DeleteFile(F + '.hash');
  end;
  DeleteFile(BackupDir + '\ready');
  DeleteFile(BackupDir + '\committed');
  DeleteFile(BackupDir + '\registration.ini');
  RemoveDir(BackupDir);
end;

procedure RestoreBackup;
var I, J: Integer; F, H, Rel, AllowedOld, AllowedNew, Key, Version: String;
begin
  if not FileExists(BackupDir + '\ready') then begin ClearBackup; Exit; end;
  { Validate every backup before restoring any file. }
  for I := 0 to GetArrayLength(Changes)-1 do begin
    Rel := Changes[I]; AllowedOld := ''; AllowedNew := '';
    for J := 0 to GetArrayLength(Checks)-1 do
      if Field(Checks[J], 0) = Rel then begin
        AllowedOld := Field(Checks[J], 1); AllowedNew := Field(Checks[J], 2); Break;
      end;
    F := BackupDir + '\' + IntToStr(I);
    H := Trim(GetIniString('backup', 'hash', '', F + '.hash'));
    if ((H <> AllowedOld) and (H <> AllowedNew)) or
       not SafeTree(F) or not SafeTree(F + '.hash') or
       ((H <> '-') and (Hash(F) <> H)) or not SafeTree(AppFile(Rel)) then
      RaiseException('更新恢复文件不完整，请使用完整安装包修复。');
  end;
  for I := 0 to GetArrayLength(Changes)-1 do begin
    F := BackupDir + '\' + IntToStr(I);
    H := GetIniString('backup', 'hash', '', F + '.hash');
    if H = '-' then begin
      if FileExists(AppFile(Changes[I])) and not DeleteFile(AppFile(Changes[I])) then
        RaiseException('无法恢复文件，请关闭软件后重新运行更新包。');
    end else if not FileCopy(F, AppFile(Changes[I]), False) then
      RaiseException('无法恢复文件，请关闭软件后重新运行更新包。');
  end;
  if not IsPackageValidation then begin
    Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppIdentity}_is1';
    Version := GetIniString('previous', 'version', '', BackupDir + '\registration.ini');
    if Version <> '' then begin
      if not RegWriteStringValue(HKCU, Key, 'DisplayVersion', Version) or
         not RegWriteDWordValue(HKCU, Key, 'EstimatedSize',
           GetIniInt('previous', 'size', 0, 0, 2147483647, BackupDir + '\registration.ini')) then
        RaiseException('无法恢复安装记录，请使用完整安装包修复。');
    end;
  end;
  ClearBackup;
end;

function ApplicationRunning: Boolean;
var Locator, Services, Items, Item: Variant; I: Integer; ExeName, Root: String;
begin
  Result := True;
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Services := Locator.ConnectServer('', 'root\CIMV2');
    Items := Services.ExecQuery('SELECT ExecutablePath FROM Win32_Process');
    Root := Lowercase(AddBackslash(ExpandConstant('{app}')));
    for I := 0 to Items.Count-1 do begin
      Item := Items.ItemIndex(I);
      if not VarIsNull(Item.ExecutablePath) then begin
        ExeName := Lowercase(Item.ExecutablePath);
        if Pos(Root, ExeName) = 1 then Exit;
      end;
    end;
    Result := False;
  except
    Log('Cannot establish whether application is closed.');
  end;
end;

function RuntimeInstalled: Boolean;
var Installed, Major, Minor, Build: Cardinal; Key: String;
begin
  { Same minimum as the full installer's offline prerequisite. }
  Key := 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
  Result := RegQueryDWordValue(HKLM64, Key, 'Installed', Installed) and
            RegQueryDWordValue(HKLM64, Key, 'Major', Major) and
            RegQueryDWordValue(HKLM64, Key, 'Minor', Minor) and
            RegQueryDWordValue(HKLM64, Key, 'Bld', Build);
  if Result then Result := (Installed = 1) and ((Major > 14) or
    ((Major = 14) and ((Minor > 51) or ((Minor = 51) and (Build >= 36247)))));
end;

procedure InitializeWizard;
begin
  Progress := CreateOutputProgressPage('检查安装文件', '正在验证运行环境和模型。');
  ExtractTemporaryFile('checks.tsv'); ExtractTemporaryFile('changed.txt');
  ExtractTemporaryFile('removed.tsv');
  if not LoadStringsFromFile(ExpandConstant('{tmp}\checks.tsv'), Checks) or
     not LoadStringsFromFile(ExpandConstant('{tmp}\changed.txt'), Changes) or
     not LoadStringsFromFile(ExpandConstant('{tmp}\removed.tsv'), Removed) then
    RaiseException('更新包不完整，请重新下载。');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var I: Integer; Actual, Rel, Ver, Key, PreviousDir, PreviousVersion: String; PreviousSize: Cardinal;
begin
  Result := ''; Prepared := False; Committed := False; UpdateFailed := False;
  BackupDir := ExpandConstant('{app}\.vpl-update-{#AppVersion}');
  try
    if not DirExists(ExpandConstant('{app}')) or not SafeTree(BackupDir) then
      RaiseException('未找到支持的安装目录，请使用完整安装包。');
    if ApplicationRunning then RaiseException('请关闭 VocalPitchLab 后再更新。');
    if not RuntimeInstalled then RaiseException('微软运行组件不完整，请使用完整安装包修复。');
    if FileExists(BackupDir + '\committed') then ClearBackup
    else if DirExists(BackupDir) then RestoreBackup;
    if not GetVersionNumbersString(AppFile('VocalPitchLab.exe'), Ver) or
       ((Ver <> '{#FromVersion}.0') and (Ver <> '{#AppVersion}.0')) then
      RaiseException('此更新包适用于 {#FromVersion}，其他版本请使用完整安装包。');
    Progress.Show;
    try
      for I := 0 to GetArrayLength(Checks)-1 do begin
        Rel := Field(Checks[I], 0);
        if not SafeTree(AppFile(Rel)) then RaiseException('安装目录包含链接，请使用完整安装包修复。');
        Actual := Hash(AppFile(Rel));
        if (Actual <> Field(Checks[I], 1)) and (Actual <> Field(Checks[I], 2)) then
          RaiseException('文件缺失或已修改：' + Rel + '。请使用完整安装包修复。');
        if (I mod 32) = 0 then Progress.SetProgress(I, GetArrayLength(Checks));
      end;
      if not ForceDirectories(BackupDir) then RaiseException('无法创建更新备份。');
      if not IsPackageValidation then begin
        Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppIdentity}_is1';
        if RegQueryStringValue(HKCU, Key, 'Inno Setup: App Path', PreviousDir) and
           (CompareText(RemoveBackslashUnlessRoot(PreviousDir), RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) = 0) then begin
          PreviousSize := 0;
          RegQueryStringValue(HKCU, Key, 'DisplayVersion', PreviousVersion);
          RegQueryDWordValue(HKCU, Key, 'EstimatedSize', PreviousSize);
          if not SetIniString('previous', 'version', PreviousVersion, BackupDir + '\registration.ini') or
             not SetIniString('previous', 'size', IntToStr(PreviousSize), BackupDir + '\registration.ini') then
            RaiseException('无法备份安装记录。');
        end;
      end;
      for I := 0 to GetArrayLength(Changes)-1 do begin
        Rel := AppFile(Changes[I]); Actual := Hash(Rel);
        if (Actual <> '-') and not FileCopy(Rel, BackupDir + '\' + IntToStr(I), False) then
          RaiseException('无法备份文件，请检查磁盘空间和文件权限。');
        if (Actual <> '-') and (Hash(BackupDir + '\' + IntToStr(I)) <> Actual) then
          RaiseException('更新备份校验失败，请检查磁盘空间。');
        if not SetIniString('backup', 'hash', Actual, BackupDir + '\' + IntToStr(I) + '.hash') then
          RaiseException('无法保存更新备份。');
      end;
      if not SaveStringToFile(BackupDir + '\ready', '{#FromVersion}-{#AppVersion}', False) then
        RaiseException('无法保存更新状态。');
      Prepared := True;
    finally Progress.Hide; end;
  except Result := GetExceptionMessage; end;
end;

procedure CheckUpdatedFile(const RelativeName, ExpectedHash: String);
begin
  try
    if Hash(AppFile(RelativeName)) <> ExpectedHash then
      RaiseException('更新校验失败：' + RelativeName);
#ifdef UpdateTestFailure
    RaiseException('Injected update failure');
#endif
  except
    UpdateFailed := True;
    FailureText := GetExceptionMessage;
    Log('Update verification failed: ' + FailureText);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var I: Integer; Rel: String;
begin
  if CurStep = ssInstall then begin
    if not Prepared or ApplicationRunning then begin
      UpdateFailed := True; FailureText := '请关闭 VocalPitchLab 后再更新。';
      Log(FailureText); Abort;
    end;
    for I := 0 to GetArrayLength(Changes)-1 do
      if not SafeTree(AppFile(Changes[I])) then begin
        UpdateFailed := True; FailureText := '安装目录发生变化，请重新运行更新包。';
        Log(FailureText); Abort;
      end;
  end;
  if CurStep = ssPostInstall then begin
    { Replacements were hashed by their AfterInstall callbacks before commit. }
    if not UpdateFailed then
      if not SaveStringToFile(BackupDir + '\committed', '1', False) then begin
        UpdateFailed := True; FailureText := '无法保存更新完成状态。';
      end;
    if UpdateFailed then begin
      try
        RestoreBackup; Prepared := False;
        FailureText := '更新未完成，原文件已恢复。请重新运行更新包或使用完整安装包。';
      except FailureText := '更新未完成，恢复失败。请使用完整安装包修复。'; end;
      Log(FailureText);
      Exit;
    end;
    Committed := True;
    for I := 0 to GetArrayLength(Removed)-1 do begin
      Rel := AppFile(Field(Removed[I], 0));
      if SafeTree(Rel) and (Hash(Rel) = Field(Removed[I], 1)) then
        if not DeleteFile(Rel) then Log('Retained obsolete file: ' + Field(Removed[I], 0));
    end;
    ClearBackup;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and UpdateFailed then begin
    WizardForm.FinishedHeadingLabel.Caption := '更新未完成';
    WizardForm.FinishedLabel.Caption := FailureText;
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  if UpdateFailed then Result := 8 else Result := 0;
end;

procedure DeinitializeSetup;
begin
  if Prepared and not Committed then begin
    try RestoreBackup;
    except Log('Recovery required: ' + GetExceptionMessage); end;
  end;
end;
