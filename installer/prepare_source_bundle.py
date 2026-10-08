"""Prepare a small source repository without songs, model weights or local environments."""
from pathlib import Path
import shutil
import argparse
import re
from application_files import SOURCE_FILES, VENDOR

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/github-source-1.1.1'

def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc','BRAND.md'))
    else:shutil.copy2(src,dst)

def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',default='1.1.1')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--archive-dir',type=Path,default=ROOT/'dist')
    args=parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+',args.version):raise SystemExit('Invalid version')
    OUT=(args.output or ROOT/('work/github-source-'+args.version)).resolve()
    if OUT.exists():raise SystemExit('Source export already exists; preserve existing work')
    OUT.mkdir(parents=True)
    for name in SOURCE_FILES:copy(ROOT/name,OUT/name)
    for name in ['assets','qml','installer','resources','docs','tests','note-settings.json','LICENSE',
                 'THIRD_PARTY_NOTICES.md','MODEL_LICENSE_REVIEW.md','INSTALLATION.md',
                 'CHANGELOG.md',f'RELEASE_NOTES_{args.version}.md','requirements.txt','.gitattributes']:
        copy(ROOT/name,OUT/name)
    for name in VENDOR:copy(ROOT/'vendor'/name,OUT/'vendor'/name)
    (OUT/'.gitignore').write_text('work/\nbuild/\ndist/\ninput/\noutputs/\nresults/\nmodels/\nlibrary/\ndatasets/\n.venv/\nbin/\n__pycache__/\n*.pyc\n.env\n',encoding='utf-8')
    copy(ROOT/'README.md',OUT/'README.md')
    archive=args.archive_dir.resolve()/f'VocalPitchLab-{args.version}-source'
    archive.parent.mkdir(exist_ok=True)
    shutil.make_archive(str(archive),'zip',OUT)
    print(OUT)

if __name__=='__main__':main()
