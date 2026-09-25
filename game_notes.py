"""GAME 1.0.3 ONNX note transcription, official decoding defaults."""
import json,hashlib
from pathlib import Path
import numpy as np

from app_paths import DATA_ROOT,MODEL_ROOT
ROOT=DATA_ROOT
VERSION='game-small-1.0.3-8steps-universal-v2'
REFINEMENT_VERSION='game-long-curve-reconcile-v4'
def gate_silent_notes(notes,audio,sr):
    y=audio.mean(axis=1) if audio.ndim==2 else audio
    result=[]
    for original in notes:
        a=max(0,int(round(original['start']*sr)));b=min(len(y),int(round(original['end']*sr)))
        if b<=a or float(np.mean(np.square(y[a:b],dtype=np.float64)))<=10**(-55/10):continue
        n=original.copy();n['note_id']=len(result)+1;result.append(n)
    return result
def refine_notes(notes,times,midi,trim='end'):
    result=[];hop=float(np.median(np.diff(times))) if len(times)>1 else .01
    for original in notes:
        n=original.copy();indices=np.where((times>=n['start'])&(times<n['end'])&np.isfinite(midi))[0]
        if len(indices)>=3:
            p=float(np.median(midi[indices]));key=int(round(p))
            n.update(midi=key,note=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][key%12]+str(key//12-1),center_hz=round(440*2**((p-69)/12),3),cents=round((p-key)*100,1))
            support=indices[np.abs(midi[indices]-p)<=.8]
            if len(support)>=3:
                end=float(times[support[-1]]+hop)
                if trim in ['end','both'] and n['end']-end>=.03:n['end']=round(end,4)
                start=float(times[support[0]])
                if trim=='both' and start-n['start']>=.03:n['start']=round(start,4)
        n['duration']=round(n['end']-n['start'],4);n['note_id']=len(result)+1;result.append(n)
    return result
def cache_path(song,version=VERSION):
    p=Path(song['audio']['vocals']);s=p.stat()
    digest=hashlib.sha256(f'{p.resolve()}|{s.st_size}|{s.st_mtime_ns}|{version}'.encode()).hexdigest()[:20]
    return ROOT/'results/game-notes'/(digest+'.json')

def refine_supported_notes(notes,times,midi,trim='end',allow_motion=True):
    """Retain GAME pitch with sustained or locally returning pitch support.

    This is evidence for an existing event, not a minimum note duration or a
    highest-pitch detector. Preserve the existing median-based tail boundaries.
    """
    result=refine_notes(notes,times,midi,trim)
    hop=float(np.median(np.diff(times))) if len(times)>1 else .01
    for original,n in zip(notes,result):
        if original['midi']==n['midi']:continue
        indices=np.flatnonzero((times>=original['start'])&(times<original['end'])&np.isfinite(midi)&(np.abs(midi-original['midi'])<=.5))
        if not len(indices):continue
        # Do not concatenate support across NaNs, off-pitch frames or time gaps.
        cuts=np.flatnonzero((np.diff(indices)>1)|(np.diff(times[indices])>hop*1.5))+1
        runs=np.split(indices,cuts)
        supported=any(times[r[-1]]-times[r[0]]+hop>=.06-1e-8 for r in runs)
        if not supported and allow_motion:
            # Join two near-pitch visits only across a short, voiced excursion.
            # Never bridge silence, a timestamp gap, or a distant pitch jump.
            groups=[];group=runs[0].copy()
            for run in runs[1:]:
                gap=np.arange(group[-1]+1,run[0]);segment=np.arange(group[-1],run[0]+1)
                bridge=(len(gap)*hop<=.03+1e-8 and
                        np.all(np.isfinite(midi[gap])) and
                        np.all(np.abs(midi[gap]-original['midi'])<=.9) and
                        np.all(np.diff(times[segment])<=hop*1.5))
                if bridge:group=np.r_[group,run]
                else:groups.append(group);group=run.copy()
            groups.append(group)
            supported=any(len(g)*hop>=.05-1e-8 and
                          times[g[-1]]-times[g[0]]+hop>=.06-1e-8
                          for g in groups)
        if supported:
            for key in ['midi','note','center_hz','cents']:n[key]=original[key]
    return result

def refine_event_notes(notes,times,midi,trim='end'):
    """Trust short GAME events unless dense, consistent contrary evidence exists.

    Long events and large/ octave conflicts retain the previous policy.
    Tail boundaries are unchanged to isolate the pitch decision.
    """
    result=refine_supported_notes(notes,times,midi,trim)
    for original,n in zip(notes,result):
        if original['end']-original['start']>.5+1e-8:continue
        if n['midi']==original['midi'] or abs(n['midi']-original['midi'])>=6:continue
        x=midi[(times>=original['start'])&(times<original['end'])]
        v=x[np.isfinite(x)]
        contrary=(len(v)>=12 and len(v)>=.8*len(x) and
                  np.mean(np.abs(v-n['midi'])<=.5)>=.9 and
                  not np.any(np.abs(v-original['midi'])<=.75))
        if not contrary:
            for key in ['midi','note','center_hz','cents']:n[key]=original[key]
    return result

def reconcile_notes(notes,times,midi,reliability=None):
    """Reconcile sustained curve evidence, preserving short GAME events.

    Split only long conflicting events; fill only stable uncovered intervals.
    Source tags distinguish curve-derived events from model predictions.
    """
    from main_notes import extract
    result=refine_event_notes(notes,times,midi)
    if len(times)<2:return result
    times=np.asarray(times);midi=np.asarray(midi);hop=float(np.median(np.diff(times)))
    settings=dict(median_frames=5,change_hold_seconds=.18,min_note_seconds=.30,
                  same_note_gap_seconds=0.,hysteresis_semitones=.8,refine_boundary=True)
    candidates=extract(times,midi,settings=settings)
    def stable(a,b,key):
        indices=(times>=a)&(times<b);x=midi[indices];v=x[np.isfinite(x)]
        return (b-a>=.30-1e-8 and len(v)>=.9*max(1,len(x)) and
                np.mean(np.abs(v-key)<=.75)>=.80 and
                (reliability is None or np.mean(np.asarray(reliability)[indices])>=.7))
    fixed=[]
    for original,n in zip(notes,result):
        if original['end']-original['start']<.8:
            fixed.append(n);continue
        pieces=[]
        for c in candidates:
            a=max(original['start'],c['start']);b=min(original['end'],c['end'])
            if b>a and stable(a,b,c['midi']):
                p=c.copy();p.update(start=a,end=b,duration=round(b-a,4),status='curve_split');pieces.append(p)
        conflict=any(p['duration']>=.35 and abs(p['midi']-n['midi'])>=1.5 for p in pieces)
        coverage=sum(p['duration'] for p in pieces)/(original['end']-original['start'])
        if conflict and coverage>=.75:fixed.extend(pieces)
        else:fixed.append(n)
    fixed.sort(key=lambda n:n['start'])
    # Subtract every existing event before filling, including protected shorts.
    additions=[]
    for c in candidates:
        gaps=[(c['start'],c['end'])]
        for n in fixed:
            if n['end']<=c['start']:continue
            if n['start']>=c['end']:break
            next_gaps=[]
            for a,b in gaps:
                if n['end']<=a or n['start']>=b:next_gaps.append((a,b));continue
                if a<n['start']:next_gaps.append((a,n['start']))
                if n['end']<b:next_gaps.append((n['end'],b))
            gaps=next_gaps
        for a,b in gaps:
            if b-a>=.35 and stable(a,b,c['midi']):
                p=c.copy();p.update(start=a,end=b,duration=round(b-a,4),status='curve_fill');additions.append(p)
    result=sorted(fixed+additions,key=lambda n:n['start'])
    for i,n in enumerate(result):n['note_id']=i+1
    return result

class GameNotes:
    def __init__(self):
        import onnxruntime as ort
        self.path=MODEL_ROOT/'game-small/GAME-1.0.3-small-onnx'
        self.config=json.loads((self.path/'config.json').read_text())
        options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
        self.sessions={k:ort.InferenceSession(str(self.path/(k+'.onnx')),sess_options=options,providers=['CPUExecutionProvider']) for k in ['encoder','segmenter','estimator','bd2dur']}
    def segment(self,y):
        duration=len(y)/self.config['samplerate']
        x_seg,x_est,mask=self.sessions['encoder'].run(None,dict(waveform=y[None].astype(np.float32),duration=np.array([duration],np.float32)))
        known=np.zeros_like(mask);boundaries=known.copy()
        for t in np.arange(8)/8:
            boundaries,=self.sessions['segmenter'].run(None,dict(x_seg=x_seg,language=np.array([0],np.int64),known_boundaries=known,prev_boundaries=boundaries,t=np.array([t],np.float32),maskT=mask,threshold=np.array(.2,np.float32),radius=np.array(2,np.int64)))
        durations,maskN=self.sessions['bd2dur'].run(None,dict(boundaries=boundaries,maskT=mask))
        presence,scores=self.sessions['estimator'].run(None,dict(x_est=x_est,boundaries=boundaries,maskT=mask,maskN=maskN,threshold=np.array(.2,np.float32)))
        result=[];position=0.
        for d,pitch,voiced,valid in zip(durations[0],scores[0],presence[0],maskN[0]):
            if not valid:break
            end=min(duration,position+float(d))
            if voiced and np.isfinite(pitch) and end>position:
                result.append((position,end,float(pitch)))
            position+=float(d)
        return result
    def transcribe(self,audio,sr):
        import librosa
        y=audio.mean(axis=1) if audio.ndim==2 else audio
        target=self.config['samplerate'];y=librosa.resample(y,orig_sr=sr,target_sr=target).astype(np.float32)
        # Bounded 20 s cores with 2 s context, ownership by interval midpoint.
        # Small reference clips run in one pass; no grid rounding of note pitch.
        total=len(y)/target;events=[]
        for start in np.arange(0,total,20.):
            end=min(total,start+20);left=max(0,start-2);right=min(total,end+2)
            for a,b,p in self.segment(y[round(left*target):round(right*target)]):
                a+=left;b+=left
                if start<=(a+b)/2<end:events.append((a,b,p))
        events.sort();result=[]
        for a,b,p in events:
            # Trim overlap from contextual chunk edge disagreements.
            if result:a=max(a,result[-1]['end'])
            if b-a<.01:continue
            key=int(round(p));name=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][key%12]+str(key//12-1)
            result.append(dict(start=round(a,4),end=round(b,4),duration=round(b-a,4),midi=key,note=name,center_hz=round(440*2**((p-69)/12),3),cents=round((p-key)*100,1),status='GAME',note_id=len(result)+1))
        return gate_silent_notes(result,y,target)
