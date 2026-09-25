"""Conservative offline inference trim, applied only to a disposable build stage."""
from pathlib import Path
import json,hashlib

def trim(stage):
    stage=Path(stage).resolve()
    build=Path(__file__).resolve().parents[1]/'build'
    if not stage.is_relative_to(build.resolve()) or stage==build.resolve():
        raise ValueError('Only a build subdirectory may be trimmed')
    site=stage/'runtime/Lib/site-packages'
    removals=[]
    qt_dev={'doc','glue','include','metatypes','typesystems','scripts'}
    for p in list(stage.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(stage);parts=rel.parts;reason=None
        # Qt/PyTorch execute prebuilt binaries here; no extension compilation/JIT.
        if p.is_relative_to(site/'torch') and (p.suffix=='.lib' or 'include' in p.relative_to(site/'torch').parts):reason='PyTorch C++ development files'
        elif p.is_relative_to(site/'PySide6'):
            q=p.relative_to(site/'PySide6')
            if q.parts[0] in qt_dev or p.suffix in ('.lib','.pyi') or (len(q.parts)==1 and p.suffix=='.exe'):reason='Qt development tools and metadata'
        if p.is_relative_to(site):
            q=p.relative_to(site)
            if q.parts[0]=='torchfcpe' or q.parts[0].startswith('torchfcpe-'):reason='Unused FCPE experiment'
            # NumPy/SciPy import some testing helpers in normal execution.
            # Keep dependency test namespaces instead of blanket deletion.
        if '__pycache__' in parts or p.suffix=='.pyc':reason='Regenerable bytecode'
        if reason:
            removals.append(dict(path=rel.as_posix(),bytes=p.stat().st_size,reason=reason))
            p.unlink()
    # Empty directories need not be shipped. Every target remains under stage.
    for p in sorted(stage.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if p.is_dir() and not any(p.iterdir()):p.rmdir()
    report=dict(removed_bytes=sum(x['bytes'] for x in removals),removed_files=len(removals),files=removals,
        preserved='All production model weights, DLLs/PYDs, CUDA/cuDNN/cuBLAS, Qt runtime/QML/plugins, FFmpeg and third-party license notices')
    return report
