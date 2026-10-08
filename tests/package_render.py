"""Check the installed Qt renderer without running analysis in the UI thread."""
import argparse,json,os,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('stage',type=Path);p.add_argument('data',type=Path);p.add_argument('song',type=Path);p.add_argument('--software',action='store_true');a=p.parse_args()
stage=a.stage.resolve();data=a.data.resolve()
if data.exists():raise SystemExit('Choose a fresh render directory')
data.mkdir(parents=True)
os.environ.update(VPL_DATA_DIR=str(data),VPL_MODEL_DIR=str(stage/'models'),QSG_RHI_BACKEND='d3d11',QT_QPA_PLATFORM='windows',PYTHONDONTWRITEBYTECODE='1')
os.environ.pop('QT_QUICK_BACKEND',None);sys.path.insert(0,str(stage))
os.environ['QSG_RHI_PREFER_SOFTWARE_RENDERER']='1' if a.software else '0'
os.environ['QSG_INFO']='1'
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt,qInstallMessageHandler
from PySide6.QtQuick import QSGRendererInterface
from PySide6.QtTest import QTest
from vocalpitchlab.ui.app import Controller,create_engine
app=QGuiApplication([]);warnings=[];messages=[]
def capture(k,c,m):
 messages.append(m)
 if '.qml:' in m or 'Failed to' in m:warnings.append(m)
qInstallMessageHandler(capture)
b=Controller(data/'library',bootstrap=False);b.data['songs']=[json.loads(a.song.read_text(encoding='utf-8'))];b.selectSong(0)
engine=create_engine(b);assert engine.rootObjects();window=engine.rootObjects()[0]
window.setFlags(Qt.WindowType.Tool|Qt.WindowType.WindowDoesNotAcceptFocus|Qt.WindowType.WindowStaysOnBottomHint)
window.setWidth(1060);window.setHeight(720)
try:
 for theme in ('light','dark'):
  b.setting('theme',theme);window.show()
  # Occluded windows throttle animation frames; render frames explicitly before capture.
  for _ in range(20):
   window.grabWindow();QTest.qWait(30)
  api=window.rendererInterface().graphicsApi();assert api==QSGRendererInterface.GraphicsApi.Direct3D11,api
  im=window.grabWindow();assert not im.isNull();im.save(str(data/(theme+'.png')))
 assert not warnings,warnings
 if a.software:assert any('Microsoft Basic Render Driver' in m and i+1<len(messages) and 'using this adapter' in messages[i+1] for i,m in enumerate(messages)),messages
 (data/'result.json').write_text(json.dumps(dict(renderer=str(api),software=a.software,themes=['light','dark'],warnings=warnings),indent=2))
finally:
 (data/'renderer.log').write_text('\n'.join(messages),encoding='utf-8')
 b.shutdown();window.close()
print('PASS native Direct3D 11 rendering',flush=True)
