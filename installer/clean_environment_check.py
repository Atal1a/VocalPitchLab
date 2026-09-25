"""Exercise copied application using a freshly installed Python environment."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--app',required=True,type=Path)
p.add_argument('--audio',required=True,type=Path)
p.add_argument('--data',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
args.app=args.app.resolve();args.data=args.data.resolve()
if args.data.exists():raise RuntimeError('Use a new isolated QA data directory')
args.data.mkdir(parents=True)
offline_worker=args.data/'offline-worker.py'
offline_worker.write_text(
    'import socket,sys,runpy\n'
    'def deny(*args,**kwargs): raise OSError("QA: outbound Python network is disabled")\n'
    'socket.socket.connect=deny\nsocket.socket.connect_ex=deny\nsocket.create_connection=deny\n'
    f'sys.path.insert(0,{str(args.app)!r})\n'
    f'runpy.run_path({str(args.app/"analyze_song.py")!r},run_name="__main__")\n',encoding='utf-8')
os.environ.update(VPL_DATA_DIR=str(args.data),VPL_MODEL_DIR=str(args.app/'models'),
                  QT_QPA_PLATFORM='offscreen',QSG_RHI_BACKEND='software',PYTHONNOUSERSITE='1')
os.environ['PATH']=str(args.app/'bin')+os.pathsep+os.environ.get('PATH','')
sys.path.insert(0,str(args.app))
import numpy,torch,PySide6
from quick_app import Controller,create_engine,QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import qInstallMessageHandler

warnings=[]
def handler(kind,ctx,msg):
    if '.qml:' in msg or 'QQmlApplicationEngine failed' in msg:warnings.append(msg)
qInstallMessageHandler(handler)
def until(fn,seconds=240):
    started=time.monotonic()
    while not fn():
        if time.monotonic()-started>seconds:raise RuntimeError('Check timed out')
        QTest.qWait(100)

app=QGuiApplication([]);b=None
try:
    locations={m.__name__:str(Path(m.__file__).resolve()) for m in [numpy,torch,PySide6]}
    assert all(Path(v).is_relative_to(args.app/'runtime') for v in locations.values()),locations
    b=Controller(args.data/'library',bootstrap=False,worker=offline_worker)
    b.muted=True;b.apply_audio()
    engine=create_engine(b);assert engine.rootObjects();window=engine.rootObjects()[0]
    started=time.monotonic();b.enqueue(str(args.audio.resolve()));until(lambda:b.process is None,600)
    assert b.data['jobs'][-1]['state']=='complete',b.data['jobs'][-1]
    assert b.state['activeSeparation']=='mel_bs' and b.primary=='rmvpe_tracked'
    assert b.data['jobs'][-1]['hardware']['device']=='cuda',b.data['jobs'][-1]
    song=b.song;analysis_seconds=time.monotonic()-started
    b.setSource('original');b.seek(0);b.togglePlay();QTest.qWait(1600)
    assert b.player.position()>200
    b.setSource('vocals');position=b.vocal_player.position();QTest.qWait(700)
    assert b.vocal_player.error().value==0 and b.vocal_player.position()>position+200
    b.togglePlay()
    b.preparePiano();until(lambda:b.piano.handle.value and not b.piano.loading,15)
    # Exercise real Windows MIDI output without audible sound (expression=0).
    b.piano.send(0xB0,11,0);b.piano.play(69,1);assert b.piano.note==69
    QTest.qWait(100);b.piano.release();assert b.piano.note is None
    b.setting('theme','dark');b.setting('hoverNotes',False)
    # An independent fake worker allows deterministic cancellation without a second model run.
    worker=args.data/'slow-worker.py';worker.write_text('import time\ntime.sleep(60)\n')
    b.worker=worker;b.setting('separationModel','mel_roformer');b.applySeparation()
    until(lambda:b.process is not None,5);QTest.qWait(200);b.cancel();until(lambda:b.process is None,10)
    assert b.data['jobs'][-1]['state']=='cancelled'
    assert b.song['audio']['vocals']==song['audio']['vocals']
    b.removeDisplayedJob();assert not b.state['canRetry']
    b.shutdown();window.close();engine.deleteLater();QTest.qWait(100)
    b=Controller(args.data/'library',bootstrap=False)
    assert b.settings['theme']=='dark' and b.settings['hoverNotes'] is False
    assert b.song and b.song['audio']['vocals']==song['audio']['vocals']
    assert not warnings,warnings
    result=dict(clean_dependencies=True,python_worker_network_blocked=True,modules=locations,gui=True,default_analysis=True,
                cuda=True,analysis_seconds=analysis_seconds,original_playback=True,
                vocal_playback=True,piano_midi=True,piano_audible_test=False,
                cancellation=True,delete_job=True,settings_persistence=True,library_persistence=True,
                python=sys.version,runtime=sys.executable,app=str(args.app),data=str(args.data))
    source_files=list(args.app.glob('*.py'))+list((args.app/'qml').rglob('*.qml'))
    result['application_hashes']={f.relative_to(args.app).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
                                  for f in source_files if f.name!='launch.py'}
    (args.output/'checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
except Exception:
    import traceback
    (args.output/'error.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
finally:
    if b is not None:b.shutdown()
