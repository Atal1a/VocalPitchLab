"""Explicit, dependency-checked removal of the unused Qt browser stack."""
import argparse, hashlib, json, shutil
from pathlib import Path
try:
    from .pe_dependencies import imports
except ImportError:
    from pe_dependencies import imports
ROOT=Path(__file__).resolve().parents[1]

def browser_file(rel):
    r=rel.as_posix();name=rel.name.lower()
    return (name.startswith(('qt6webengine','qt6webview','qtwebengine','qtwebview'))
        or r.startswith(('qml/QtWebEngine/','qml/QtWebView/','plugins/webview/'))
        or r=='plugins/designer/qwebengineview.dll'
        or (r.startswith('resources/') and (name.startswith('qtwebengine') or name=='icudtl.dat'))
        or (r.startswith('translations/') and name.startswith('qtwebengine')))

def audit(stage):
    qt=stage/'runtime/Lib/site-packages/PySide6'
    files=[p for p in qt.rglob('*') if p.is_file()]
    removed=[p for p in files if browser_file(p.relative_to(qt))]
    names={p.name.lower() for p in removed if p.suffix.lower() in ('.dll','.pyd','.exe')}
    blockers=[]
    for p in files:
        if p in removed:continue
        if p.suffix.lower() in ('.dll','.pyd','.exe'):
            hits=imports(p)&names
            if hits:blockers.append((p.relative_to(qt).as_posix(),sorted(hits)))
        elif p.name=='qmldir' or p.suffix in ('.qml','.py'):
            content=p.read_text(encoding='utf-8',errors='replace')
            if any(line.strip().startswith(('import QtWebEngine','import QtWebView','depends QtWebEngine','depends QtWebView')) for line in content.splitlines()):blockers.append((p.relative_to(qt).as_posix(),'QML import'))
    for folder in ('qml','vocalpitchlab'):
        for p in (stage/folder).rglob('*'):
            if p.suffix in ('.py','.qml') and any(word in p.read_text(encoding='utf-8') for word in ('QtWebEngine','QtWebView')):blockers.append((str(p.relative_to(stage)),'application reference'))
    if blockers:raise RuntimeError(f'Browser stack still referenced: {blockers}')
    return removed

def trim_browser(stage):
    stage=Path(stage).resolve()
    if stage == ROOT/'build' or not stage.is_relative_to(ROOT/'build'):
        raise ValueError('Only a disposable build subdirectory may be trimmed')
    rows=[]
    for p in audit(stage):
        with p.open('rb') as f:d=hashlib.file_digest(f,'sha256').hexdigest()
        rows.append(dict(path=p.relative_to(stage).as_posix(),bytes=p.stat().st_size,sha256=d,reason='Unused Qt browser stack; no retained PE/QML/application references'))
    # Audit every retained binary before deleting any file.
    for row in rows:(stage/row['path']).unlink()
    return dict(removed_bytes=sum(r['bytes'] for r in rows),files=rows,preserved='Models, PyTorch/CUDA, CREPE, audio dependencies, Qt rendering and multimedia, licenses')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--report',type=Path,required=True)
    a=ap.parse_args();src=a.source.resolve();stage=a.stage.resolve()
    if stage.exists() or stage==ROOT/'build' or not stage.is_relative_to(ROOT/'build'):raise SystemExit('Choose a fresh build subdirectory')
    audit(src)
    shutil.copytree(src,stage)
    report=trim_browser(stage)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(files=len(report['files']),removed_bytes=report['removed_bytes'])),flush=True)
if __name__=='__main__':main()
