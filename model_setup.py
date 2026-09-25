"""Pinned, checksum-verified model provisioning. License review is explicit."""
import argparse,hashlib,json,shutil,zipfile,time
from pathlib import Path
import requests
from app_paths import APP_ROOT,MODEL_ROOT
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def install(allow_unreviewed=False):
    entries=json.loads((APP_ROOT/'resources/model-manifest.json').read_text(encoding='utf-8'))
    unresolved=[x['path'] for x in entries if x['redistribution']!='approved']
    if unresolved and not allow_unreviewed:raise RuntimeError('Public release license review pending: '+', '.join(unresolved))
    MODEL_ROOT.mkdir(parents=True,exist_ok=True)
    for x in entries:
        dest=MODEL_ROOT/(x['path']+'.zip' if x['archive'] else x['path']);dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists() or digest(dest)!=x['sha256']:
            part=dest.with_suffix(dest.suffix+'.part')
            for attempt in range(3):
                try:
                    print('Downloading '+x['path']+' attempt '+str(attempt+1),flush=True)
                    with requests.get(x['url'],stream=True,timeout=(30,45)) as response:
                        response.raise_for_status()
                        with part.open('wb') as out:
                            for block in response.iter_content(1024*1024):out.write(block)
                    break
                except requests.RequestException:
                    if attempt==2:raise
                    time.sleep(2)
            if part.stat().st_size!=x['bytes'] or digest(part)!=x['sha256']:raise ValueError('Model integrity check failed: '+x['path'])
            part.replace(dest)
        if x['archive']:
            target=MODEL_ROOT/x['path'];target.mkdir(parents=True,exist_ok=True)
            with zipfile.ZipFile(dest) as z:
                for member in z.infolist():
                    resolved=(target/member.filename).resolve()
                    if not resolved.is_relative_to(target.resolve()):raise ValueError('Unsafe archive path')
                z.extractall(target)
        print('Verified '+x['path'],flush=True)
    shutil.copytree(APP_ROOT/'resources/model-configs',MODEL_ROOT,dirs_exist_ok=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--local-evaluation',action='store_true');args=parser.parse_args()
    install(args.local_evaluation)
