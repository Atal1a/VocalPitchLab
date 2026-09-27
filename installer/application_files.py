"""Production application source allowlist shared by build paths."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = ['main.py', *sorted(p.relative_to(ROOT).as_posix()
                                 for p in (ROOT/'vocalpitchlab').rglob('*.py'))]
RESOURCES = ['qml','assets','resources','note-settings.json','LICENSE',
             'THIRD_PARTY_NOTICES.md']
VENDOR = ['__init__.py','rmvpe_rvc.py','LICENSE-RVC','MODEL-CARD-RVC.md','provenance.json']
