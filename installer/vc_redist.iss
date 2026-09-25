; Keep the version/hash synchronized with resources/vc-redist.json.
#ifndef VCRedistPath
  #define VCRedistPath AddBackslash(SourcePath) + "..\work\installer-tools\prerequisites\vc_redist.x64.exe"
#endif
#if !FileExists(VCRedistPath)
  #error Offline VC++ runtime missing. See installer/BUILD.md; define VCRedistPath if stored elsewhere.
#endif

[Files]
; Extracted on demand before application installation; never remove shared runtimes on uninstall.
Source: "{#VCRedistPath}"; DestName: "vpl-vc-redist.x64.exe"; Flags: dontcopy noencryption

[Code]
var
  VCRestartPending: Boolean;

function HasVCRuntimeInView(RootKey: Integer): Boolean;
var
  Installed, Major, Minor, Build: Cardinal;
  Key: String;
begin
  Result := False;
  Key := 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
  if not RegQueryDWordValue(RootKey, Key, 'Installed', Installed) then Exit;
  if Installed <> 1 then Exit;
  if not RegQueryDWordValue(RootKey, Key, 'Major', Major) then Exit;
  if not RegQueryDWordValue(RootKey, Key, 'Minor', Minor) then Exit;
  if not RegQueryDWordValue(RootKey, Key, 'Bld', Build) then Exit;
  Result := (Major > 14) or ((Major = 14) and ((Minor > 51) or
    ((Minor = 51) and (Build >= 36247))));
end;

function HasVCRuntime: Boolean;
begin
  Result := HasVCRuntimeInView(HKLM64) or HasVCRuntimeInView(HKLM32);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  RuntimeFile, LogDir, LogFile: String;
  ExitCode: Integer;
begin
  Result := '';
  if VCRestartPending then begin
    NeedsRestart := True;
    Result := '运行组件需要重启。请重启 Windows 后重新运行安装程序。';
    Exit;
  end;
  if HasVCRuntime then Exit;
  WizardForm.PreparingLabel.Caption := '正在安装必要的运行组件，请稍候。系统可能请求管理员权限。';
  ExtractTemporaryFile('vpl-vc-redist.x64.exe');
  RuntimeFile := ExpandConstant('{tmp}\vpl-vc-redist.x64.exe');
  if CompareText(GetSHA256OfFile(RuntimeFile),
      '843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c') <> 0 then begin
    Result := '运行组件文件损坏，请重新下载完整安装包。';
    Exit;
  end;
  LogDir := ExpandConstant('{localappdata}\VocalPitchLab\installer-logs');
  if not ForceDirectories(LogDir) then begin
    Result := '无法创建安装日志目录：' + LogDir;
    Exit;
  end;
  LogFile := LogDir + '\vc-redist-' + GetDateTimeString('yyyymmdd-hhnnss', '-', ':') + '.log';
  if not ShellExec('runas', RuntimeFile,
      '/install /quiet /norestart /log "' + LogFile + '"', '',
      SW_HIDE, ewWaitUntilTerminated, ExitCode) then begin
    Result := '必要运行组件未安装。请允许管理员权限后重试。' + #13#10 + SysErrorMessage(ExitCode);
    Exit;
  end;
  Log('VC++ runtime installer exit code: ' + IntToStr(ExitCode));
  if (ExitCode = 3010) or (ExitCode = 1641) then begin
    VCRestartPending := True;
    NeedsRestart := True;
    Result := '运行组件需要重启。请保存工作、重启 Windows，然后重新运行安装程序。';
    Exit;
  end;
  if ((ExitCode = 0) or (ExitCode = 1638)) and HasVCRuntime then Exit;
  Result := '必要运行组件安装未完成（代码 ' + IntToStr(ExitCode) + '）。请重试。' + #13#10 +
    '诊断日志：' + LogFile;
end;
