"""Exercise upgrade cleanup in an isolated installed directory."""
import argparse,json,shutil,sys,winreg
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
from package_benchmark import measure,verify,digest

def registration():
    name=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\VocalPitchLab.LocalPreview_is1'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,name) as key:
            values=[];i=0
            while True:
                try:values.append(winreg.EnumValue(key,i));i+=1
                except OSError:break
            return values
    except FileNotFoundError:return None

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--old-install',type=Path,required=True);p.add_argument('--installer',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--removals',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or out.is_relative_to(a.old_install.resolve()):raise SystemExit('Choose a fresh validation directory outside the old installation')
    out.mkdir(parents=True);target=out/'覆盖更新 with spaces';shutil.copytree(a.old_install,target)
    original_registration=registration()
    fixture=target/'unrelated-user-file.txt';fixture.write_text('preserve',encoding='utf-8')
    data=out/'user-data';data.mkdir();(data/'library.json').write_text('{"songs":[{"name":"preserve"}]}')
    data_hash=digest(data/'library.json')
    rows=json.loads(a.manifest.read_text(encoding='utf-8'));removed=json.loads(a.removals.read_text(encoding='utf-8'))['files']
    modified=next(r['path'] for r in removed if r['path'].endswith('/qmldir'))
    (target/modified).write_text('externally modified fixture',encoding='utf-8')
    checks=[]
    for name in ('upgrade','same-version'):
        metrics=measure([str(a.installer.resolve()),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/PACKAGEVALIDATION=1','/NOCLOSEAPPLICATIONS',f'/DIR={target}',f'/LOG={out/(name+"-setup.log")}'],out/(name+'.log'))
        verification=verify(target,rows)
        assert all(not (target/r['path']).exists() for r in removed if r['path']!=modified)
        assert (target/modified).read_text()=='externally modified fixture'
        assert fixture.read_text()=='preserve' and digest(data/'library.json')==data_hash
        assert registration()==original_registration
        checks.append(dict(scenario=name,install=metrics,verification=verification,obsolete_removed=len(removed)-1,modified_obsolete_preserved=True,unrelated_file_preserved=True,external_user_data_preserved=True,registration_unchanged=True))
        (out/'results.json').write_text(json.dumps(checks,indent=2))
        print(name+' PASS',flush=True)

if __name__=='__main__':main()
