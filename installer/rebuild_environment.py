"""Offline clean QA environment from hash-locked wheels; no installed packages copied."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from application_files import MODULES, RESOURCES, VENDOR

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--local-evaluation',action='store_true')
    p.add_argument('--stage',type=Path,default=ROOT/'work/repro-build/app')
    p.add_argument('--artifacts',type=Path,default=ROOT/'work/repro-build')
    args=p.parse_args()
    if not args.local_evaluation: p.error('Only local evaluation is permitted while redistribution review is pending')
    if sys.version_info[:2] != (3,12) or sys.platform!='win32' or platform.architecture()[0]!='64bit':
        p.error('Use Windows x64 Python 3.12')
    stage=args.stage.resolve();work=(ROOT/'work').resolve()
    if not stage.is_relative_to(work) or stage==work or stage.exists():
        p.error('Stage must be a new directory below project work/')
    frozen=ROOT/'resources/reproducible'
    records=json.loads((frozen/'artifacts.json').read_text(encoding='utf-8'))
    for r in records:
        asset=args.artifacts/r['group']/r['file']
        if not asset.is_file() or digest(asset)!=r['sha256']:raise ValueError('Missing or modified wheel: '+r['file'])
    binaries=json.loads((frozen/'local-assets.json').read_text(encoding='utf-8'))
    for r in binaries:
        if digest(ROOT/r['path'])!=r['sha256']:raise ValueError('Modified local asset: '+r['path'])
    stage.mkdir(parents=True)
    env=dict(os.environ)
    for key in ['PYTHONPATH','PYTHONHOME']:env.pop(key,None)
    env.update(PYTHONNOUSERSITE='1',PIP_CONFIG_FILE=os.devnull,PIP_DISABLE_PIP_VERSION_CHECK='1')
    def run(command):subprocess.run(command,check=True,env=env,cwd=stage)
    run([sys.executable,'-I','-m','venv',str(stage/'runtime')])
    python=stage/'runtime/Scripts/python.exe'
    for group,lock,target in [('wheels','runtime.lock',None),('vendor-wheels','separation.lock',stage/'vendor/separation-runtime')]:
        command=[str(python),'-I','-m','pip','install','--no-index','--no-deps','--require-hashes',
                 '--find-links',str((args.artifacts/group).resolve()),'-r',str(frozen/lock)]
        if target:command+=['--target',str(target)]
        run(command)
    run([str(python),'-I','-m','pip','check'])
    for patch in json.loads((frozen/'separation-patch.json').read_text()):
        path=stage/'vendor/separation-runtime'/patch['path']
        original=path.read_text(encoding='utf-8').replace('\r\n','\n')
        if hashlib.sha256(original.encode()).hexdigest()!=patch['original_sha256']:raise ValueError('Patch source differs')
        updated=original.replace(patch['old'],patch['new'])
        if hashlib.sha256(updated.encode()).hexdigest()!=patch['patched_sha256']:raise ValueError('Patch output differs')
        path.write_text(updated,encoding='utf-8',newline='\n')
    def copy(src,dst):
        dst.parent.mkdir(parents=True,exist_ok=True)
        if src.is_dir():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:shutil.copy2(src,dst)
    for name in MODULES:copy(ROOT/(name+'.py'),stage/(name+'.py'))
    for name in RESOURCES:copy(ROOT/name,stage/name)
    for name in VENDOR:copy(ROOT/'vendor'/name,stage/'vendor'/name)
    for r in binaries:copy(ROOT/r['path'],stage/r['path'])
    copy(ROOT/'installer/launch.py',stage/'launch.py')
    (stage/'BUILD_EVIDENCE.json').write_text(json.dumps(dict(
        python=sys.version,isolated=True,dependency_install='offline hash-locked wheels',
        stage=str(stage),source_packages_copied=False,
        scope='Same-host clean Python environment; not fresh Windows or public distribution approval'),indent=2))
    print('Clean environment ready:',stage,flush=True)


if __name__=='__main__':main()
