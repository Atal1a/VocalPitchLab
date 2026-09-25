"""Stable main-note regions with optional audio-supported re-articulation."""
import csv,json
from pathlib import Path
import numpy as np
from scipy.ndimage import median_filter

SETTINGS=dict(version=1,median_frames=5,change_hold_seconds=.08,min_note_seconds=.10,
              same_note_gap_seconds=.03,hysteresis_semitones=.65)
CONFIG_PATH=Path(__file__).resolve().parent/'note-settings.json'

def current_settings():
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8')) if CONFIG_PATH.exists() else SETTINGS.copy()

def audio_onsets(audio,sr,prominence_db=9):
    """Conservative re-articulation candidates from energy valleys, not beats."""
    import librosa
    from scipy.signal import find_peaks
    y=audio.mean(axis=1) if audio.ndim==2 else audio
    y=librosa.resample(y,orig_sr=sr,target_sr=16000)
    rms=librosa.feature.rms(y=y,frame_length=400,hop_length=160)[0]
    db=median_filter(20*np.log10(np.maximum(rms,1e-7)),size=3,mode='nearest')
    valleys,_=find_peaks(-db,prominence=prominence_db,distance=15)
    events=[]
    for p in valleys:
        left=db[max(0,p-12):p];right=db[p+1:p+13]
        if not len(left) or not len(right):continue
        if min(float(left.max()),float(right.max()))-db[p]<prominence_db:continue
        if right.max()<-50:continue
        recovery=np.where(right>=db[p]+prominence_db*.5)[0]
        if len(recovery):events.append((p+1+int(recovery[0]))*.01)
    return np.array(events)

def extract(times,midi,settings=None,onset_times=None):
    settings=current_settings() if settings is None else settings
    times=np.asarray(times);midi=np.asarray(midi)
    if len(times)<2:return []
    hop=float(np.median(np.diff(times)))
    if not np.allclose(np.diff(times),hop,atol=1e-5):raise ValueError('Uniform frame grid required')
    finite=np.isfinite(midi);edges=np.diff(np.r_[False,finite,False].astype(int));regions=[]
    hold=max(1,int(np.ceil(settings['change_hold_seconds']/hop-1e-7)))
    for a,b in zip(np.where(edges==1)[0],np.where(edges==-1)[0]):
        values=median_filter(midi[a:b],size=settings['median_frames'],mode='nearest')
        current=int(np.rint(values[0]));start=a;pending=None;count=0
        for local,value in enumerate(values):
            i=a+local;target=int(np.rint(value))
            if target!=current and abs(value-current)>settings['hysteresis_semitones']:
                if target==pending:count+=1
                else:pending=target;count=1
                if count>=hold:
                    boundary=i-count+1
                    # A sustained change confirms the note; optionally move its
                    # boundary back to the midpoint crossing, rather than the
                    # later hysteresis crossing. Never cross an earlier note.
                    if settings.get('refine_boundary',False):
                        middle=(current+target)/2;direction=1 if target>current else -1
                        floor=max(start+1,boundary-int(round(.08/hop)))
                        while boundary>floor and direction*(values[boundary-a-1]-middle)>=0:
                            boundary-=1
                    regions.append([start,boundary,current])
                    start=boundary;current=target;pending=None;count=0
            else:pending=None;count=0
        regions.append([start,b,current])
    # Merge only equal pitches across tiny missing-frame gaps, never long breaths.
    merged=[]
    for a,b,key in regions:
        if merged and key==merged[-1][2] and (a-merged[-1][1])*hop<=settings['same_note_gap_seconds']+1e-6:
            merged[-1][1]=b
        else:merged.append([a,b,key])
    if onset_times is not None:
        split=[];minimum=int(np.ceil(settings['min_note_seconds']/hop-1e-7))
        candidates=np.searchsorted(times,onset_times)
        for a,b,key in merged:
            start=a
            for cut in candidates[(candidates>=a+minimum)&(candidates<=b-minimum)]:
                if cut-start<minimum:continue
                before=midi[max(a,cut-8):cut];after=midi[cut:min(b,cut+8)]
                # Require stable same-pitch evidence on both sides; do not split
                # a glide solely because its energy changes.
                if np.isfinite(before).sum()<4 or np.isfinite(after).sum()<4:continue
                if abs(float(np.nanmedian(before))-key)>.5 or abs(float(np.nanmedian(after))-key)>.5:continue
                split.append([start,int(cut),key]);start=int(cut)
            split.append([start,b,key])
        merged=split
    result=[];names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    for region_index,(a,b,key) in enumerate(merged):
        duration=(b-a)*hop
        values=midi[a:b];values=values[np.isfinite(values)]
        if not len(values):continue
        center=float(np.median(values));spread=float(np.percentile(values,90)-np.percentile(values,10))
        if duration<settings['min_note_seconds']-1e-6:
            short=settings.get('short_notes')
            if not short or duration<short['min_seconds']-1e-6:continue
            # Judge the ORIGINAL contour, not the median-smoothed contour.
            stable=(len(values)/(b-a)>=.9 and spread<=short['spread_semitones'] and abs(center-key)<=.3)
            onset=onset_times is not None and np.any(np.abs(np.asarray(onset_times)-times[a])<=.04+1e-6)
            neighbors=[]
            for neighbor in [region_index-1,region_index+1]:
                if 0<=neighbor<len(merged):
                    x,y,k=merged[neighbor];gap=max(a-y,x-b,0)*hop
                    neighbors.append((y-x)*hop>=.1-1e-6 and gap<=.03+1e-6 and 0<abs(k-key)<=5)
            # A short octave spike must not be restored by context alone.
            context=len(neighbors)==2 and all(neighbors)
            if not stable or not (onset or context):continue
        flags=[]
        if duration<.15:flags.append('短音')
        if spread>1:flags.append('音高变化较大')
        if abs(center-key)>.35:flags.append('接近音名边界')
        result.append(dict(start=round(float(times[a]),4),end=round(float(times[b-1]+hop),4),
            duration=round(duration,4),midi=key,note=names[key%12]+str(key//12-1),
            center_hz=round(float(440*2**((center-69)/12)),3),cents=round((center-key)*100,1),
            status=' / '.join(flags) if flags else '常规',note_id=len(result)+1))
    return result

def export_notes(path,notes):
    fields=['note_id','start','end','duration','note','midi','center_hz','cents','status']
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(notes)

def main():
    from lab import ROOT
    from rmvpe_batch import read_pitch
    index_path=sorted((ROOT/'results').glob('rmvpe-*/index.json'))[-1]
    index=json.loads(index_path.read_text(encoding='utf-8'))
    for song in index['songs']:
        source='tuned_vocals' if 'tuned_vocals' in song['curves'] else 'rmvpe_vocals'
        onsets=None;settings=current_settings()
        if settings.get('onset_prominence_db'):
            import soundfile as sf
            audio,sr=sf.read(song['audio']['vocals'],dtype='float32',always_2d=True)
            onsets=audio_onsets(audio,sr,settings['onset_prominence_db'])
        notes=extract(*read_pitch(song['curves'][source]),onset_times=onsets)
        path=index_path.parent/(song['name']+'-main-notes.json')
        path.write_text(json.dumps(dict(settings=current_settings(),source=source,notes=notes),ensure_ascii=False,indent=2),encoding='utf-8')
        export_notes(path.with_suffix('.csv'),notes);song['main_notes']=str(path)
        print(song['name'],len(notes),'main notes')
    temp=index_path.with_suffix('.tmp');temp.write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(index_path)

if __name__=='__main__':main()
