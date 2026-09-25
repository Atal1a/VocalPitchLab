"""Offline pitch-model comparison. Run with the project's virtual environment."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import time

from app_paths import APP_ROOT,DATA_ROOT,MODEL_ROOT,prepare
ROOT = DATA_ROOT
prepare()
os.environ.setdefault('TORCH_HOME', str(MODEL_ROOT))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'work' / 'matplotlib'))

def ffmpeg_path():
    override = os.environ.get('VPL_FFMPEG')
    if override:
        target = Path(override).expanduser().resolve()
        if not target.is_file():raise FileNotFoundError('Configured FFmpeg executable is missing')
        return str(target)
    bundled = APP_ROOT/'bin/ffmpeg.exe'
    if bundled.is_file():
        return str(bundled)
    found = shutil.which('ffmpeg')
    if found:
        return found
    raise RuntimeError('FFmpeg not found. Add ffmpeg.exe to PATH.')

def decode(source, target, start, duration):
    cmd = [ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source), '-ss', str(start)]
    if duration > 0:
        cmd += ['-t', str(duration)]
    subprocess.run(cmd + ['-ar', '44100', '-ac', '2', '-c:a', 'pcm_f32le', str(target)], check=True)

def separate(audio, sr, device):
    import torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    model = get_model('htdemucs').to(device).eval()
    wav = torch.from_numpy(audio.T.copy()).float()
    ref = wav.mean(0)
    scale = ref.std().clamp(min=1e-8)
    normalized = (wav - ref.mean()) / scale
    with torch.inference_mode():
        stems = apply_model(model, normalized[None], device=device, shifts=0,
                            split=True, overlap=0.25, progress=True)[0].cpu()
    result = (stems[model.sources.index('vocals')] * scale + ref.mean()).numpy().T
    del model
    if device == 'cuda':
        torch.cuda.empty_cache()
    return result

def track(audio, sr, method, device, threshold=0.21):
    import numpy as np
    import librosa
    import torch
    import torchcrepe
    y = librosa.resample(audio.mean(axis=1), orig_sr=sr, target_sr=16000)
    if method == 'pyin':
        f0, voiced, confidence = librosa.pyin(y, sr=16000, fmin=65, fmax=1100,
                                            frame_length=1024, hop_length=160)
        raw = f0.copy()
    else:
        from resource_policy import batches,is_oom,clear
        for attempt_device,batch in [(device,b) for b in batches(device)]+([('cpu',32)] if device=='cuda' else []):
            if attempt_device=='cpu' and device=='cuda':
                from resource_policy import cpu_fallback
                cpu_fallback()
            try:
                pitch,periodicity=torchcrepe.predict(torch.from_numpy(y)[None],16000,hop_length=160,
                    fmin=65,fmax=1100,model=method,batch_size=batch,device=attempt_device,return_periodicity=True)
                break
            except RuntimeError as error:
                if not is_oom(error):raise
                clear();print('VPL_RESOURCE: reducing pitch batch or using CPU',flush=True)
        else:raise RuntimeError('Pitch inference exhausted allocation retries')
        periodicity = torchcrepe.filter.median(periodicity, 3)
        raw = pitch[0].cpu().numpy().copy()
        confidence = periodicity[0].cpu().numpy()
        voiced = confidence >= threshold
        f0 = raw.copy()
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=160)[0]
    n = min(len(f0), len(rms))
    f0, raw, confidence = f0[:n], raw[:n], confidence[:n]
    voiced = voiced[:n] & (rms[:n] > 10 ** (-55 / 20)) & np.isfinite(f0)
    f0[~voiced] = np.nan
    return np.arange(n) * 0.01, raw, f0, confidence, voiced

def write_track(path, data, offset=0):
    import numpy as np
    import librosa
    times, raw, f0, confidence, voiced = data
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['time_seconds', 'raw_hz', 'pitch_hz', 'midi_float', 'nearest_note', 'periodicity_or_probability', 'voiced'])
        for t, r, f, c, v in zip(times, raw, f0, confidence, voiced):
            midi = float(librosa.hz_to_midi(f)) if v else None
            writer.writerow([round(t + offset, 4), float(r) if np.isfinite(r) else '',
                float(f) if v else '', midi if v else '',
                librosa.midi_to_note(int(round(midi))) if v else '', float(c), int(v)])

def run(args, progress=None):
    progress = progress or (lambda value, message: None)
    import numpy as np
    import soundfile as sf
    import torch
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import librosa
    source = Path(args.file).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    from resource_policy import device as select_device
    device = select_device()
    stamp = time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns())[-6:]
    folder = ROOT / 'results' / (source.stem + '-' + stamp)
    folder.mkdir(parents=True)
    from resource_policy import hardware
    (folder/'hardware.json').write_text(json.dumps(hardware(),ensure_ascii=False,indent=2),encoding='utf-8')
    progress(5,'读取音频')
    decode(source, folder / 'original.wav', args.start, args.seconds)
    audio, sr = sf.read(folder / 'original.wav', dtype='float32', always_2d=True)
    if len(audio) < 1600:
        raise ValueError('Selected audio is empty or too short.')
    info = dict(source=str(source), clip_sha256=hashlib.sha256((folder / 'original.wav').read_bytes()).hexdigest(), start=args.start, duration=len(audio)/sr,
                device=device, torch=torch.__version__, separation='none' if args.no_separate else getattr(args,'separation','htdemucs'),
                fmin=65, fmax=1100, hop_seconds=0.01, crepe_threshold=0.21,
                silence_dbfs=-55, note='No ground truth: coverage is NOT accuracy.', models={})
    (folder / 'run.json').write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding='utf-8')
    tick = time.perf_counter()
    progress(15,'提取人声')
    if args.no_separate:vocals=audio
    elif getattr(args,'separation','htdemucs') in ['mel_roformer','mel_bs']:
        from vocal_separator import separate as high_quality,VERSION
        progress(15,'提取高质量人声');vocals=high_quality(audio,sr,device,folder);info['separation_version']=VERSION
    else:vocals=separate(audio,sr,device)
    if not args.no_separate and getattr(args,'separation','')=='mel_bs':
        sf.write(folder/'all-vocals.wav',vocals,sr,subtype='FLOAT')
        progress(35,'分离和声')
        vocals=high_quality(vocals,sr,device,folder,lead=True)
        info['lead_separation_version']='bs-frazer-becruily-eb90ee24-overlap4-v1'
    info['separation_seconds'] = time.perf_counter() - tick
    sf.write(folder / 'vocals.wav', vocals, sr, subtype='FLOAT')
    fig, ax = plt.subplots(figsize=(15, 5))
    for method in args.methods:
        progress(45 if method=='tiny' else 60,'识别人声音高')
        print('Pitch model:', method, flush=True)
        tick = time.perf_counter()
        data = track(vocals, sr, method, device)
        write_track(folder / (method + '.csv'), data, args.start)
        times, raw, f0, confidence, voiced = data
        info['models'][method] = dict(seconds=time.perf_counter()-tick, voiced_fraction=float(voiced.mean()))
        ax.plot(times + args.start, librosa.hz_to_midi(f0), label=method, linewidth=0.8, alpha=0.8)
    ax.set(xlabel='Time in original song (seconds)', ylabel='Pitch (MIDI; 69 = A4)', title='Pitch comparison — gaps indicate rejected/unvoiced frames')
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(folder / 'comparison.png', dpi=150)
    plt.close(fig)
    (folder / 'run.json').write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Results:', folder, flush=True)
    return folder

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Compare local vocal pitch models')
    parser.add_argument('file')
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--seconds', type=float, default=30, help='0 = whole song')
    parser.add_argument('--methods', nargs='+', choices=['tiny', 'full', 'pyin'], default=['tiny', 'full'])
    parser.add_argument('--no-separate', action='store_true', help='Only for isolated vocals / synthetic tests')
    args = parser.parse_args()
    if args.start < 0 or args.seconds < 0:
        parser.error('start and seconds must be nonnegative')
    run(args)
