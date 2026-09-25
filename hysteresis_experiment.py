"""Offline dual-threshold experiment. Never changes production or library files."""
import csv
import json
from pathlib import Path
import numpy as np
from benchmark_vocadito import OUT, DATA, predict, single, metrics, save
from lab import ROOT, write_track
from main_notes import extract, audio_onsets, current_settings

DEST = ROOT/'results/hysteresis-v1'


def recover(d, baseline, config):
    """Strict baseline opens a run. Lower threshold may only continue it.

    No interpolation, no state across unsupported frames, bounded continuation.
    CREPE supports larger steps; strong primary frames keep real leaps intact.
    """
    out = baseline.copy()
    low = single(d, 'rmvpe', config['low'], 3)
    auxiliary = single(d, 'crepe', .5, 3)
    previous = np.nan
    weak_frames = 0
    for i in range(len(out)):
        if np.isfinite(baseline[i]):
            previous = out[i]
            weak_frames = 0
            continue
        supported = (np.isfinite(auxiliary[i]) and
                     abs(auxiliary[i]-low[i]) <= .5)
        if (np.isfinite(previous) and np.isfinite(low[i]) and
                weak_frames < config['max_frames'] and
                (abs(low[i]-previous) <= 1 or supported)):
            out[i] = low[i]
            previous = out[i]
            weak_frames += 1
        else:
            previous = np.nan
            weak_frames = 0
    return out


def aligned_metrics(d, midi):
    ix=np.rint(d['ref_time']/.01).astype(int)
    valid=(ix>=0)&(ix<len(midi)); p=np.full(len(ix),np.nan)
    p[valid]=midi[ix[valid]]
    return metrics(d['ref_hz'],p)


def summarize(rows):
    singers={}
    for row in rows:singers.setdefault(row['singer'],[]).append(row['metrics'])
    return {k:float(np.mean([np.mean([r[k] for r in group]) for group in singers.values()]))
            for k in rows[0]['metrics']}


def evaluate(rows, base, config=None):
    detail=[]
    for row in rows:
        with np.load(OUT/'cache'/f"{row['track_id']}.npz") as d:
            p=predict(d,base)
            if config:p=recover(d,p,config)
            detail.append(dict(track=row['track_id'],singer=row['singer_id'],metrics=aligned_metrics(d,p)))
    return dict(macro=summarize(detail),tracks=detail)


def main():
    import librosa
    import soundfile as sf
    from validate_pipeline import measure
    DEST.mkdir(exist_ok=True)
    split=json.loads((OUT/'split.json').read_text(encoding='utf-8'))
    base=json.loads((OUT/'selected-config.json').read_text(encoding='utf-8'))
    protocol=dict(baseline=base,search_low=[.1,.2,.3],search_max_frames=[12,24],
                  frame_seconds=.01,selection='development singer macro balanced only',
                  safeguards='RMS/range gate; no unsupported gap crossing; max one semitone/frame unless auxiliary agrees; strict primary remains unchanged',
                  limitation='Previously used test and mixtures are regression data, not a new independent test. Song coverage is not accuracy.')
    pp=DEST/'protocol.json'
    if pp.exists():assert json.loads(pp.read_text(encoding='utf-8'))==protocol
    else:save(pp,protocol)
    development=[]
    for low in protocol['search_low']:
        for frames in protocol['search_max_frames']:
            c=dict(low=low,max_frames=frames)
            development.append(dict(config=c,score=evaluate(split['development'],base,c)['macro']))
    chosen=max(development,key=lambda r:r['score']['balanced'])['config']
    frozen=DEST/'selected-config.json'
    if frozen.exists():assert json.loads(frozen.read_text())==chosen
    else:save(frozen,chosen)
    save(DEST/'development.json',dict(baseline=evaluate(split['development'],base)['macro'],candidates=development))
    test={label:evaluate(split['test'],base,c) for label,c in [('baseline',None),('candidate',chosen)]}
    save(DEST/'test.json',test)
    print('Frozen candidate',chosen,'test', {k:v['macro'] for k,v in test.items()},flush=True)

    # Cached separated mixtures test the actual separation -> pitch pipeline.
    mixed=[];settings=current_settings()
    for folder in sorted((ROOT/'results/pipeline-validation-v1').glob('*')):
        if not (folder/'pitch.npz').exists():continue
        tid=folder.name.split('_')[0]
        d=dict(np.load(folder/'pitch.npz'))
        ref=np.load(OUT/'cache'/f'{tid}.npz')
        d.update(ref_time=ref['ref_time'],ref_hz=ref['ref_hz'])
        audio,sr=sf.read(folder/'vocals.wav',always_2d=True,dtype='float32')
        onsets=audio_onsets(audio,sr,settings['onset_prominence_db'])
        refs={ann:np.loadtxt(DATA/'Annotations/Notes'/f'vocadito_{tid}_notes{ann}.csv',delimiter=',',ndmin=2) for ann in ['A1','A2']}
        baseline=predict(d,base);entry=dict(case=folder.name)
        for label,p in [('baseline',baseline),('candidate',recover(d,baseline,chosen))]:
            notes=extract(np.arange(len(p))*.01,p,settings,onsets)
            entry[label]=measure(p,np.column_stack((d['ref_time'],d['ref_hz'])),notes,refs)
        mixed.append(entry)
    save(DEST/'mixtures.json',mixed)
    print('Mixtures complete',len(mixed),flush=True)

    library=json.loads((ROOT/'library/index.json').read_text(encoding='utf-8'))
    song=next(s for s in library['songs'] if '小镇姑娘' in s['name'])
    d={}
    for key,model,score_key in [('crepe_full','crepe','periodicity_or_probability'),('rmvpe_vocals','rmvpe','rmvpe_max_salience')]:
        with open(song['curves'][key],encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        d[model+'_raw']=np.array([float(r['raw_hz'] or 'nan') for r in rows])
        d[model+'_score']=np.array([float(r[score_key]) for r in rows])
    audio,sr=sf.read(song['audio']['vocals'],always_2d=True,dtype='float32')
    y=librosa.resample(audio.mean(axis=1),orig_sr=sr,target_sr=16000)
    d['rms']=librosa.feature.rms(y=y,frame_length=1024,hop_length=160)[0]
    n=min(map(len,d.values()));d={k:v[:n] for k,v in d.items()}
    baseline=predict(d,base);candidate=recover(d,baseline,chosen)
    times=np.arange(n)*.01;onsets=audio_onsets(audio,sr,settings['onset_prominence_db'])
    report=dict(name=song['name'],config=chosen,intervals=[])
    notes={label:extract(times,p,settings,onsets) for label,p in [('baseline',baseline),('candidate',candidate)]}
    for lo,hi in [(170.36,170.73),(171.97,172.13)]:
        mask=(times>=lo)&(times<hi);entry=dict(start=lo,end=hi,frames=int(mask.sum()))
        for label,p in [('baseline',baseline),('candidate',candidate)]:
            entry[label]=dict(valid_frames=int(np.isfinite(p[mask]).sum()),notes=[note for note in notes[label] if note['start']<hi and note['end']>lo])
        report['intervals'].append(entry)
    report['added_seconds']=float((np.isfinite(candidate)&~np.isfinite(baseline)).sum()*.01)
    save(DEST/'song-report.json',report)
    hz=440*2**((candidate-69)/12)
    write_track(DEST/'candidate.csv',(times,hz,hz,np.zeros(n),np.isfinite(hz)))
    save(DEST/'main-notes.json',dict(settings=settings,notes=notes['candidate'],experimental=True))
    np.savez_compressed(DEST/'song-comparison.npz',time=times,baseline=baseline,candidate=candidate)
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
