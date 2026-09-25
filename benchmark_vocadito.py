"""Singer-disjoint, development-only calibration. Frozen test is never searched."""
import csv, json, hashlib
from pathlib import Path
import numpy as np
from scipy.ndimage import median_filter
from lab import ROOT

DATA=ROOT/'datasets/vocadito'
OUT=ROOT/'results/vocadito-v1'

def save(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def smooth(x,width):
    out=x.copy()
    edges=np.diff(np.r_[False,np.isfinite(x),False].astype(int))
    for a,b in zip(np.where(edges==1)[0],np.where(edges==-1)[0]):
        out[a:b]=median_filter(x[a:b],size=width,mode='nearest')
    return out

def single(d,model,threshold,width):
    raw=d[model+'_raw']; score=d[model+'_score']
    mask=(score>=threshold)&(raw>=65)&(raw<=1100)&(d['rms']>10**(-55/20))
    midi=69+12*np.log2(np.maximum(raw,1e-12)/440)
    midi[~mask]=np.nan
    return smooth(midi,width)

def predict(d,c):
    if c['model']!='fusion':return single(d,c['model'],c['threshold'],c['width'])
    a=predict(d,c['crepe']); b=predict(d,c['rmvpe'])
    out=(a if c['primary']=='crepe' else b).copy()
    agree=np.isfinite(a)&np.isfinite(b)&(np.abs(a-b)<=.5)
    out[agree]=c['weight']*a[agree]+(1-c['weight'])*b[agree]
    if c.get('fallback'):
        # Recover only independently supported gaps; never interpolate silence.
        f=c['fallback']; secondary='crepe' if c['primary']=='rmvpe' else 'rmvpe'
        alternative=single(d,secondary,f['threshold'],3)
        support=single(d,c['primary'],f['support_threshold'],3)
        eligible=np.isfinite(alternative)&np.isfinite(support)&(np.abs(alternative-support)<=f['agreement_semitones'])
        edges=np.diff(np.r_[False,eligible,False].astype(int))
        for start,end in zip(np.where(edges==1)[0],np.where(edges==-1)[0]):
            if end-start<f['min_frames']:continue
            fill=~np.isfinite(out[start:end])
            out[start:end][fill]=alternative[start:end][fill]
    return out

def metrics(ref,pred):
    v=ref>0;p=np.isfinite(pred)
    target=69+12*np.log2(np.maximum(ref,1e-12)/440)
    error=np.abs(target-pred)*100
    correct=v&p&(error<=50)
    recall=float(correct.sum()/max(1,v.sum()))
    silence=float((~v&~p).sum()/max(1,(~v).sum()))
    return dict(balanced=(recall+silence)/2,voiced_correct=recall,
                silence_correct=silence,false_alarm=1-silence,
                miss=float((v&~p).sum()/max(1,v.sum())),
                overall=float((correct|(~v&~p)).mean()),
                octave_error=float((v&p&(np.abs(error-1200)<=50)).sum()/max(1,v.sum())),
                outside_range=float((v&((ref<65)|(ref>1100))).sum()/max(1,v.sum())))

def score(rows,config):
    singers={}; detail=[]
    for row in rows:
        d=np.load(OUT/'cache'/f"{row['track_id']}.npz")
        pred=predict(d,config)
        indices=np.rint(d['ref_time']/.01).astype(int)
        aligned=np.full(len(indices),np.nan)
        valid=(indices>=0)&(indices<len(pred))
        aligned[valid]=pred[indices[valid]]
        m=metrics(d['ref_hz'],aligned)
        singers.setdefault(row['singer_id'],[]).append(m)
        detail.append(dict(track=row['track_id'],singer=row['singer_id'],**m))
    # Equal tracks within singer, then equal singers.
    macro={k:float(np.mean([np.mean([r[k] for r in group]) for group in singers.values()])) for k in detail[0] if k not in ('track','singer')}
    return dict(macro=macro,tracks=detail)

def main():
    import librosa,soundfile as sf,torch
    from lab import track
    from rmvpe_adapter import PitchEstimator
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'cache').mkdir(exist_ok=True)
    rows=list(csv.DictReader((DATA/'vocadito_metadata.csv').open()))
    singers=sorted({r['singer_id'] for r in rows},key=lambda s:hashlib.sha256(('vocalpitch-v1:'+s).encode()).hexdigest())
    held=set(singers[:8])
    split=dict(development=[r for r in rows if r['singer_id'] not in held],test=[r for r in rows if r['singer_id'] in held])
    save(OUT/'split.json',split)
    save(OUT/'protocol.json',dict(objective='Equal singer macro mean of voiced <=50 cent detection accuracy and unvoiced recall',alignment='nearest 10ms prediction at reference times; missing coverage counts as unvoiced',search='CREPE thresholds .1/.21/.35/.5; RMVPE .01/.03/.1/.2/.4; median 1/3/5 frames; best individual candidates fused only within 50 cents, CREPE weights .25/.5/.75, each primary',range_hz=[65,1100],outside_range='Included in errors',rms_gate_dbfs=-55,test_singers=sorted(held)))
    device='cuda' if torch.cuda.is_available() else 'cpu'; engine=PitchEstimator(device)
    for i,row in enumerate(rows):
        tid=row['track_id']; dest=OUT/'cache'/f'{tid}.npz'
        if dest.exists():continue
        audio,sr=sf.read(DATA/'Audio'/f'vocadito_{tid}.wav',dtype='float32',always_2d=True)
        a=track(audio,sr,'full',device); b=engine.track(audio,sr)
        y=librosa.resample(audio.mean(axis=1),orig_sr=sr,target_sr=16000)
        rms=librosa.feature.rms(y=y,frame_length=1024,hop_length=160)[0]
        n=min(len(a[0]),len(b[0]),len(rms))
        ref=np.loadtxt(DATA/'Annotations/F0'/f'vocadito_{tid}_f0.csv',delimiter=',')
        np.savez_compressed(dest,crepe_raw=a[1][:n],crepe_score=a[3][:n],rmvpe_raw=b[1][:n],rmvpe_score=b[3][:n],rms=rms[:n],ref_time=ref[:,0],ref_hz=ref[:,1])
        print(f'Cached {i+1}/40: {tid}',flush=True)
    bases=dict(crepe=dict(model='crepe',threshold=.21,width=1),rmvpe=dict(model='rmvpe',threshold=.03,width=1))
    candidates=[]; best={}
    for model,thresholds in [('crepe',[.1,.21,.35,.5]),('rmvpe',[.01,.03,.1,.2,.4])]:
        group=[dict(model=model,threshold=t,width=w) for t in thresholds for w in [1,3,5]]
        scored=[dict(config=c,score=score(split['development'],c)['macro']) for c in group]
        candidates+=scored;best[model]=max(scored,key=lambda r:r['score']['balanced'])['config']
    for weight in [.25,.5,.75]:
        for primary in ['crepe','rmvpe']:
            c=dict(model='fusion',crepe=best['crepe'],rmvpe=best['rmvpe'],weight=weight,primary=primary)
            candidates.append(dict(config=c,score=score(split['development'],c)['macro']))
    chosen=max(candidates,key=lambda r:r['score']['balanced'])['config']
    save(OUT/'development-search.json',candidates)
    # Freeze before touching held-out scores; reruns reuse the frozen choice.
    frozen=OUT/'selected-config.json'
    if frozen.exists():
        assert json.loads(frozen.read_text(encoding='utf-8'))==chosen,'Frozen choice changed; create a new protocol version.'
    else:save(frozen,chosen)
    results={partition:{name:score(items,c) for name,c in dict(**bases,selected=chosen).items()} for partition,items in split.items()}
    save(OUT/'scores.json',results)
    print(json.dumps(dict(selected=chosen,test={k:v['macro'] for k,v in results['test'].items()}),indent=2),flush=True)

if __name__=='__main__':main()
