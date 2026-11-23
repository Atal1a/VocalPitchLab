"""Fixed production pipeline; research comparisons remain in lab.py."""
import os
from pathlib import Path
import time
import numpy as np
import soundfile as sf
from vocalpitchlab.analysis.analysis_cache import stage, digest_file, atomic_json
from vocalpitchlab.analysis.recording import RecordingChanged, prepared_original, source_signature

SEPARATION_MODES = ('original', 'mel_roformer', 'bs_only', 'mel_bs', 'htdemucs')


def prepare_stems(source, separation, progress, recording, device, resource, cached, metrics, timeline):
    from vocalpitchlab.audio.audio_io import decode, separate as demucs
    from vocalpitchlab.audio.vocal_separator import separate, VERSION as separation_version

    progress(5, '读取音频')
    signature = recording.get('source_signature') if recording else None
    original = prepared_original(recording) if recording else None
    if original:
        source_hash = recording['source_sha256']
        metrics['decode'] = dict(key=recording['decode_key'], content={'audio': recording['decoded_sha256']},
                                 hit=True, seconds=0)
    elif recording:
        source_hash = recording['source_sha256']
        if not source_hash:
            raise RecordingChanged('Verified recording unavailable')
    else:
        with timeline.span('source_hash'):
            signature = source_signature(source)
            source_hash = digest_file(source)

    def decoded(folder):
        nonlocal signature
        if recording:
            if not source.is_file():
                raise RecordingChanged('Verified recording unavailable')
            signature = source_signature(source)
            if digest_file(source) != source_hash:
                raise RecordingChanged('Input contents changed')
        path = folder/'original.wav'
        decode(source, path, 0, 0)
        if source_signature(source) != signature or digest_file(source) != source_hash:
            raise RecordingChanged('Input contents changed while decoding')
        if recording and recording['decoded_sha256'] and digest_file(path) != recording['decoded_sha256']:
            raise RecordingChanged('Decoded audio does not match the saved recording')
        info = sf.info(path)
        if info.frames < 1600 or info.samplerate != 44100 or info.channels != 2:
            raise ValueError('Invalid decoded audio')
        return dict(audio=path)
    if original is None:
        original = cached('decode', dict(source=source_hash, version='ffmpeg-float32-stereo-44100-v1'), decoded)['audio']
        if recording and recording['decoded_sha256'] and metrics['decode']['content']['audio'] != recording['decoded_sha256']:
            raise RecordingChanged('Decoded audio does not match the saved recording')
    duration = sf.info(original).duration
    def separated(input_path, folder, lead=False):
        audio, sr = sf.read(input_path, dtype='float32', always_2d=True)
        vocals = demucs(audio, sr, device) if separation == 'htdemucs' else separate(audio, sr, device, folder, lead=lead)
        if vocals.shape != audio.shape or not np.isfinite(vocals).all():
            raise ValueError('Invalid separated audio')
        path = folder/'vocals.wav'; sf.write(path, vocals, sr, subtype='FLOAT')
        return dict(audio=path)
    vocals = original
    vocal_key = metrics['decode']['content']['audio']
    full_version = None
    if separation in ('mel_roformer', 'mel_bs', 'htdemucs'):
        progress(15, '提取人声')
        full_version = 'htdemucs-v1' if separation == 'htdemucs' else separation_version
        vocals = cached('vocals', dict(input=vocal_key, version=full_version, resource=resource),
                        lambda folder: separated(original, folder),
                        after_publish=lambda folder: (folder/'separation'/'v.wav').unlink(missing_ok=True))['audio']
        vocal_key = metrics['vocals']['content']['audio']
    lead_version = 'bs-frazer-becruily-eb90ee24-overlap4-v1'
    harmony = separation in ('mel_bs', 'bs_only')
    if harmony:
        progress(35, '分离和声')
        harmony_input = vocals
        vocals = cached('lead', dict(input=vocal_key, version=lead_version, resource=resource),
                        lambda folder: separated(harmony_input, folder, lead=True),
                        after_publish=lambda folder: (folder/'lead-separation'/'v.wav').unlink(missing_ok=True))['audio']
        vocal_key = metrics['lead']['content']['audio']
    song = dict(name=source.stem, duration=duration, source=str(source), source_sha256=source_hash,
                source_signature=signature, baseline=str(vocals.parent),
                audio=dict(original=str(original), vocals=str(vocals)), stage_cache=metrics,
                created=time.strftime('%Y-%m-%d %H:%M:%S'),
                algorithm=dict(pipeline='lead-default-v2', separation=separation,
                               separation_version=full_version, harmony_separation=harmony))
    if separation == 'mel_bs':
        song['full_vocals'] = str(harmony_input)
    if harmony:song['algorithm']['lead_separation_version'] = lead_version
    return song, vocal_key


def analyze(source, separation='mel_bs', progress=None, *, recording=None, stems_only=False, stems_ready=None):
    from vocalpitchlab.analysis.pipeline_timing import Timeline
    from vocalpitchlab.runtime.resource_policy import device as select_device, clear, overlap_game, hardware
    import torch

    if separation not in SEPARATION_MODES or (stems_only and separation == 'original'):
        raise ValueError('Invalid separation')
    timeline=Timeline()
    progress = progress or (lambda value, message: None)
    source = Path(source).resolve()
    hardware(replay=True)
    device = select_device()
    if device=='cuda':torch.cuda.reset_peak_memory_stats()
    resource = dict(device=device, torch=torch.__version__, memory_limit=os.environ.get('VPL_CUDA_MEMORY_GIB', '0'))
    if separation == 'original':
        torch.set_num_threads(4)
    else:
        from vocalpitchlab.audio.separation_execution import select as separation_policy
        resource['separation_execution']=separation_policy(device)
    metrics = {}

    def cached(name, signature, build, *, after_publish=None):
        with timeline.span(name):paths, meta = stage(name, signature, build, after_publish=after_publish)
        if name in ['vocals','lead']:
            import json
            detail=paths['audio'].parent/('lead-separation' if name=='lead' else 'separation')/'resources.json'
            if detail.is_file():
                try:meta['recorded_execution']=dict(from_cache=meta['hit'],details=json.loads(detail.read_text()))
                except (OSError,ValueError):pass
        metrics[name] = meta
        return paths

    song, vocal_key = prepare_stems(source, separation, progress, recording, device, resource, cached, metrics, timeline)
    if stems_ready is not None and separation != 'original':
        stems_ready(song)
    clear()
    if stems_only:
        metrics['timing'] = timeline.report()
        return song

    vocals = Path(song['audio']['vocals'])
    duration = song['duration']
    from vocalpitchlab.audio.audio_io import track, write_track
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    cancel_game=Event()
    from vocalpitchlab.analysis.game_notes import GameNotes, VERSION, REFINEMENT_VERSION
    def game(folder):
        audio, sr = sf.read(vocals, dtype='float32', always_2d=True)
        notes = GameNotes().transcribe(audio, sr, cancel_event=cancel_game)
        if not all(0 <= n['start'] < n['end'] <= duration+.001 for n in notes) or not all(a['end'] <= b['start'] for a,b in zip(notes, notes[1:])):
            raise ValueError('Invalid GAME note events')
        atomic_json(folder/'game.json', dict(version=VERSION, notes=notes))
        return dict(notes=folder/'game.json')
    def run_game():
        return cached('game', dict(input=vocal_key, version=VERSION), game)['notes']
    parallel=overlap_game(device,duration)
    metrics['game_overlapped']=parallel
    executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='vpl-notes') if parallel else None
    game_future=executor.submit(run_game) if executor else None
    try:
        progress(60, '识别人声音高')
        def crepe(folder):
            audio, sr = sf.read(vocals, dtype='float32', always_2d=True)
            write_track(folder/'full.csv', track(audio, sr, 'full', device))
            return dict(curve=folder/'full.csv')
        full_curve = cached('crepe-full', dict(input=vocal_key, version='full-hop10ms-65-1100-v1', resource=resource), crepe)['curve']
        clear()
        progress(78, '整理连续音高')
        def rmvpe(folder):
            from vocalpitchlab.audio.rmvpe_adapter import PitchEstimator
            from vocalpitchlab.analysis.pitch_models import continuous_pitch
            audio, sr = sf.read(vocals, dtype='float32', always_2d=True)
            raw, salience, rms = PitchEstimator(device).track(audio, sr, return_salience=True)
            pitch, score = continuous_pitch(salience, rms, raw[4])
            write_track(folder/'rmvpe.csv', raw)
            write_track(folder/'tracked.csv', (raw[0], pitch.copy(), pitch, score, np.isfinite(pitch)))
            return dict(raw=folder/'rmvpe.csv', tracked=folder/'tracked.csv')
        curves = cached('rmvpe', dict(input=vocal_key, version='rmvpe-continuous-v1', resource=resource), rmvpe)
        clear()
    except BaseException:
        cancel_game.set()
        raise
    finally:
        if executor:executor.shutdown(wait=True,cancel_futures=True)
    song.update(result_format=2, review_windows=[],
                curves=dict(crepe_full=str(full_curve), rmvpe_vocals=str(curves['raw']), rmvpe_tracked=str(curves['tracked'])))
    song['algorithm']['display_pitch'] = 'rmvpe_tracked'
    progress(90, '识别音符边界')
    try:
        song['game_notes'] = str(game_future.result() if game_future else run_game())
        song['game_notes_version'] = VERSION
    except Exception as error:
        metrics['game_error'] = type(error).__name__ + ': ' + str(error)
        progress(93, '音符模型暂不可用，使用连续曲线整理音符')
    clear()
    progress(96, '整理主要音符')
    from vocalpitchlab.analysis.presentation_results import prepare
    with timeline.span('presentation'):song['presentation'] = prepare(song)
    song['main_notes'] = song['presentation']['notes']
    song['algorithm']['note_events'] = (VERSION if song.get('game_notes') else 'curve-fallback')+'+'+REFINEMENT_VERSION
    if device == 'cuda':
        metrics['cuda_peak_allocated_mib'] = torch.cuda.max_memory_allocated()/2**20
        metrics['cuda_peak_reserved_mib'] = torch.cuda.max_memory_reserved()/2**20
    metrics['timing']=timeline.report()
    return song
