"""Read-only application files and separately writable user data."""
import os,sys
from pathlib import Path
APP_ROOT=Path(__file__).resolve().parent
DATA_ROOT=Path(os.environ.get('VPL_DATA_DIR',str(APP_ROOT))).expanduser().resolve()
MODEL_ROOT=Path(os.environ.get('VPL_MODEL_DIR',str(DATA_ROOT/'models'))).resolve()
def prepare():
    for name in ['library','results','work','input']:(DATA_ROOT/name).mkdir(parents=True,exist_ok=True)
def worker_python():
    current=Path(sys.executable)
    return str(current.with_name('python.exe') if current.name.lower()=='pythonw.exe' else current)
