"""Frozen experimental decoders; no changes to production defaults."""
import hashlib
from pathlib import Path
import numpy as np

VERSION='tracking-v2-matched-voicing-fcpe-ddsp200k'
def result_folder(song):
    p=Path(song['audio']['vocals']);s=p.stat()
    key=hashlib.sha256(f'{p.resolve()}|{s.st_size}|{s.st_mtime_ns}|{VERSION}'.encode()).hexdigest()[:20]
    from app_paths import DATA_ROOT
    return DATA_ROOT/'results'/'pitch-experiments'/key

def continuous_pitch(salience,rms,voiced_mask=None):
    """Top six local peaks, bounded transition cost, reset at unvoiced gaps.

    Scores are saliences, not calibrated probabilities. Require a .03 anchor
    in each region above .015, and do not bridge silence. All constants frozen.
    """
    cents=1997.3794084376191+20*np.arange(salience.shape[1])
    hz=10*2**(cents/1200);midi=69+12*np.log2(hz/440)
    s=salience.copy();s[:,(hz<65)|(hz>1100)]=0
    strength=s.max(axis=1);gate=(strength>=.015)&(rms>10**(-55/20))
    peaks=(s>=np.roll(s,1,axis=1))&(s>=np.roll(s,-1,axis=1))
    peaks[:,0]=False;peaks[:,-1]=False
    ranked=np.where(peaks,s,0)
    ix=np.argsort(ranked,axis=1)[:,-6:]
    value=np.take_along_axis(s,ix,axis=1);valid=np.take_along_axis(peaks,ix,axis=1)&(value>=np.maximum(.01,strength[:,None]*.08))
    cost=-np.log(np.maximum(value,1e-9)/np.maximum(strength[:,None],1e-9));cost[~valid]=1e6
    out=np.full(len(s),np.nan);chosen_score=np.zeros(len(s))
    edges=np.diff(np.r_[False,gate,False].astype(int))
    for a,b in zip(np.where(edges==1)[0],np.where(edges==-1)[0]):
        if not np.any(strength[a:b]>=.03):continue
        back=np.zeros((b-a,6),np.int8);dp=cost[a].copy()
        for t in range(a+1,b):
            delta=np.abs(midi[ix[t-1]][:,None]-midi[ix[t]][None,:])
            transition=np.minimum(2.5,.18*np.maximum(0,delta-.4))
            candidates=dp[:,None]+transition
            back[t-a]=candidates.argmin(axis=0)
            dp=candidates.min(axis=0)+cost[t];dp-=dp.min()
        k=int(dp.argmin())
        for t in range(b-1,a-1,-1):
            center=ix[t,k]
            if valid[t,k]:
                lo=max(0,center-4);hi=min(len(hz),center+5);w=s[t,lo:hi]
                out[t]=10*2**(np.dot(w,cents[lo:hi])/max(w.sum(),1e-9)/1200)
                chosen_score[t]=value[t,k]
            k=int(back[t-a,k])
    if voiced_mask is not None:
        out[~voiced_mask]=np.nan;chosen_score[~voiced_mask]=0
    return out,chosen_score

class FCPE:
    def __init__(self,device='cuda'):
        import torch,sys
        # Upstream wheel omits f02midi; use the pinned complete source checkout.
        sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor/fcpe-source'))
        from torchfcpe.models_infer import InferCFNaiveMelPE
        from torchfcpe.tools import DotDict
        path=Path(__file__).resolve().parent/'models/fcpe-ddsp-200k.pt'
        checkpoint=torch.load(path,map_location='cpu',weights_only=True)
        self.model=InferCFNaiveMelPE(DotDict(checkpoint['config_dict']),checkpoint['model']).to(device).eval()
        self.device=device
    def track(self,audio,sr):
        import torch,librosa
        y=librosa.resample(audio.mean(axis=1),orig_sr=sr,target_sr=16000)
        n=(len(y)+159)//160;out=np.full(n,np.nan)
        for start in range(0,n,2000):
            end=min(n,start+2000);left=max(0,start-100);right=min(n,end+100)
            segment=y[left*160:min(len(y),right*160)]
            if len(segment)<1024:segment=np.pad(segment,(0,1024-len(segment)))
            with torch.inference_mode():
                pred=self.model(torch.from_numpy(segment)[None,:,None].to(self.device),sr=16000,decoder_mode='local_argmax',threshold=.006).flatten().cpu().numpy()
            out[start:end]=pred[start-left:end-left]
        rms=librosa.feature.rms(y=y,frame_length=1024,hop_length=160)[0][:n]
        out[(out<65)|(out>1100)|(rms<=10**(-55/20))]=np.nan
        # FCPE API returns F0 only; no invented confidence values.
        return np.arange(n)*.01,out.copy(),out,np.full(n,np.nan),np.isfinite(out)
