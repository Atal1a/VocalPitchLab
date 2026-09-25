"""Stable display sampling and a bounded, audio-corrected presentation clock."""
import math
from functools import lru_cache
import numpy as np

def lod_stride(span,pixels,frame_seconds):
    ratio=max(1,span/max(1,pixels)/max(frame_seconds,1e-6)/2)
    return 2**max(0,math.floor(math.log2(ratio)))

def stable_envelope(times,values,stride):
    """Buckets are anchored to the recording, never the moving viewport.

    Preserve min/max and finite-run endpoints, including even one-frame gaps.
    Returned timestamps stay sorted and are never synthesized or shifted.
    """
    if stride<=1:return times,values
    finite=np.isfinite(values);changes=np.diff(np.r_[False,finite,False].astype(int))
    indices=[]
    for start,end in zip(np.flatnonzero(changes==1),np.flatnonzero(changes==-1)):
        if start:indices.append(start-1)
        indices.append(start)
        for a in range((start//stride)*stride,end,stride):
            lo=max(start,a);hi=min(end,a+stride);chunk=values[lo:hi]
            indices.extend(sorted({lo+int(np.argmin(chunk)),lo+int(np.argmax(chunk))}))
        indices.append(end-1)
        if end<len(values):indices.append(end)
    indices=np.array(sorted(set(indices)),dtype=int)
    return times[indices],values[indices]


def melody_outline(times,values,stride):
    """Whole-song median buckets for overview; retain every voiced gap."""
    if stride<=1:return times,values
    edges=np.diff(np.r_[False,np.isfinite(values),False].astype(int));points=[]
    for start,end in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
        if start:points.append((times[start-1],np.nan))
        points.append((times[start],values[start]))
        for a in range(start//stride*stride,end,stride):
            lo=max(start,a);hi=min(end,a+stride)
            mid=(lo+hi-1)//2
            if start<mid<end-1:points.append((times[mid],float(np.median(values[lo:hi]))))
        if end-1>start:points.append((times[end-1],values[end-1]))
        if end<len(values):points.append((times[end],np.nan))
    if not points:return np.array([]),np.array([])
    pairs=np.array(points);unique=np.r_[True,np.diff(pairs[:,0])>0]
    return pairs[unique,0],pairs[unique,1]


@lru_cache(maxsize=16)
def vocal_gain(original,vocals):
    """Conservative RMS match, only over audible vocal blocks; at most +6dB."""
    import soundfile as sf
    with sf.SoundFile(original) as a,sf.SoundFile(vocals) as b:
        if a.samplerate!=b.samplerate:return 1.
        energies=[];peak=0.
        while True:
            x=a.read(a.samplerate//10,dtype='float32',always_2d=True);y=b.read(b.samplerate//10,dtype='float32',always_2d=True)
            if not len(x) or not len(y):break
            yr=float(np.sqrt(np.mean(y*y)));peak=max(peak,float(np.max(abs(y))))
            if yr>.01:energies.append((float(np.mean(x*x)),yr*yr))
    if not energies:return 1.
    e=np.array(energies);ratio=np.sqrt(e[:,0].mean()/e[:,1].mean())
    return float(np.clip(min(ratio,.95/max(peak,.001)),1,2))

class PresentationClock:
    """Interpolate short notification gaps without running ahead indefinitely.

    Small corrections change speed, not position. Explicit seeks reset instantly.
    This is a media-clock interpolation, not an assumed hardware-latency offset.
    """
    def __init__(self):self.reset(0,0)
    def reset(self,position,now):self.anchor=position;self.wall=now;self.rate=1.;self.filtered_error=0.
    def value(self,now):return self.anchor+min(1.,max(0,now-self.wall))*self.rate
    def feed(self,position,now):
        current=self.value(now);error=position-current
        if abs(error)>.5:self.reset(position,now)
        else:
            self.filtered_error=.9*self.filtered_error+.1*error
            correction=0. if abs(self.filtered_error)<.01 else self.filtered_error
            self.anchor=current;self.wall=now;self.rate=1+float(np.clip(correction/3,-.015,.015))
        return self.anchor


def vocal_loudness(path,cache_folder):
    """25 ms vocal RMS for display only; independent of playback volume/source.

    Whole-song reference and 125 ms smoothing avoid per-view renormalizing.
    Missing/corrupt audio falls back to a neutral visible line at the caller.
    """
    import hashlib
    from pathlib import Path
    import soundfile as sf
    path=Path(path);stat=path.stat()
    key=hashlib.sha256(f'{path}:{stat.st_size}:{stat.st_mtime_ns}:v2'.encode()).hexdigest()
    folder=Path(cache_folder);folder.mkdir(parents=True,exist_ok=True);cache=folder/(key+'.npz')
    if cache.exists():
        with np.load(cache) as d:return d['time'],d['level']
    info=sf.info(path);hop=max(1,round(info.samplerate*.025))
    rms=np.array([np.sqrt(np.mean(block.astype(np.float64)**2)) for block in sf.blocks(path,blocksize=hop,always_2d=True,dtype='float32')])
    db=20*np.log10(np.maximum(rms,1e-8))
    audible=db[db>-50]
    if len(audible):
        lower,upper=np.percentile(audible,[20,95]);lower=min(lower,upper-12)
    else:lower,upper=-48,-12
    level=np.clip((db-lower)/(upper-lower),0,1)
    level=np.convolve(np.pad(level,(2,2),mode='edge'),np.ones(5)/5,mode='valid')
    times=(np.arange(len(level))+.5)*hop/info.samplerate
    np.savez_compressed(cache,time=times,level=level)
    return times,level
