"""Check update/uninstall log merging with a QA identity and a small payload."""
import argparse
import json
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
from package_benchmark import ROOT, manifest, verify


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--old-stage',type=Path,required=True)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists():raise SystemExit('Choose a fresh directory')
    out.mkdir(parents=True);old=out/'old';new=out/'new';old.mkdir();new.mkdir()
    for source,dest in ((a.old_stage,old),(a.stage,new)):
        for rel in ('VocalPitchLab.exe','INSTALLATION.md','CHANGELOG.md','assets/vocalpitch.ico'):
            (dest/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/rel,dest/rel)
        (dest/'runtime').mkdir();(dest/'runtime/fixture.txt').write_text('retained dependency')
    compiler=ROOT/'work/installer-tools/inno/ISCC.exe'
    identity='VocalPitchLab.UpdateQA';title='VocalPitchLab Update QA'
    keyname='Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\'+identity+'_is1'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,keyname):pass
        raise SystemExit('QA identity already installed')
    except FileNotFoundError:pass
    target=out/'注册更新';group=title
    # Include a file only in the old installer; uninstall must still remember it.
    (old/'baseline-only.txt').write_text('old uninstall record')
    base=out/'base.iss'
    base.write_text(f'''[Setup]
AppId={identity}
AppName={title}
AppVersion=1.1.0
DefaultDirName={target}
DefaultGroupName={group}
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={out}
OutputBaseFilename=baseline-setup
UninstallDisplayIcon={{app}}\\assets\\vocalpitch.ico
[Files]
Source: "{old}\\*"; DestDir: "{{app}}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{{group}}\\{title}"; Filename: "{{app}}\\VocalPitchLab.exe"; IconFilename: "{{app}}\\assets\\vocalpitch.ico"
''',encoding='utf-8-sig')
    subprocess.run([str(compiler),'/Q',str(base)],check=True)
    subprocess.run([sys.executable,'-B',str(ROOT/'installer/build_update.py'),'--baseline',str(old),
        '--stage',str(new),'--output',str(out/'update'),'--from-version','1.1.0','--version','1.1.1'],check=True)
    script=(ROOT/'installer/Update.iss').read_text(encoding='utf-8')
    script=script.replace('#define AppIdentity "VocalPitchLab.LocalPreview"','#define AppIdentity "'+identity+'"')
    script=script.replace('AppName=VocalPitchLab\n','AppName='+title+'\n')
    script=script.replace('SetupMutex=VocalPitchLab.Update','SetupMutex='+identity)
    script=script.replace('SetupIconFile=..\\assets\\vocalpitch.ico','SetupIconFile='+str(ROOT/'assets/vocalpitch.ico'))
    script=script.replace('LicenseFile=..\\LICENSE','LicenseFile='+str(ROOT/'LICENSE'))
    script=script.replace('#include "update_guard.iss"','#include "'+str(ROOT/'installer/update_guard.iss')+'"')
    update_script=out/'update.iss';update_script.write_text(script,encoding='utf-8-sig')
    subprocess.run([str(compiler),'/Q',f'/DUpdateDir={out/"update"}','/DAppVersion=1.1.1','/DFromVersion=1.1.0',str(update_script)],check=True)
    (out/'failure').mkdir()
    subprocess.run([str(compiler),'/Q',f'/DUpdateDir={out/"update"}','/DAppVersion=1.1.1','/DFromVersion=1.1.0',
        '/DUpdateTestFailure',f'/O{out/"failure"}',str(update_script)],check=True)
    common=['/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/DIR={target}',f'/GROUP={group}']
    sentinel=out/'user-data.json';sentinel.write_text('{"preserve":true}')
    installed=False
    try:
        subprocess.run([str(out/'baseline-setup.exe'),*common,f'/LOG={out/"install.log"}'],check=True);installed=True
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,keyname) as key:
            assert winreg.QueryValueEx(key,'DisplayVersion')[0]=='1.1.0'
        failure=subprocess.run([str(next((out/'failure').glob('*.exe'))),*common,f'/LOG={out/"failure.log"}'],timeout=180)
        assert failure.returncode==8,failure.returncode
        verify(target,manifest(old))
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,keyname) as key:
            assert winreg.QueryValueEx(key,'DisplayVersion')[0]=='1.1.0'
        print('PASS registered failure rollback',flush=True)
        update=next((out/'update').glob('*.exe'))
        for name in ('update','repeat'):
            subprocess.run([str(update),*common,f'/LOG={out/(name+".log")}'],check=True,timeout=180)
            verify(target,manifest(new))
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,keyname) as key:
                assert winreg.QueryValueEx(key,'DisplayVersion')[0]=='1.1.1'
            assert len(list(target.glob('unins*.exe')))==1
            print('PASS registered '+name,flush=True)
        assert sentinel.read_text()=='{"preserve":true}'
    finally:
        if installed:subprocess.run([str(target/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/LOG={out/"uninstall.log"}'],check=True)
    assert not (target/'VocalPitchLab.exe').exists()
    assert not (target/'baseline-only.txt').exists()
    assert not (target/'runtime/fixture.txt').exists()
    assert sentinel.read_text()=='{"preserve":true}'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,keyname):pass
        raise AssertionError('QA registration still exists')
    except FileNotFoundError:pass
    (out/'result.json').write_text(json.dumps(dict(registered_update=True,registered_repeat=True,failed_update_restores_version=True,
        merged_uninstall_log=True,uninstall_removed_original_and_updated_files=True,user_data_preserved=True,
        scope='Small fixture payload with QA-only installation identity'),indent=2))
    print('PASS uninstall after update',flush=True)


if __name__=='__main__':main()
