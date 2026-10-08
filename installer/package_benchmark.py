"""Build and verify isolated offline installer candidates; never publishes assets."""
import argparse, hashlib, json, re, subprocess, time
from pathlib import Path
import psutil
try:
    from .privacy_check import EXCLUDED, inspect
except ImportError:
    from privacy_check import EXCLUDED, inspect

ROOT=Path(__file__).resolve().parents[1]
PROFILES=('fast','max','max-solid','ultra64-solid')

def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def component(path):
    if path.startswith('models/'):return 'models'
    if path.startswith('runtime/Lib/site-packages/torch/') :return 'pytorch-cuda'
    if path.startswith('runtime/Lib/site-packages/PySide6/'):return 'qt'
    if path.startswith('runtime/') or path.startswith('vendor/separation-runtime/'):return 'python-dependencies'
    return 'application'

def manifest(stage):
    rows=[]
    for p in sorted(stage.rglob('*')):
        if not p.is_file():continue
        r=p.relative_to(stage).as_posix()
        if any(part in EXCLUDED for part in p.relative_to(stage).parts) or p.suffix in ('.pyc','.pyo','.pdb'):continue
        c=component(r)
        rows.append(dict(path=r,bytes=p.stat().st_size,sha256=digest(p),component=c,reason={'models':'Unchanged production weights','pytorch-cuda':'Existing inference and GPU architecture support','qt':'UI runtime; retain unless dependency audit proves unused','python-dependencies':'Runtime dependency; retain unless audit proves unused','application':'Application, resources and notices'}[c]))
    return rows

def measure(command,log):
    start=time.monotonic();peak=0;private=0
    with log.open('w',encoding='utf-8') as out:
        p=subprocess.Popen(command,stdout=out,stderr=subprocess.STDOUT)
        while p.poll() is None:
            try:
                procs=[psutil.Process(p.pid),*psutil.Process(p.pid).children(recursive=True)]
                mem=[]
                for proc in procs:
                    try:mem.append(proc.memory_info())
                    except psutil.Error:pass
                peak=max(peak,sum(m.rss for m in mem));private=max(private,sum(getattr(m,'private',m.vms) for m in mem))
            except psutil.Error:pass
            time.sleep(.1)
    result=dict(seconds=round(time.monotonic()-start,3),peak_tree_rss_bytes=peak,peak_tree_private_bytes=private,exit_code=p.returncode)
    if p.returncode:raise RuntimeError(f'{log}: {result}')
    return result

def write_include(stage,rows,path,solid):
    lines=[];previous=None
    for row in sorted(rows,key=lambda r:(r['component'],r['path'])):
        rel=Path(row['path']);flags='ignoreversion'
        if solid and previous!=row['component']:flags+=' solidbreak'
        previous=row['component']
        dest='{app}'+('\\'+str(rel.parent) if str(rel.parent)!='.' else '')
        lines.append(f'Source: "{stage/rel}"; DestDir: "{dest}"; Flags: {flags}')
    path.write_text('\n'.join(lines),encoding='utf-8-sig')

def verify(target,rows):
    errors=[]
    for row in rows:
        p=target/row['path']
        if not p.is_file() or digest(p)!=row['sha256']:errors.append(row['path'])
    if errors:raise RuntimeError(f'Installed files differ: {errors[:20]}')
    return dict(files=len(rows),all_hashes_match=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--deny-file',type=Path);ap.add_argument('--resume',action='store_true');ap.add_argument('--removals',type=Path);ap.add_argument('--version',default='1.1.1');ap.add_argument('--profiles',nargs='+',choices=PROFILES,default=list(PROFILES))
    ap.add_argument('--compiler',type=Path,default=ROOT/'work/installer-tools/inno/ISCC.exe')
    args=ap.parse_args();stage=args.stage.resolve();output=args.output.resolve()
    required=('VocalPitchLab.exe','main.py','runtime/python.exe','models','qml','vocalpitchlab','vendor')
    if any(not (stage/name).exists() for name in required):raise SystemExit('Stage is missing required application components')
    if output.exists() and not args.resume:raise SystemExit('Choose a fresh output directory or explicitly resume')
    if output==stage or output.is_relative_to(stage):raise SystemExit('Output must be outside stage')
    output.mkdir(parents=True,exist_ok=True)
    config=dict(deny_sha256=digest(args.deny_file) if args.deny_file else None,version=args.version,stage=str(stage),compiler_sha256=digest(args.compiler),installer_sha256=digest(ROOT/'installer/VocalPitchLab.iss'),prerequisite_script_sha256=digest(ROOT/'installer/vc_redist.iss'),removals_sha256=digest(args.removals) if args.removals else None)
    config_path=output/'input.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:raise SystemExit('Build inputs changed; choose a fresh output directory')
    if args.resume and not config_path.exists():raise SystemExit('Resume requires an input fingerprint')
    config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    sources=output/'build-sources';sources.mkdir(exist_ok=True)
    for name in ('VocalPitchLab.iss','vc_redist.iss'):(sources/name).write_bytes((ROOT/'installer'/name).read_bytes())
    rows=manifest(stage)
    old_manifest=output/'manifest.json'
    if old_manifest.exists() and json.loads(old_manifest.read_text(encoding='utf-8'))!=rows:raise SystemExit('Input stage changed; choose a fresh output directory')
    (output/'manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    cleanup=[]
    if args.removals:
        report=json.loads(args.removals.read_text(encoding='utf-8'))
        for row in report['files']:
            rel=Path(row['path'])
            if rel.is_absolute() or '..' in rel.parts or any(c in str(rel) for c in (':', chr(39), chr(34), '\n', '\r')):raise ValueError('Unsafe obsolete path')
            if not re.fullmatch('[a-f0-9]{64}',row['sha256']):raise ValueError('Invalid obsolete hash')
            if (stage/rel).exists():raise ValueError('Obsolete file is still in candidate')
            cleanup.append(f"Type: files; Name: \"{{app}}\\{rel}\"; Check: ObsoleteFileMatches('{rel}', '{row['sha256']}')")
    obsolete=output/'obsolete.iss';obsolete.write_text('\n'.join(cleanup),encoding='utf-8-sig')
    results=json.loads((output/'results.json').read_text()) if (output/'results.json').exists() else []
    for profile in args.profiles:
        if any(r['profile']==profile for r in results):
            completed=output/profile
            for line in (completed/'SHA256SUMS.txt').read_text().splitlines():
                expected,name=line.split('  ',1)
                asset=completed/name
                if not asset.is_file() or digest(asset)!=expected:raise RuntimeError('Completed asset changed; choose a fresh output directory')
            verify(completed/'安装验证 with spaces',rows)
            print('VERIFIED existing '+profile,flush=True)
            continue
        dest=output/profile;dest.mkdir(exist_ok=True);include=dest/'files.iss'
        write_include(stage,rows,include,'solid' in profile)
        print('BUILD '+profile,flush=True)
        build=measure([str(args.compiler),'/Q',f'/DStageDir={stage}',f'/DAppVersion={args.version}',f'/DCompressionProfile={profile}',f'/DPackageOutputDir={dest}',f'/DPackageFilesInclude={include}',f'/DObsoleteFilesInclude={obsolete}','/DGithubAssets',str(ROOT/'installer/VocalPitchLab.iss')],dest/'build.log')
        assets=sorted(p for p in dest.iterdir() if p.suffix in ('.bin','.exe'))
        if not assets or any(p.stat().st_size>=2*1024**3 for p in assets):raise RuntimeError('Missing assets or GitHub asset size limit exceeded')
        (dest/'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in assets))
        target=dest/'安装验证 with spaces';exe=next(p for p in assets if p.suffix=='.exe')
        print('INSTALL '+profile,flush=True)
        install=measure([str(exe),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/PACKAGEVALIDATION=1','/NOCLOSEAPPLICATIONS',f'/DIR={target}',f'/LOG={dest / "setup.log"}'],dest/'install.log')
        check=verify(target,rows)
        privacy=inspect(target,json.loads(args.deny_file.read_text(encoding='utf-8')) if args.deny_file else [])
        (dest/'privacy.json').write_text(json.dumps(privacy,indent=2),encoding='utf-8')
        if not privacy['passed']:raise RuntimeError('Installed package contains disallowed content; see privacy.json')
        result=dict(profile=profile,compiler_sha256=digest(args.compiler),installer_source_sha256=digest(ROOT/'installer/VocalPitchLab.iss'),download_bytes=sum(p.stat().st_size for p in assets),installed_payload_bytes=sum(r['bytes'] for r in rows),build=build,install=install,verification=check)
        results.append(result);(output/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps(result),flush=True)
    if manifest(stage)!=rows:raise RuntimeError('Input stage changed during benchmark')

if __name__=='__main__':main()
