"""Local-only high quality separation using the validated pinned RoFormer."""
import sys,os,logging,gc,time
from pathlib import Path
import numpy as np,soundfile as sf

from app_paths import APP_ROOT,MODEL_ROOT
ROOT=APP_ROOT
VERSION='mel-kim-87201f4d-adaptive-overlap4-v2'

def prepare_decoded_mix(instance,path):
    """Pass our decoded float32 stereo audio through upstream validation."""
    audio=instance.vpl_decoded_mix
    instance.input_bit_depth=32;instance.input_subtype='FLOAT'
    return type(instance).prepare_mix(instance,audio)

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
    # Logical filename is used only to name output stems by the pinned runtime.
    # Keep FLOAT-WAV-equivalent rounding, without writing then rereading input.
    source=work/'input.wav';scaled_audio=np.asarray(audio*gain,dtype=np.float32)
    from resource_policy import separation_segments,is_oom,clear
    from separation_execution import select,configure_attention,precision_failure
    import separation_pool
    policy=select(device);mode=policy['mode']
    attempts=[(device,segment,mode) for segment in separation_segments(device)]
    if device=='cuda':
        if mode=='amp':attempts.append(('cuda',256,'fp32'))
        attempts.append(('cpu',256,'fp32'))
    rejected_amp=False
    for attempt,(target,segment,precision) in enumerate(attempts):
        if rejected_amp and precision=='amp':precision='fp32'
        if target=='cpu' and device=='cuda':
            from resource_policy import cpu_fallback
            cpu_fallback()
        model=None
        try:
            load_start=time.perf_counter()
            model_dir=MODEL_ROOT/('lead-separation' if lead else 'roformer')
            filename='bs_roformer_karaoke_frazer_becruily.ckpt' if lead else 'vocals_mel_band_roformer.ckpt'
            identity=tuple((str(p.resolve()),p.stat().st_size,p.stat().st_mtime_ns) for p in [model_dir/filename]+sorted(model_dir.glob('*.yaml')))
            key=(target,segment,precision,identity)
            model=separation_pool.take(key)
            reused=model is not None
            params={'batch_size':1,'overlap':4}
            if segment:params.update(segment_size=segment,override_model_segment_size=True)
            if reused:
                model.output_dir=str(work);model.model_instance.output_dir=str(work)
                model.model_instance.model_run.to(torch.device(target))
            else:
                model=Separator(log_level=logging.WARNING,model_file_dir=str(model_dir),output_dir=str(work),
                    output_format='WAV',output_single_stem='Vocals',normalization_threshold=1.,amplification_threshold=0.,
                    use_soundfile=True,mdxc_params=params,use_autocast=precision=='amp')
                model.torch_device=torch.device(target)
                model.load_model(model_filename=filename)
            if precision=='amp':configure_attention(model.model_instance)
            load_seconds=time.perf_counter()-load_start
            from types import MethodType
            model.model_instance.vpl_decoded_mix=scaled_audio
            model.model_instance.prepare_mix=MethodType(prepare_decoded_mix,model.model_instance)
            # WAV/soundfile is fixed here; bypass the generic writer's input-file
            # duration lookup, retaining its validation, normalization and atomic export.
            model.model_instance.write_audio=model.model_instance.write_audio_soundfile
            inference_start=time.perf_counter()
            paths=model.separate(str(source));path=Path(paths[0]);path=path if path.is_absolute() else work/path
            separation_seconds=time.perf_counter()-inference_start
            read_start=time.perf_counter()
            voice,rate=sf.read(path,dtype='float32',always_2d=True);voice/=gain
            if voice.shape!=audio.shape or rate!=sr:raise ValueError('Invalid separated audio shape or rate')
            if not np.isfinite(voice).all():raise ValueError('Non-finite separated audio')
            read_seconds=time.perf_counter()-read_start
            cache_start=time.perf_counter()
            separation_pool.put(key,model)
            cache_store_seconds=time.perf_counter()-cache_start
            import json
            (work/'resources.json').write_text(json.dumps(dict(device=target,segment=segment,overlap=4,
                requested_policy=policy,precision=precision,precision_fallback=rejected_amp,
                successful_attempt=attempt+1,model_reused=reused,load_seconds=round(load_seconds,4),
                separation_and_export_seconds=round(separation_seconds,4),read_and_validate_seconds=round(read_seconds,4),
                cache_store_seconds=round(cache_store_seconds,4))))
            return voice
        except (RuntimeError,ValueError) as error:
            separation_pool.clear()
            if is_oom(error):
                print('VPL_RESOURCE: reducing separation window or using CPU',flush=True)
            elif precision=='amp' and precision_failure(error):
                rejected_amp=True
                attempts.insert(attempt+1,(target,segment,'fp32'))
                print('VPL_RESOURCE: separation precision fallback to FP32',flush=True)
            else:raise
        finally:
            del model;clear()
    raise RuntimeError('Separation exhausted allocation retries')
