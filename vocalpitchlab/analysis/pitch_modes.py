"""Conservative gap recovery; never replace an existing production pitch."""
import numpy as np

def recover_gaps(base, crepe, rmvpe, crepe_score, rmvpe_score):
    out=np.asarray(base).copy()
    eligible=(np.isfinite(crepe)&np.isfinite(rmvpe)&
              (crepe_score>=.5)&(rmvpe_score>=.03)&(np.abs(crepe-rmvpe)<=.5))
    edges=np.diff(np.r_[False,eligible,False].astype(int))
    for start,end in zip(np.where(edges==1)[0],np.where(edges==-1)[0]):
        if end-start<10:continue
        missing=~np.isfinite(out[start:end])
        out[start:end][missing]=((crepe[start:end]+rmvpe[start:end])*.5)[missing]
    return out
