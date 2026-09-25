"""Local-only high quality separation using the validated pinned RoFormer."""
import sys,os,logging,gc
from pathlib import Path
import numpy as np,soundfile as sf

from app_paths import APP_ROOT,MODEL_ROOT
ROOT=APP_ROOT
VERSION='mel-kim-87201f4d-fp32-overlap4-v1'

def available():
    return all(p.is_file() for p in [MODEL_ROOT/'roformer/vocals_mel_band_roformer.ckpt',
        MODEL_ROOT/'roformer/vocals_mel_band_roformer.yaml',ROOT/'vendor/separation-runtime/audio_separator/__init__.py'])

def separate(audio,sr,device,folder,lead=False):
    if not available():raise FileNotFoundError('High quality vocal separation model/runtime missing')
    if sr!=44100:raise ValueError('RoFormer expects 44100 Hz decoded audio')
    import torch
    from lab import ffmpeg_path
    sys.path.insert(0,str(ROOT/'vendor/separation-runtime'))
    os.environ['PATH']=str(Path(ffmpeg_path()).parent)+os.pathsep+os.environ['PATH']
    from audio_separator.separator import Separator
    torch.set_num_threads(4)
    work=Path(folder)/('lead-separation' if lead else 'separation');work.mkdir(exist_ok=True)
    gain=min(1.,.95/max(float(np.max(np.abs(audio))),1e-8))
    source=work/'input.wav';sf.write(source,audio*gain,sr,subtype='FLOAT')
    from resource_policy import separation_segments,is_oom,clear
    attempts=[(device,segment) for segment in separation_segments(device)]
    if device=='cuda':attempts.append(('cpu',256))
    for target,segment in attempts:
        if target=='cpu' and device=='cuda':
            from resource_policy import cpu_fallback
            cpu_fallback()
        model=None
        try:
            params={'batch_size':1,'overlap':4}
            if segment:params.update(segment_size=segment,override_model_segment_size=True)
            model=Separator(log_level=logging.WARNING,model_file_dir=str(MODEL_ROOT/('lead-separation' if lead else 'roformer')),output_dir=str(work),
                output_format='WAV',output_single_stem='Vocals',normalization_threshold=1.,amplification_threshold=0.,
                use_soundfile=True,mdxc_params=params)
            model.torch_device=torch.device(target)
            model.load_model(model_filename='bs_roformer_karaoke_frazer_becruily.ckpt' if lead else 'vocals_mel_band_roformer.ckpt')
            paths=model.separate(str(source));path=Path(paths[0]);path=path if path.is_absolute() else work/path
            voice,rate=sf.read(path,dtype='float32',always_2d=True);voice/=gain
            if voice.shape!=audio.shape or rate!=sr or not np.isfinite(voice).all():raise ValueError('Invalid separated audio')
            import json
            (work/'resources.json').write_text(json.dumps(dict(device=target,segment=segment,overlap=4)))
            return voice
        except RuntimeError as error:
            if not is_oom(error):raise
            print('VPL_RESOURCE: reducing separation window or using CPU',flush=True)
        finally:
            del model;clear()
    raise RuntimeError('Separation exhausted allocation retries')
