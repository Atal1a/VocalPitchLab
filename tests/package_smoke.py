import os,sys,time,json
from pathlib import Path
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('stage',type=Path);parser.add_argument('data',type=Path);parser.add_argument('audio',type=Path)
args=parser.parse_args()
stage=args.stage.resolve();data=args.data.resolve();sample_audio=str(args.audio.resolve())
if data.exists() and any(data.iterdir()):raise SystemExit('Choose a fresh test data directory')
data.mkdir(parents=True,exist_ok=True)
import runpy
runpy.run_path(str(Path(__file__).parent/'fixtures/package_offline/sitecustomize.py'))
os.environ['PYTHONPATH']=str(Path(__file__).parent/'fixtures/package_offline')
os.environ['VPL_NETWORK_AUDIT']=str(data/'network-audit.txt')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ.update(VPL_DATA_DIR=str(data),VPL_MODEL_DIR=str(stage/'models'),QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
os.environ['PATH']=str(stage/'bin')+os.pathsep+os.environ.get('PATH','');sys.path.insert(0,str(stage))
from vocalpitchlab.ui.app import Controller,create_engine
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtTest import QTest
app=QGuiApplication([]);warnings=[]
qInstallMessageHandler(lambda k,c,m: warnings.append(m) if '.qml:' in m or 'Traceback' in m else None)
b=Controller(data/'library',bootstrap=False);engine=create_engine(b);assert engine.rootObjects();window=engine.rootObjects()[0]
from PySide6.QtQuick import QSGRendererInterface
QTest.qWait(100)
assert window.rendererInterface().graphicsApi()==QSGRendererInterface.GraphicsApi.Software
def until(fn,timeout=180):
 t=time.monotonic()
 while not fn():
  if time.monotonic()-t>timeout:raise TimeoutError(str(b.data['jobs'])+' '+str(b.message))
  QTest.qWait(80)
try:
 for theme in ['light','dark']:
  b.setting('theme',theme);QTest.qWait(100)
 window.setWidth(1060);window.setHeight(720);QTest.qWait(100)
 from PySide6.QtCore import QObject
 from PySide6.QtQml import QQmlComponent
 popup=window.findChild(QObject,'settingsPopup')
 if popup:popup.open();QTest.qWait(100);popup.close()
 component=QQmlComponent(engine);component.setData(b'import QtQuick; import QtQuick.Dialogs; FileDialog {}',__import__('PySide6.QtCore',fromlist=['QUrl']).QUrl())
 dialog=component.create();assert dialog is not None,component.errors();dialog.open();QTest.qWait(100);dialog.close()
 print('PASS QML light/dark, narrow layout, settings and file dialog',flush=True)
 b.enqueue(sample_audio)
 until(lambda: b.data['jobs'] and b.data['jobs'][-1]['state'] in ['complete','failed','error'],240)
 assert b.data['jobs'][-1]['state']=='complete',b.data['jobs'][-1]
 assert b.song and b.song.get('game_notes'),b.song
 for theme in ['light','dark']:
  b.setting('theme',theme)
  for _ in range(20):
   window.grabWindow();QTest.qWait(30)
  snapshot=window.grabWindow()
  assert not snapshot.isNull(),'Window capture is empty'
  snapshot.save(str(data/('preview-'+theme+'.png')))
 print('PASS real queued separation, pitch and GAME through relocated worker',flush=True)
 b.muted=True;b.apply_audio();b.setSource('original');b.togglePlay();QTest.qWait(1200);assert b.player.position()>200
 b.setSource('vocals');QTest.qWait(800);assert b.vocal_player.position()>200 and b.vocal_player.error().value==0
 b.togglePlay();print('PASS original/vocal playback',flush=True)
 b.setSongHarmony(False)
 until(lambda: b.song.get('algorithm',{}).get('separation')=='mel_roformer',240)
 b.seek(1.0);b.togglePlay();QTest.qWait(600)
 before=b.player.position();b.setSongHarmony(True);QTest.qWait(700)
 assert b.song.get('algorithm',{}).get('separation')=='mel_bs'
 assert b.player.position()>before and b.state['playing']
 assert b.vocal_player.error().value==0 and b.vocal_player.position()>200
 b.togglePlay();print('PASS harmony off/on and uninterrupted transport',flush=True)
 song=data/'song.json';song.write_text(json.dumps(b.song,ensure_ascii=False),encoding='utf-8')
 b.setSpan(3);b.adjustView('center',2);b.adjustView('width',2);b.toggleOverview();b.toggleOverview()
 b.setPianoVolume(.01);b.previewPiano(60);QTest.qWait(500);assert b.piano is not None
 # Queued cancellation and running-job deletion use a copied sample to avoid duplicate detection.
 import shutil
 sample=data/'cancel-sample.wav';shutil.copy2(sample_audio,sample)
 b.enqueue(str(sample));until(lambda:b.active is not None,30);key=b.active['id'];b.removeJob(key)
 until(lambda:not any(j['id']==key for j in b.data['jobs']),30)
 print('PASS view controls, piano backend and running cancellation',flush=True)
 assert not warnings,warnings
 # Capture actual loaded modules before shutdown for dependency evidence.
 import psutil
 loaded=[m.path for m in psutil.Process().memory_maps()]
 (data/'loaded-libraries.json').write_text(json.dumps(loaded,indent=2))
finally:
 b.shutdown();window.close()
print('PASS shutdown',flush=True)

b2=Controller(data/'library',bootstrap=False);assert b2.data['songs'];b2.selectSong(0);assert b2.song;b2.shutdown();print('PASS library reopen',flush=True)
