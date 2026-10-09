"""Prepare a small source repository without songs, model weights or local environments."""
from pathlib import Path
import shutil
import argparse
import re
import json
from application_files import SOURCE_FILES, VENDOR
from privacy_check import ignore_private_files, inspect

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/github-source-1.1.1'

def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir():shutil.copytree(src,dst,ignore=ignore_private_files)
    else:shutil.copy2(src,dst)

def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',default='1.1.1')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--archive-dir',type=Path,default=ROOT/'dist')
    parser.add_argument('--deny-file',type=Path,help='Local JSON list of private strings to reject before archiving')
    args=parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+',args.version):raise SystemExit('Invalid version')
    OUT=(args.output or ROOT/('work/github-source-'+args.version)).resolve()
    if OUT.exists():raise SystemExit('Source export already exists; preserve existing work')
    OUT.mkdir(parents=True)
    for name in SOURCE_FILES:copy(ROOT/name,OUT/name)
    for name in ['assets','qml','installer','resources','docs','note-settings.json','LICENSE',
                 'THIRD_PARTY_NOTICES.md','MODEL_LICENSE_REVIEW.md','INSTALLATION.md',
                 'CHANGELOG.md',f'RELEASE_NOTES_{args.version}.md','requirements.txt','.gitattributes']:
        copy(ROOT/name,OUT/name)
    # Older experimental tests rely on private audio and removed application modules.
    for pattern in ['test_*.py','package_*.py']:
        for path in sorted((ROOT/'tests').glob(pattern)):
            copy(path,OUT/'tests'/path.name)
    copy(ROOT/'tests/fixtures/package_offline',OUT/'tests/fixtures/package_offline')
    for name in VENDOR:copy(ROOT/'vendor'/name,OUT/'vendor'/name)
    copy(ROOT/'.gitignore',OUT/'.gitignore')
    copy(ROOT/'README.md',OUT/'README.md')
    forbidden=[str(ROOT),str(Path.home())]
    if args.deny_file:
        forbidden+=json.loads(args.deny_file.read_text(encoding='utf-8-sig'))
    audit=inspect(OUT,forbidden)
    if not audit['passed']:
        raise SystemExit('Source export privacy check failed: '+json.dumps(audit['findings']))
    archive=args.archive_dir.resolve()/f'VocalPitchLab-{args.version}-source'
    archive.parent.mkdir(exist_ok=True)
    shutil.make_archive(str(archive),'zip',OUT)
    print(OUT)

if __name__=='__main__':main()
