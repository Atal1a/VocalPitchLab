"""Installed entry point: no installed Python or source checkout required."""
import os,sys
from pathlib import Path
APP=Path(__file__).resolve().parent
os.environ.setdefault('VPL_DATA_DIR',str(Path(os.environ['LOCALAPPDATA'])/'VocalPitchLab'))
os.environ.setdefault('VPL_MODEL_DIR',str(APP/'models'))
os.environ['PATH']=str(APP/'bin')+os.pathsep+os.environ.get('PATH','')
os.environ.setdefault('PYTHONIOENCODING','utf-8')
os.chdir(APP)
sys.path.insert(0,str(APP))
try:
    from quick_app import main
    sys.exit(main())
except Exception:
    import traceback,ctypes
    target=Path(os.environ['VPL_DATA_DIR']);target.mkdir(parents=True,exist_ok=True)
    (target/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
    ctypes.windll.user32.MessageBoxW(0,'启动失败，诊断已保存到：'+str(target/'startup-error.log'),'VocalPitchLab',16)
    raise
