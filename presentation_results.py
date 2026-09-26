"""Prepare reusable note/display data without running any neural models."""
import csv
import json
from pathlib import Path
import numpy as np
from analysis_cache import stage, digest_file, atomic_json

PRESENTATION_VERSION = 'presentation-v1'


def read_curve(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    times = np.array([float(r['time_seconds']) for r in rows])
    midi = np.array([float(r['midi_float']) if r['midi_float'] else np.nan for r in rows])
    score = np.array([float(r.get('rmvpe_max_salience', r.get('periodicity_or_probability', 0)) or 0) for r in rows])
    if len(times) and (not np.isfinite(times).all() or np.any(np.diff(times) <= 0)):
        raise ValueError('Invalid curve timestamps')
    return times, midi, score


def prepare(song):
    from game_notes import display_cache_path, reconcile_notes, REFINEMENT_VERSION, RECONCILE_SETTINGS
    from curve_reliability import display_weight, note_evidence, NOTE_EVIDENCE_VERSION as evidence_version, VERSION as display_version
    from main_notes import extract, current_settings
    curves = song['curves']
    key = next(k for k in ['rmvpe_tracked', 'rmvpe_vocals', 'tuned_vocals', 'crepe_full'] if k in curves)
    raw = display_cache_path(song)
    has_game = raw.is_file()
    signatures = {k: digest_file(curves[k]) for k in [key, 'crepe_full', 'rmvpe_vocals'] if k in curves}
    signature = dict(version=PRESENTATION_VERSION, refinement=REFINEMENT_VERSION, evidence=evidence_version, display=display_version,
                     curves=signatures, game=digest_file(raw) if has_game else None,
                     fallback=current_settings() if not has_game else None, duration=song['duration'], settings=RECONCILE_SETTINGS)

    def build(folder):
        times, midi, _ = read_curve(curves[key])
        scores = []
        for name in ['crepe_full', 'rmvpe_vocals']:
            if name in curves:
                t, _, s = read_curve(curves[name])
                scores.append(np.interp(times, t, s, left=0, right=0) if len(t) else np.zeros(len(times)))
            else:
                scores.append(np.zeros(len(times)))
        c, r = scores
        weight = display_weight(midi, c, r) if len(times) else np.array([])
        evidence = note_evidence(midi, c, r)
        original = json.loads(raw.read_text(encoding='utf-8'))['notes'] if has_game else extract(times, midi)
        notes = reconcile_notes(original, times, midi, reliability=evidence)
        # Copy and bound records; never mutate model output or pitch samples.
        bounded = []
        for item in notes:
            n = dict(item); n['start'] = max(0., float(n['start'])); n['end'] = min(float(song['duration']), float(n['end']))
            if n['end'] <= n['start']:
                continue
            if bounded and n['start'] < bounded[-1]['end'] - 1e-7:
                raise ValueError('Overlapping final note events')
            n.update(duration=round(n['end']-n['start'], 4), note_id=len(bounded)+1)
            n.setdefault('status', 'GAME' if has_game else 'curve_fallback')
            bounded.append(n)
        atomic_json(folder/'notes.json', dict(version=REFINEMENT_VERSION, source='GAME' if has_game else 'curve_fallback', notes=bounded))
        np.savez_compressed(folder/'evidence.npz', time=times, weight=weight, evidence=evidence)
        return dict(notes=folder/'notes.json', evidence=folder/'evidence.npz')

    paths, meta = stage('presentation', signature, build)
    # Loudness depends on audio, not note rules, and can be reused independently.
    audio = Path(song['audio']['vocals'])
    def loudness(folder):
        from plot_support import vocal_loudness, vocal_gain
        t, v = vocal_loudness(audio, folder)
        np.savez_compressed(folder/'loudness.npz', time=t, level=v)
        atomic_json(folder/'gain.json', dict(gain=vocal_gain(song['audio']['original'], audio)))
        return dict(loudness=folder/'loudness.npz', gain=folder/'gain.json')
    levels, loud_meta = stage('loudness', dict(version='rms-display-v2', audio=digest_file(audio), original=digest_file(song['audio']['original'])), loudness)
    return dict(version=PRESENTATION_VERSION, refinement=REFINEMENT_VERSION, evidence_version=evidence_version,
                display_version=display_version,
                settings=RECONCILE_SETTINGS, fallback_settings=current_settings() if not has_game else None,
                primary=key, notes=str(paths['notes']), evidence=str(paths['evidence']), loudness=str(levels['loudness']),
                gain=json.loads(levels['gain'].read_text(encoding='utf-8'))['gain'],
                game_available=has_game, cache=dict(presentation=meta, loudness=loud_meta))


def load(value):
    from game_notes import REFINEMENT_VERSION, RECONCILE_SETTINGS
    from main_notes import current_settings
    from curve_reliability import NOTE_EVIDENCE_VERSION as VERSION, VERSION as display_version
    if value.get('version') != PRESENTATION_VERSION or value.get('refinement') != REFINEMENT_VERSION or value.get('evidence_version') != VERSION or value.get('display_version') != display_version:
        raise ValueError('Presentation needs refresh')
    if value.get('settings')!=RECONCILE_SETTINGS or (not value.get('game_available') and value.get('fallback_settings')!=current_settings()):
        raise ValueError('Note settings changed')
    notes = json.loads(Path(value['notes']).read_text(encoding='utf-8'))['notes']
    with np.load(value['evidence'], allow_pickle=False) as d:
        evidence = (d['time'], d['weight'])
    with np.load(value['loudness'], allow_pickle=False) as d:
        loudness = (d['time'], d['level'])
    for times,values in (evidence,loudness):
        if times.ndim!=1 or values.shape!=times.shape or not np.isfinite(times).all() or not np.isfinite(values).all() or np.any(np.diff(times)<=0):
            raise ValueError('Invalid presentation timeline')
    if not all(np.isfinite([n['start'],n['end'],n['midi']]).all() and 0<=n['start']<n['end'] for n in notes):
        raise ValueError('Invalid presentation note')
    if not all(a['end']<=b['start']+1e-7 for a,b in zip(notes,notes[1:])):
        raise ValueError('Overlapping presentation notes')
    return notes, evidence, loudness


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--song-file',required=True);parser.add_argument('--result-file',required=True)
    args=parser.parse_args()
    song=json.loads(Path(args.song_file).read_text(encoding='utf-8'))
    atomic_json(Path(args.result_file),prepare(song))
