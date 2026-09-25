"""Prepare a small source repository without songs, model weights or local environments."""
from pathlib import Path
import shutil
from application_files import MODULES, VENDOR

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/github-source-1.0.0'

def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    else:shutil.copy2(src,dst)

def main():
    if OUT.exists():raise SystemExit('Source export already exists; preserve existing work')
    OUT.mkdir(parents=True)
    for name in MODULES:copy(ROOT/(name+'.py'),OUT/(name+'.py'))
    for name in ['assets','qml','installer','resources','note-settings.json','LICENSE',
                 'THIRD_PARTY_NOTICES.md','MODEL_LICENSE_REVIEW.md','INSTALLATION.md',
                 'CHANGELOG.md','DEFAULT_PIPELINE.md','CLEAN_BUILD.md','WINDOWS_SANDBOX_QA.md',
                 'PERFORMANCE_PREVIEW.md','RELEASE_PLAN.md','RELEASE_READINESS.md','requirements.txt']:
        copy(ROOT/name,OUT/name)
    for name in VENDOR:copy(ROOT/'vendor'/name,OUT/'vendor'/name)
    (OUT/'.gitignore').write_text('work/\nbuild/\ndist/\ninput/\noutputs/\nresults/\nmodels/\nlibrary/\ndatasets/\n.venv/\nbin/\n__pycache__/\n*.pyc\n.env\n',encoding='utf-8')
    copy(ROOT/'README.md',OUT/'README.md')
    archive=ROOT/'dist/VocalPitchLab-1.0.0-source'
    archive.parent.mkdir(exist_ok=True)
    shutil.make_archive(str(archive),'zip',OUT)
    print(OUT)

if __name__=='__main__':main()

