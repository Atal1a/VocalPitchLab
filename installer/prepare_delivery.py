"""Assemble current application with previously rebuilt dependencies. Does not run tests."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from application_files import SOURCE_FILES, RESOURCES, VENDOR
from trim_runtime import trim
from privacy_check import ignore_private_files, inspect

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'build/delivery-1.1.1'
CLEAN = ROOT / 'work/repro-build/app'
BASE = ROOT / 'build/slim-preview/runtime'

def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=ignore_private_files)
    else:
        shutil.copy2(src, dst)

def main():
    global STAGE, CLEAN, BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='1.1.1')
    parser.add_argument('--stage', type=Path, default=STAGE)
    parser.add_argument('--dependencies', type=Path, default=CLEAN)
    parser.add_argument('--base-runtime', type=Path, default=BASE)
    parser.add_argument('--report-dir', type=Path)
    parser.add_argument('--keep-unused-qt', action='store_false', dest='trim_unused_qt', default=True)
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:\.\d+)?', args.version) or any(int(n)>65534 for n in args.version.split('.')):
        raise SystemExit('Version must contain three or four numeric components below 65535')
    STAGE, CLEAN, BASE = args.stage.resolve(), args.dependencies.resolve(), args.base_runtime.resolve()
    if not STAGE.is_relative_to(ROOT/'build') or STAGE == ROOT/'build':
        raise SystemExit('Stage must be a fresh build subdirectory')
    reports = (args.report_dir or STAGE.parent/(STAGE.name+'-reports')).resolve()
    if reports == STAGE or reports.is_relative_to(STAGE):
        raise SystemExit('Reports must remain outside the application stage')
    if STAGE.exists():
        raise SystemExit('Delivery stage already exists; choose a fresh stage directory')
    if not CLEAN.is_dir() or not BASE.is_dir():
        raise SystemExit('Prepared dependency and base runtime directories are required')
    if reports.exists() and any(reports.iterdir()):
        raise SystemExit('Choose a fresh report directory')
    reports.mkdir(parents=True, exist_ok=True)
    STAGE.mkdir(parents=True)
    for name in SOURCE_FILES: copy(ROOT/name, STAGE/name)
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
    if args.trim_unused_qt:
        from trim_optional_runtime import trim_browser
        optional = trim_browser(STAGE)
        (reports/'optional-trim.json').write_text(json.dumps(optional, indent=2), encoding='utf-8')
    (reports/'trim.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    csc = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    assembly_version = args.version + ('.0' if len(args.version.split('.')) == 3 else '')
    launcher_source = (ROOT/'installer/Launcher.cs').read_text(encoding='utf-8')
    launcher_source = re.sub(r'(Assembly(?:File)?Version\(")[^"]+("\))',
                             lambda m: m[1] + assembly_version + m[2], launcher_source)
    launcher = reports/'Launcher.cs'
    launcher.write_text(launcher_source, encoding='utf-8-sig')
    subprocess.run([str(csc), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
                    '/reference:System.Windows.Forms.dll', '/win32icon:'+str(ROOT/'assets/vocalpitch.ico'),
                    '/out:'+str(STAGE/'VocalPitchLab.exe'), str(launcher)], check=True)
    audit = inspect(STAGE, [str(ROOT), str(Path.home())])
    if not audit['passed']: raise RuntimeError('Private build content: '+str(audit['findings']))
    files=[]
    for p in sorted(STAGE.rglob('*')):
        if p.is_file():
            with p.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
            files.append(dict(path=p.relative_to(STAGE).as_posix(),bytes=p.stat().st_size,sha256=digest))
    (reports/'manifest.json').write_text(json.dumps(dict(version=args.version,
        tests_run=False,code_signing=False,distribution_review='pending',
        runtime='CPython standalone base from earlier package; dependencies from clean rebuilt environment',
        files=files),indent=2),encoding='utf-8')
    print(STAGE,flush=True)

if __name__=='__main__':main()
