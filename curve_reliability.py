"""Experimental voicing decisions, never average or replace pitch values."""
import numpy as np
from scipy.ndimage import median_filter

VERSION='curve-reliability-pilot-v1'

def display_weight(midi,crepe_score,rmvpe_score):
    """Conservative visual emphasis; no pitch samples are removed."""
    from scipy.ndimage import gaussian_filter1d
    keep=mask(midi,crepe_score,rmvpe_score,'hysteresis')
    return gaussian_filter1d(np.where(keep,1.,.35),sigma=2,mode='nearest')

def evidence(crepe_score,rmvpe_score):
    # Heuristic evidence only, not a calibrated voiced probability.
    c=median_filter(np.nan_to_num(crepe_score),size=3,mode='nearest')
    r=median_filter(np.nan_to_num(rmvpe_score),size=3,mode='nearest')
    return np.maximum(c,np.minimum(r,.3))

def mask(midi,crepe_score,rmvpe_score,mode):
    valid=np.isfinite(midi);s=evidence(crepe_score,rmvpe_score)
    if mode=='baseline':return valid.copy()
    if mode=='threshold':return valid&(s>=.21)
    if mode=='hysteresis':
        weak=valid&(s>=.10);strong=s>=.30;out=np.zeros(len(valid),bool)
        edges=np.diff(np.r_[False,weak,False].astype(int))
        for a,b in zip(np.where(edges==1)[0],np.where(edges==-1)[0]):
            # Require two adjacent strong frames, not a minimum event length.
            if np.any(strong[a:b-1]&strong[a+1:b]):out[a:b]=True
        return out
    if mode=='temporal':
        # Binary Viterbi decision with explicit unvoiced state. Costs are
        # heuristic; invalid baseline frames stay unvoiced and are never filled.
        p=np.clip((s-.05)/.35,.01,.99)
        emission=np.column_stack([-np.log(1-p),-np.log(p)])
        emission[~valid,1]=1e6
        back=np.zeros((len(s),2),np.int8);dp=np.array([0.,2.])
        transition=np.array([[0.,2.],[2.,0.]])
        for i in range(len(s)):
            paths=dp[:,None]+transition;back[i]=paths.argmin(axis=0)
            dp=paths.min(axis=0)+emission[i];dp-=dp.min()
        out=np.zeros(len(s),bool);k=int(dp.argmin())
        for i in range(len(s)-1,-1,-1):out[i]=bool(k);k=int(back[i,k])
        return out&valid
    raise ValueError(mode)
