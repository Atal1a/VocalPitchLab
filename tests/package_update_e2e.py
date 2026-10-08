"""Exercise the real offline updater only in a fresh isolated directory."""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'installer'))
from package_benchmark import digest, verify


def run_installer(exe, target, log, success=True):
    start=time.monotonic()
    result=subprocess.run([str(exe), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
        '/NOICONS', '/NOCLOSEAPPLICATIONS', '/PACKAGEVALIDATION=1', f'/DIR={target}',
        f'/LOG={log}'], capture_output=True, timeout=600)
    if (result.returncode==0) != success:
        raise AssertionError(f'{log}: unexpected installer exit {result.returncode}')
    return dict(exit_code=result.returncode, seconds=round(time.monotonic()-start,3))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-installer',type=Path,required=True)
    p.add_argument('--update',type=Path,required=True)
    p.add_argument('--failure-update',type=Path,required=True)
    p.add_argument('--plan-dir',type=Path,required=True)
    p.add_argument('--old-launcher',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--recovery-only',action='store_true')
    a=p.parse_args();out=a.output.resolve()
    if out.exists() and not a.recovery_only:raise SystemExit('Choose a fresh test directory')
    out.mkdir(parents=True,exist_ok=a.recovery_only);target=out/'升级 中文 path'
    before=json.loads((a.plan_dir/'baseline-manifest.json').read_text(encoding='utf-8'))
    after=json.loads((a.plan_dir/'target-manifest.json').read_text(encoding='utf-8'))
    plan=json.loads((a.plan_dir/'plan.json').read_text(encoding='utf-8'))
    result=json.loads((out/'results.json').read_text()) if a.recovery_only else {}
    def save(name,data):
        result[name]=data;(out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print('PASS '+name,flush=True)
    def update(name,success=True,exe=None):
        return run_installer((exe or a.update).resolve(),target,out/(name+'.log'),success)
    def reject_file(name,rel,missing=False):
        file=target/rel;original=file.read_bytes();file.unlink() if missing else file.write_bytes(b'corrupt fixture')
        launcher_hash=digest(target/'VocalPitchLab.exe')
        try:
            data=update(name,False)
            assert digest(target/'VocalPitchLab.exe')==launcher_hash
            assert (not file.exists()) if missing else file.read_bytes()==b'corrupt fixture'
        finally:file.write_bytes(original)
        save(name,data)

    if not a.recovery_only:
        save('empty_directory_rejected',run_installer(a.update.resolve(),out/'empty',out/'empty.log',False))
        save('published_baseline_installed',run_installer(a.baseline_installer.resolve(),target,out/'baseline.log'))
    save('baseline_hashes',verify(target,before))
    if not a.recovery_only:
        source_exe=(target/'VocalPitchLab.exe').read_bytes()
        shutil.copy2(a.old_launcher,target/'VocalPitchLab.exe')
        save('unsupported_version_rejected',update('wrong-version',False))
        (target/'VocalPitchLab.exe').write_bytes(source_exe)
        reject_file('changed_code_rejected','main.py')
        reject_file('missing_runtime_rejected','runtime/python.exe',True)
        reject_file('changed_dependency_rejected','runtime/Lib/site-packages/PySide6/Qt6Core.dll')
        model=next(r['path'] for r in before if r['path'].startswith('models/') and r['bytes']>1024)
        original=target/model;hidden=original.with_name(original.name+'.qa-disabled');original.rename(hidden)
        try:save('missing_model_rejected',update('missing-model',False))
        finally:hidden.rename(original)
        process=subprocess.Popen([str(target/'runtime/python.exe'),'-I','-S','-c','import time; time.sleep(90)'])
        try:save('running_application_rejected',update('running',False))
        finally:process.terminate();process.wait(timeout=20)
    # Fail after Inno has overwritten the first file; verify that all old bytes return.
    save('write_failure_rejected',update('write-failure',False,a.failure_update))
    save('write_failure_rollback',verify(target,before))
    assert not (target/'.vpl-update-1.1.1/ready').exists()
    # Simulate interrupted installation with a durable, valid backup journal.
    backup=target/'.vpl-update-1.1.1';backup.mkdir(exist_ok=True)
    for i,row in enumerate(plan['changed']):
        file=target/row['path'];h=digest(file) if file.exists() else '-'
        if file.exists():shutil.copy2(file,backup/str(i))
        (backup/(str(i)+'.hash')).write_text('[backup]\nhash='+h+'\n',encoding='utf-8')
    (backup/'ready').write_text('1.1.0-1.1.1')
    (target/'VocalPitchLab.exe').write_bytes(b'interrupted write')
    fixture=target/'unrelated-user-file.txt';fixture.write_text('preserve')
    # Use a real prior test library, outside the install directory, as protected data.
    user=out/'user-data';user.mkdir();(user/'library.json').write_text('{"songs":[{"name":"preserve"}]}')
    user_hash=digest(user/'library.json')
    modified=next(r['path'] for r in plan['removed'] if r['path'].endswith('/qmldir'))
    (target/modified).write_text('user-modified')
    save('interrupted_update_recovered_and_completed',update('recover'))
    save('target_hashes',verify(target,after))
    assert (target/modified).read_text()=='user-modified'
    assert all(not (target/r['path']).exists() for r in plan['removed'] if r['path']!=modified)
    assert fixture.read_text()=='preserve' and digest(user/'library.json')==user_hash
    assert not backup.exists()
    save('cleanup_and_data_preservation',True)
    save('repeat_update',update('repeat'))
    save('repeat_hashes',verify(target,after))
    print('ALL UPDATE CHECKS PASSED',flush=True)


if __name__=='__main__':main()
