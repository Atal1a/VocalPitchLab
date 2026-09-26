"""Assemble current application with previously rebuilt dependencies. Does not run tests."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from application_files import MODULES, RESOURCES, VENDOR
from trim_runtime import trim

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'build/delivery-1.1.0'
CLEAN = ROOT / 'work/repro-build/app'
BASE = ROOT / 'build/slim-preview/runtime'

def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    else:
        shutil.copy2(src, dst)

def main():
    if STAGE.exists():
        raise SystemExit('Delivery stage already exists; preserve it and choose a fresh version')
    STAGE.mkdir(parents=True)
    for name in MODULES: copy(ROOT / (name+'.py'), STAGE / (name+'.py'))
    for name in [*RESOURCES, 'INSTALLATION.md', 'CHANGELOG.md']: copy(ROOT/name, STAGE/name)
    copy(ROOT/'installer/launch.py', STAGE/'launch.py')
    for name in [*VENDOR, 'separation-runtime']: copy(CLEAN/'vendor'/name, STAGE/'vendor'/name)
    copy(CLEAN/'models', STAGE/'models')
    copy(CLEAN/'bin', STAGE/'bin')
    for child in BASE.iterdir():
        if child.name == 'Lib':
            for part in child.iterdir():
                if part.name not in ('site-packages', '__pycache__'):
                    copy(part, STAGE/'runtime/Lib'/part.name)
        else: copy(child, STAGE/'runtime'/child.name)
    copy(CLEAN/'runtime/Lib/site-packages', STAGE/'runtime/Lib/site-packages')
    report = trim(STAGE)
    (ROOT/'build/delivery-trim.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    csc = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    subprocess.run([str(csc), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
                    '/reference:System.Windows.Forms.dll', '/win32icon:'+str(ROOT/'assets/vocalpitch.ico'),
                    '/out:'+str(STAGE/'VocalPitchLab.exe'), str(ROOT/'installer/Launcher.cs')], check=True)
    files=[]
    for p in sorted(STAGE.rglob('*')):
        if p.is_file():
            with p.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
            files.append(dict(path=p.relative_to(STAGE).as_posix(),bytes=p.stat().st_size,sha256=digest))
    (ROOT/'build/delivery-manifest.json').write_text(json.dumps(dict(version='1.1.0',
        tests_run=False,code_signing=False,distribution_review='pending',
        runtime='CPython standalone base from earlier package; dependencies from clean rebuilt environment',
        files=files),indent=2),encoding='utf-8')
    print(STAGE,flush=True)

if __name__=='__main__':main()
