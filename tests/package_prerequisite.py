"""Exercise the real Inno prerequisite flow with isolated runtime responses."""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,default=ROOT/'work/installer-tools/inno/ISCC.exe')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    source=(ROOT/'installer/vc_redist.iss').read_text(encoding='utf-8-sig')
    # Replace only the OS-facing runtime detection and execution. The actual
    # PrepareToInstall and NeedRestart event implementations remain unchanged.
    source,count=re.subn(r'function HasVCRuntime: Boolean;\s*begin.*?\nend;',
        'function HasVCRuntime: Boolean;\nbegin\n  Result := TestRuntimePresent;\nend;',source,count=1,flags=re.S)
    assert count==1
    source=source.replace('  VCRestartPending: Boolean;',
        '  VCRestartPending, TestRuntimePresent: Boolean;\n  TestRuntimeCalls: Integer;')
    source=source.replace("  if not ShellExec('runas', RuntimeFile,","  if not TestShellExec('runas', RuntimeFile,")
    insertion=r'''
function TestShellExec(Operation, FileName, Parameters, WorkingDir: String;
  ShowCmd: Integer; Wait: TExecWait; var ExitCode: Integer): Boolean;
begin
  TestRuntimeCalls := TestRuntimeCalls + 1;
  if Pos('/norestart', Lowercase(Parameters)) = 0 then
    RaiseException('Prerequisite must not restart Windows itself');
  ExitCode := StrToInt(ExpandConstant('{param:TESTEXIT|0}'));
  TestRuntimePresent := ExpandConstant('{param:TESTPRESENT|1}') = '1';
  Result := ExitCode <> 1223;
end;
'''
    source=source.replace('function PrepareToInstall(',insertion+'\nfunction PrepareToInstall(',1)
    (output/'vc_redist-test.iss').write_text(source,encoding='utf-8-sig')
    (output/'payload.txt').write_text('Installation completed before restart.\n')
    harness=r'''
[Setup]
AppName=VocalPitchLab prerequisite QA
AppVersion=1.0
AppId=VocalPitchLab.PrerequisiteQA
DefaultDirName={localappdata}\VocalPitchLab-PrerequisiteQA
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Uninstallable=no
CreateUninstallRegKey=no
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
OutputDir=.
OutputBaseFilename=prerequisite-qa
Compression=lzma2/fast
[Files]
Source: "payload.txt"; DestDir: "{app}"
#include "vc_redist-test.iss"
[Code]
procedure InitializeWizard;
begin
  TestRuntimePresent := ExpandConstant('{param:TESTALREADY|0}') = '1';
end;
procedure CurStepChanged(CurStep: TSetupStep);
var MessageText: String; EarlyRestart: Boolean;
begin
  if CurStep = ssPostInstall then begin
    { A repeated preparation must not rerun an already successful prerequisite. }
    EarlyRestart := False;
    MessageText := PrepareToInstall(EarlyRestart);
    if (MessageText <> '') or EarlyRestart then
      RaiseException('Successful prerequisite must not block application installation');
    SaveStringToFile(ExpandConstant('{app}\completed.txt'), 'complete', False);
  end;
end;
procedure DeinitializeSetup;
begin
  SaveStringToFile(ExpandConstant('{param:TESTREPORT}'),
    'calls=' + IntToStr(TestRuntimeCalls) + #13#10 +
    'restart=' + IntToStr(Ord(NeedRestart)), False);
end;
'''
    (output/'test.iss').write_text(harness,encoding='utf-8-sig')
    runtime=ROOT/'work/installer-tools/prerequisites/vc_redist.x64.exe'
    result=subprocess.run([str(args.compiler.resolve()),'/Q',f'/DVCRedistPath={runtime}',str(output/'test.iss')],capture_output=True,text=True)
    (output/'compile.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError('Compile failed; see compile.log')
    cases=[('already-installed',0,True,True,0,False),('installed',0,False,True,0,False),
           ('newer-installed',1638,False,True,0,False),('reboot-required',3010,False,False,3010,True),
           ('reboot-status',1641,False,False,3010,True),('runtime-missing',0,False,False,None,False),
           ('runtime-error',1603,False,False,None,False),('elevation-cancelled',1223,False,False,None,False)]
    results=[]
    for name,code,already,present,expected,restart in cases:
        target=output/name;report=output/(name+'.txt')
        command=[str(output/'prerequisite-qa.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/RESTARTEXITCODE=3010',
                 f'/DIR={target}',f'/TESTEXIT={code}',f'/TESTALREADY={int(already)}',f'/TESTPRESENT={int(present)}',
                 f'/TESTREPORT={report}',f'/LOG={output/(name+".log")}']
        run=subprocess.run(command,timeout=90,capture_output=True)
        values=dict(line.split('=',1) for line in report.read_text().splitlines())
        installed=(target/'payload.txt').exists() and (target/'completed.txt').exists()
        assert int(values['calls'])==(0 if already else 1),(name,values)
        assert bool(int(values['restart']))==restart,(name,values)
        if expected is None:assert run.returncode not in (0,3010) and not installed,(name,run.returncode)
        else:assert run.returncode==expected and installed,(name,run.returncode)
        results.append(dict(case=name,exit_code=run.returncode,installed=installed,restart_at_end=restart))
        print(name+' passed',flush=True)
    (output/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')


if __name__=='__main__':main()
