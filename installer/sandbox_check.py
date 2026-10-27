"""Run with the installed runtime in a disposable Windows Sandbox."""
import os,sys,json,time
from pathlib import Path
appdir=Path(sys.executable).resolve().parent.parent
sys.path.insert(0,str(appdir))
os.environ['VPL_DATA_DIR']=os.environ.get('VPL_QA_DATA_DIR',str(Path(os.environ['LOCALAPPDATA'])/'VocalPitchLab-SandboxQA'))
os.environ['VPL_MODEL_DIR']=str(appdir/'models')
os.environ['VPL_DEVICE']=os.environ.get('VPL_QA_DEVICE','cpu');os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_QUICK_BACKEND']='software'
os.environ['PATH']=str(appdir/'bin')+os.pathsep+os.environ.get('PATH','')
out=Path(sys.argv[1]);out.mkdir(exist_ok=True);controller=None
try:
    import torch,torchaudio
    assert torch.__version__=='2.7.1+cu128' and torchaudio.__version__=='2.7.1+cu128'
    assert torch.version.cuda=='12.8'
    from vocalpitchlab.ui.app import Controller, create_engine, QGuiApplication
    from PySide6.QtTest import QTest
    app=QGuiApplication([]);controller=Controller(bootstrap=False);engine=create_engine(controller)
    assert engine.rootObjects()
    controller.enqueue(str(Path(sys.argv[2])))
    started=time.monotonic()
    while controller.data['jobs'][-1]['state'] in ('queued','running') and time.monotonic()-started<900:QTest.qWait(100)
    assert controller.data['jobs'][-1]['state']=='complete',controller.data['jobs'][-1]
    assert controller.primary=='rmvpe_tracked'
    analysis_seconds=time.monotonic()-started
    controller.muted=True;controller.apply_audio()
    controller.setSource('original');controller.seek(0);controller.togglePlay();QTest.qWait(1800)
    assert controller.player.position()>200,'original playback did not advance'
    controller.setSource('vocals');QTest.qWait(400)
    assert controller.vocal_player.error().value==0,'vocal playback failed'
    vocal_position=controller.vocal_player.position();QTest.qWait(600)
    assert controller.vocal_player.position()>vocal_position+200,'vocal playback did not advance'
    controller.togglePlay()
    assert controller.data['jobs'][-1]['hardware']['device']==os.environ['VPL_DEVICE']
    result=dict(gui=True,analysis=True,device=os.environ['VPL_DEVICE'],torch=torch.__version__,cuda_runtime=torch.version.cuda,original_playback=True,vocal_playback=True,seconds=analysis_seconds,runtime=sys.executable,data=os.environ['VPL_DATA_DIR'])
    controller.shutdown();(out/'sandbox-result.json').write_text(json.dumps(result,indent=2))
except Exception:
    import traceback
    (out/'sandbox-error.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
finally:
    if controller is not None:controller.shutdown()
