"""Build an explicit local-only preview, never a public release artifact."""
import sys,shutil,json,hashlib,importlib.metadata as md
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];stage=ROOT/('build/slim-preview' if '--trim' in sys.argv else 'build/local-preview')
if '--trim' in sys.argv and stage.exists():raise SystemExit('Use a fresh slim-preview stage to avoid stale artifacts')
stage.mkdir(parents=True,exist_ok=True)
if '--local-preview' not in sys.argv:raise SystemExit('Public release blocked: unresolved model/runtime redistribution review. Pass --local-preview for local QA only.')
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir():shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
    else:shutil.copy2(src,dst)
from application_files import MODULES
modules=MODULES
for name in modules:copy(ROOT/(name+'.py'),stage/(name+'.py'))
for name in ['qml','assets','resources','note-settings.json','LICENSE','THIRD_PARTY_NOTICES.md','PERFORMANCE_PREVIEW.md','INSTALLATION.md']:copy(ROOT/name,stage/name)
copy(ROOT/'installer/launch.py',stage/'launch.py')
for name in ['__init__.py','rmvpe_rvc.py','LICENSE-RVC','MODEL-CARD-RVC.md','provenance.json','separation-runtime']:
    copy(ROOT/'vendor'/name,stage/'vendor'/name)
base=Path(sys.base_prefix);runtime=stage/'runtime';runtime.mkdir(exist_ok=True)
for p in base.iterdir():
    if p.suffix in ['.exe','.dll'] or p.name in ['DLLs','LICENSE.txt']:copy(p,runtime/p.name)
for p in (base/'Lib').iterdir():
    if p.name not in ['site-packages','__pycache__','test','idlelib','tkinter','turtledemo','ensurepip']:copy(p,runtime/'Lib'/p.name)
copy(Path(sys.prefix)/'Lib/site-packages',runtime/'Lib/site-packages')
copy(ROOT/'bin/ffmpeg.exe',stage/'bin/ffmpeg.exe')
for name in ['rmvpe.pt','roformer','game-small']:copy(ROOT/'models'/name,stage/'models'/name)
for name in ['bs_roformer_karaoke_frazer_becruily.ckpt','config_bs_roformer_karaoke_frazer_becruily.yaml','download_checks.json','source.json']:
    copy(ROOT/'models/lead-separation'/name,stage/'models/lead-separation'/name)
if '--trim' in sys.argv:
    from trim_runtime import trim
    report=trim(stage)
    (ROOT/'build/trim-report.json').write_text(json.dumps(report,indent=2))
inventory=[]
for path in [runtime/'Lib/site-packages',stage/'vendor/separation-runtime']:
    for d in md.distributions(path=[str(path)]):
        inventory.append(dict(name=d.metadata['Name'],version=d.version,license=d.metadata.get('License-Expression') or d.metadata.get('License'),location=str(path.relative_to(stage))))
(stage/'THIRD_PARTY_INVENTORY.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
(stage/'LOCAL_PREVIEW_ONLY.txt').write_text('LOCAL QA ONLY. Not approved for public distribution. BS model license unresolved; runtime/FFmpeg third-party source and notices review pending.\n')
(ROOT/('build/slim-stage-report.json' if '--trim' in sys.argv else 'build/stage-report.json')).write_text(json.dumps(dict(stage=str(stage),files=sum(1 for p in stage.rglob('*') if p.is_file()),bytes=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())),indent=2))
print(stage,flush=True)
