import os,sys,json,random,runpy
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description='Seeded offline inference using an installed package')
parser.add_argument('stage',type=Path);parser.add_argument('data',type=Path);parser.add_argument('audio',type=Path)
parser.add_argument('--cpu',action='store_true')
args=parser.parse_args();stage=args.stage.resolve();data=args.data.resolve()
if data.exists() and any(data.iterdir()):raise SystemExit('Choose a fresh test data directory')
data.mkdir(parents=True,exist_ok=True)
if args.cpu:os.environ.update(VPL_DEVICE='cpu',CUDA_VISIBLE_DEVICES='-1',PYTORCH_NVML_BASED_CUDA_CHECK='0')
os.environ.update(VPL_DATA_DIR=str(data),VPL_MODEL_DIR=str(stage/'models'),PYTHONDONTWRITEBYTECODE='1')
os.environ['PATH']=str(stage/'bin')+os.pathsep+os.environ['PATH'];sys.path.insert(0,str(stage))
runpy.run_path(str(Path(__file__).parent/'fixtures/package_offline/sitecustomize.py'))
import numpy as np,torch
from vocalpitchlab.analysis.production_pipeline import analyze
for mode in ['mel_bs','mel_roformer']:
 random.seed(7301);np.random.seed(7301);torch.manual_seed(7301);torch.cuda.manual_seed_all(7301)
 if args.cpu:
  from vocalpitchlab.runtime.resource_policy import device
  assert device()=='cpu'
 result=analyze(args.audio.resolve(),separation=mode)
 (data/(mode+'.json')).write_text(json.dumps(result,default=str),encoding='utf-8')
 print('PASS',mode,flush=True)
