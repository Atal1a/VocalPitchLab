"""GAME 1.0.3 ONNX note transcription, official decoding defaults."""
import json,hashlib
from pathlib import Path
import numpy as np

from app_paths import DATA_ROOT,MODEL_ROOT
ROOT=DATA_ROOT
GAME_SEED=7301
VERSION='game-small-1.0.3-8steps-universal-v3-seed7301'
REFINEMENT_VERSION='game-local-evidence-v7'
RECONCILE_SETTINGS=dict(stable_seconds=.30,fill_seconds=.35,conflict_seconds=.35,
                       valid_fraction=.90,pitch_fraction=.80,pitch_radius=.75,
                       evidence_fraction=.70,conflict_semitones=1.5,octave_boundary=10.,
                       short_support_seconds=.07,short_bridge_seconds=.03,short_max_seconds=.5)

def correct_leading_pitch(notes,times,midi,reliability):
    """Split an early target label only after a supported, continuous ascent.

    This deliberately excludes instantaneous octave flips and changes inside
    a note whose opening already agrees with GAME.
    """
    if reliability is None or len(times)<3:return [n.copy() for n in notes]
    times=np.asarray(times);midi=np.asarray(midi);evidence=np.asarray(reliability)
    if evidence.shape!=midi.shape:raise ValueError('Evidence timeline mismatch')
    hop=float(np.median(np.diff(times)));result=[]
    width=max(1,round(.25/hop));hold=max(1,round(.30/hop))
    for original in notes:
        n=original.copy();result.append(n)
        if n['end']-n['start']<1.:continue
        ix=np.flatnonzero((times>=n['start'])&(times<n['end']))
        if len(ix)<width+hold:continue
        t=times[ix];x=midi[ix];ev=evidence[ix]
        if not np.all(np.isfinite(x[:width])) or np.mean(ev[:width]>=.7)<.9:continue
        center=float(np.median(x[:width]));key=int(round(center));target=n['midi']
        # Opening must already carry another pitch, not an attack sliding up.
        if not 2<=target-key<=14 or np.mean(abs(x[:width]-key)<=.85)<.8:continue
        limit=np.searchsorted(t,n['start']+1.2)
        arrival=None
        for j in range(width,min(limit,len(x)-hold+1)):
            if abs(x[j]-target)>.75:continue
            z=x[j:j+hold]
            if (np.all(np.isfinite(z)) and np.mean(abs(z-target)<=.85)>=.9 and
                    abs(np.median(z)-target)<=.6 and np.mean(ev[j:j+hold]>=.7)>=.9):
                arrival=j;break
        if arrival is None:continue
        segment=x[:arrival+hold]
        if (not np.all(np.isfinite(segment)) or np.any(np.diff(t[:arrival+hold])>hop*1.5)
                or np.mean(ev[:arrival+hold]>=.7)<.9):continue
        # Find sustained departure, allowing a small rounded turn in the low note.
        departure=None;leaving=max(1,round(.06/hop))
        for j in range(width,arrival):
            if np.all(x[j:j+leaving]>key+.85):departure=j;break
        if departure is None or t[departure]-t[0]<.25:continue
        bridge=x[max(0,departure-1):arrival+1]
        middle=bridge[(bridge>key+1)&(bridge<target-1)]
        if target-key>=6:
            if len(middle)*hop<.04-1e-8 or len(np.unique(np.floor(middle)))<3:continue
        if (np.any(abs(np.diff(bridge))>3.5) or np.any(np.diff(bridge)<-.75)
                or t[arrival]-t[departure]>.45):continue
        prefix=n.copy();prefix.update(start=float(t[0]),end=float(t[departure]),midi=key,
            note=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][key%12]+str(key//12-1),
            center_hz=round(440*2**((center-69)/12),3),cents=round((center-key)*100,1),
            status='curve_onset_prefix',duration=round(float(t[departure]-t[0]),4))
        origin=dict(start=original['start'],end=original['end'],midi=original['midi'])
        prefix['onset_source']=origin
        n.update(start=float(t[arrival]),duration=round(float(n['end']-t[arrival]),4),status='curve_onset_target',onset_source=origin)
        result[-1:]=[prefix,n]
    return result
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
    if song.get('game_notes') and song.get('game_notes_version')==version:return Path(song['game_notes'])
    p=Path(song['audio']['vocals']);s=p.stat()
    digest=hashlib.sha256(f'{p.resolve()}|{s.st_size}|{s.st_mtime_ns}|{version}'.encode()).hexdigest()[:20]
    return ROOT/'results/game-notes'/(digest+'.json')

def display_cache_path(song):
    """Keep existing analyses readable without relabeling them as seeded."""
    if song.get('game_notes') and Path(song['game_notes']).is_file():return Path(song['game_notes'])
    for version in [VERSION,'game-small-1.0.3-8steps-universal-v2','game-small-1.0.3-8steps-universal-v1']:
        path=cache_path(song,version)
        if path.is_file():return path
    return cache_path(song)

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

def vibrato_regions(times,midi,reliability):
    """Repeated narrow, rounded oscillations; preserve silence and note steps."""
    from scipy.signal import find_peaks
    from scipy.ndimage import median_filter
    if reliability is None or len(times)<4:return []
    times=np.asarray(times);midi=np.asarray(midi)
    hop=float(np.median(np.diff(times)))
    valid=np.isfinite(midi)&(np.asarray(reliability)>=RECONCILE_SETTINGS['evidence_fraction'])
    indices=np.flatnonzero(valid)
    if not len(indices):return []
    runs=np.split(indices,np.flatnonzero((np.diff(indices)>1)|(np.diff(times[indices])>hop*1.5))+1)
    regions=[]
    for run in runs:
        x=median_filter(midi[run],size=3,mode='nearest')
        peaks,_=find_peaks(x,prominence=.5,distance=max(1,round(.10/hop)))
        group=[]
        def flush():
            if len(group)<3:return
            a,b=group[0][0],group[-1][1]
            center=float(np.median([c[2] for c in group]));key=int(round(center))
            regions.append(dict(start=float(times[run[a]]),end=float(times[run[b]]+hop),
                duration=float(times[run[b]]-times[run[a]]+hop),midi=key,
                note=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][key%12]+str(key//12-1),
                center_hz=round(440*2**((center-69)/12),3),cents=round((center-key)*100,1),status='curve_vibrato'))
        for a,b in zip(peaks,peaks[1:]):
            y=x[a:b+1];low=float(np.min(y));high=float((x[a]+x[b])/2)
            width=high-low;period=times[run[b]]-times[run[a]];center=(high+low)/2
            # Long flat extrema suggest separate alternating notes, not vibrato.
            rounded=np.mean((y<=low+.15*width)|(y>=high-.15*width))<.68
            ok=(.11<=period<=.29 and .6<=width<=3. and abs(x[a]-x[b])<=.7 and rounded)
            consistent=not group or (abs(center-np.median([c[2] for c in group]))<=.45 and
                max(period,group[-1][3])/min(period,group[-1][3])<=1.5)
            if not ok or not consistent:
                flush();group=[]
            if ok:group.append((a,b,center,period))
        flush()
    return regions


def motion_candidates(times,midi,reliability,oscillations=None):
    """Short supported turns, never crossings of an unvoiced gap."""
    from scipy.signal import find_peaks
    from scipy.ndimage import median_filter
    cfg=RECONCILE_SETTINGS
    if len(times)<3 or reliability is None:return []
    hop=float(np.median(np.diff(times)));evidence=np.asarray(reliability)
    valid=np.isfinite(midi)&(evidence>=cfg['evidence_fraction'])
    # A discontinuity in the timestamp axis also breaks a run.
    runs=[];start=None
    for i,ok in enumerate(valid):
        if start is not None and (not ok or (i and times[i]-times[i-1]>hop*1.5)):
            runs.append((start,i));start=None
        if ok and start is None:start=i
    if start is not None:runs.append((start,len(times)))
    oscillations=vibrato_regions(times,midi,reliability) if oscillations is None else oscillations
    result=[]
    for lo,hi in runs:
        if hi-lo<7:continue
        values=midi[lo:hi];smooth=median_filter(values,size=3,mode='nearest')
        for direction in (1,-1):
            peaks,properties=find_peaks(direction*smooth,prominence=cfg['conflict_semitones'])
            for j,peak in enumerate(peaks):
                if properties['prominences'][j]>=cfg['octave_boundary']:continue
                key=int(round(smooth[peak]));left=peak;right=peak+1
                # Grow only around this turning point, not distant visits.
                while left>0 and abs(values[left-1]-key)<=.9 and (peak-left+1)*hop<=cfg['short_max_seconds']:left-=1
                while right<len(values) and abs(values[right]-key)<=.9 and (right-peak)*hop<=cfg['short_max_seconds']:right+=1
                support=np.flatnonzero(np.abs(values[left:right]-key)<=.5)+left
                if not len(support):continue
                cuts=np.flatnonzero((np.diff(support)-1)*hop>cfg['short_bridge_seconds']+1e-8)+1
                groups=np.split(support,cuts)
                group=min(groups,key=lambda g:np.min(np.abs(g-peak)))
                a=lo+int(group[0]);b=lo+int(group[-1])+1
                if any(v['start']<=times[lo+peak]<v['end'] for v in oscillations):continue
                duration=float(times[b-1]+hop-times[a])
                if len(group)*hop<cfg['short_support_seconds']-1e-8 or duration>cfg['short_max_seconds']:continue
                # Require a return on both sides; normal vibrato below 1.5 st
                # and one-frame spikes never become candidates.
                lb=int(properties['left_bases'][j]);rb=int(properties['right_bases'][j])
                if min(direction*(smooth[peak]-smooth[lb]),direction*(smooth[peak]-smooth[rb]))<cfg['conflict_semitones']:continue
                result.append(dict(start=float(times[a]),end=float(times[b-1]+hop),duration=duration,
                                   midi=key,note=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][key%12]+str(key//12-1),
                                   center_hz=round(440*2**((key-69)/12),3),cents=0.,status='curve_turn'))
    return sorted(result,key=lambda n:(n['start'],-n['duration']))


def reconcile_notes(notes,times,midi,reliability=None):
    """Local sustained reconciliation plus evidence-backed short turns.

    Raw notes and the pitch curve remain immutable. Large/octave disagreements
    retain the former policy; protected model shorts take priority over fills.
    """
    from main_notes import extract
    result=refine_event_notes(notes,times,midi)
    if len(times)<2:return result
    times=np.asarray(times);midi=np.asarray(midi);cfg=RECONCILE_SETTINGS
    hop=float(np.median(np.diff(times)))
    if reliability is not None and len(reliability)!=len(times):raise ValueError('Evidence timeline mismatch')
    settings=dict(median_frames=5,change_hold_seconds=.18,min_note_seconds=cfg['stable_seconds'],
                  same_note_gap_seconds=0.,hysteresis_semitones=.8,refine_boundary=True)
    candidates=extract(times,midi,settings=settings)
    def stable(a,b,key):
        indices=(times>=a)&(times<b);x=midi[indices];v=x[np.isfinite(x)];t=times[indices]
        return (b-a>=cfg['stable_seconds']-1e-8 and len(v)>0 and
                len(v)>=cfg['valid_fraction']*max(1,len(x)) and
                (len(t)<2 or np.all(np.diff(t)<=hop*1.5)) and
                np.mean(np.abs(v-key)<=cfg['pitch_radius'])>=cfg['pitch_fraction'] and
                reliability is not None and np.mean(np.asarray(reliability)[indices])>=cfg['evidence_fraction'])
    def part(n,a,b,status=None):
        p=n.copy();p.update(start=float(a),end=float(b),duration=round(b-a,4))
        if status:p['status']=status
        return p
    def subtract(a,b,events):
        gaps=[(a,b)]
        for n in events:
            remaining=[]
            for lo,hi in gaps:
                if n['end']<=lo or n['start']>=hi:remaining.append((lo,hi));continue
                if lo<n['start']:remaining.append((lo,n['start']))
                if n['end']<hi:remaining.append((n['end'],hi))
            gaps=remaining
        return gaps
    fixed=[]
    onset_events=correct_leading_pitch(notes,times,midi,reliability)
    onset_by_start={}
    for item in onset_events:
        if 'onset_source' in item:
            origin=item['onset_source'];onset_by_start.setdefault((origin['start'],origin['end']),[]).append(item)
    for original,n in zip(notes,result):
        corrected=onset_by_start.get((original['start'],original['end']))
        if corrected:
            fixed.extend(corrected);continue
        if original['end']-original['start']<.8:
            fixed.append(n);continue
        replacements=[]
        for c in candidates:
            a=max(original['start'],c['start']);b=min(original['end'],c['end'])
            difference=abs(c['midi']-n['midi'])
            if (b-a>=cfg['conflict_seconds'] and cfg['conflict_semitones']<=difference<cfg['octave_boundary']
                    and stable(a,b,c['midi'])):
                replacements.append(part(c,a,b,'curve_split'))
        # Preserve all unmatched portions instead of requiring 75% coverage.
        left,right=(original['start'],original['end']) if replacements else (n['start'],n['end'])
        fixed.extend(part(n,a,b) for a,b in subtract(left,right,replacements) if b>a)
        fixed.extend(replacements)
    fixed.sort(key=lambda n:n['start'])
    for c in candidates:
        for a,b in subtract(c['start'],c['end'],fixed):
            if b-a>=cfg['fill_seconds'] and stable(a,b,c['midi']):fixed.append(part(c,a,b,'curve_fill'))
        fixed.sort(key=lambda n:n['start'])
    oscillations=vibrato_regions(times,midi,reliability)
    for c in oscillations:
        for a,b in subtract(c['start'],c['end'],fixed):
            if b-a>=cfg['fill_seconds']:fixed.append(part(c,a,b))
        fixed.sort(key=lambda n:n['start'])
    protected=[n for n in notes if n['end']-n['start']<=cfg['short_max_seconds']]
    for c in motion_candidates(times,midi,reliability,oscillations):
        a,b=c['start'],c['end']
        if any(n['start']<b and n['end']>a for n in protected):continue
        overlap=[n for n in fixed if n['start']<b and n['end']>a]
        if any(abs(n['midi']-c['midi'])<cfg['conflict_semitones'] or
               abs(n['midi']-c['midi'])>=cfg['octave_boundary'] or n.get('status')=='curve_turn' for n in overlap):continue
        updated=[]
        for n in fixed:
            updated.extend(part(n,lo,hi) for lo,hi in subtract(n['start'],n['end'],[c]) if hi>lo)
        fixed=sorted(updated+[c],key=lambda n:n['start'])
    for i,n in enumerate(fixed):n['note_id']=i+1
    return fixed

class GameNotes:
    def __init__(self,allow_spinning=False,threads=4):
        import onnxruntime as ort
        self._session_options=(allow_spinning,threads);self._transcribed=False
        # Fresh sessions per transcription start the ONNX random operators
        # from the same seed; session reuse would advance their random state.
        ort.set_seed(GAME_SEED)
        self.path=MODEL_ROOT/'game-small/GAME-1.0.3-small-onnx'
        self.config=json.loads((self.path/'config.json').read_text())
        options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
        # Four sessions execute sequentially. Sleeping idle pools avoids CPU
        # competition between encoder, segmenter, duration and pitch heads.
        options.add_session_config_entry('session.intra_op.allow_spinning','1' if allow_spinning else '0')
        options.add_session_config_entry('session.inter_op.allow_spinning','1' if allow_spinning else '0')
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
    def transcribe(self,audio,sr,cancel_event=None):
        import librosa
        if self._transcribed:self.__init__(*self._session_options)
        self._transcribed=True
        y=audio.mean(axis=1) if audio.ndim==2 else audio
        target=self.config['samplerate'];y=librosa.resample(y,orig_sr=sr,target_sr=target).astype(np.float32)
        # Bounded 20 s cores with 2 s context, ownership by interval midpoint.
        # Small reference clips run in one pass; no grid rounding of note pitch.
        total=len(y)/target;events=[]
        for start in np.arange(0,total,20.):
            if cancel_event is not None and cancel_event.is_set():raise RuntimeError('Note preparation cancelled')
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
