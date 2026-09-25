"""Uniform 10 ms output, bounded chunks with one second context on each side."""
import numpy as np
import librosa
import torch
from app_paths import MODEL_ROOT
from vendor.rmvpe_rvc import RMVPE

class PitchEstimator:
    def __init__(self, device='cuda'):
        self.device = device
        from resource_policy import is_oom,clear
        try:self.engine = RMVPE(str(MODEL_ROOT/'rmvpe.pt'),is_half=False,device=device,use_jit=False)
        except RuntimeError as error:
            if not is_oom(error):raise
            from resource_policy import cpu_fallback
            cpu_fallback()
            clear();self.device='cpu';self.engine=RMVPE(str(MODEL_ROOT/'rmvpe.pt'),is_half=False,device='cpu',use_jit=False)

    def track(self, audio, sr, threshold=.03, chunk_seconds=20, return_salience=False):
        from resource_policy import is_oom,clear
        for size in [chunk_seconds,5]:
            try:return self._track(audio,sr,threshold,size,return_salience)
            except RuntimeError as error:
                if not is_oom(error):raise
                clear();print('VPL_RESOURCE: reducing RMVPE window',flush=True)
        from resource_policy import cpu_fallback
        cpu_fallback()
        self.engine.model.cpu();del self.engine;clear();self.__init__('cpu')
        return self._track(audio,sr,threshold,5,return_salience)

    def _track(self, audio, sr, threshold=.03, chunk_seconds=20, return_salience=False):
        y = librosa.resample(audio.mean(axis=1),orig_sr=sr,target_sr=16000)
        frames = (len(y)+159)//160
        raw = np.full(frames,np.nan)
        confidence = np.zeros(frames)
        salience = np.zeros((frames,360),dtype=np.float32) if return_salience else None
        chunk_frames = int(chunk_seconds*100)
        # All windows align with the 160-sample hop. Discard context predictions.
        for first in range(0,frames,chunk_frames):
            last = min(frames,first+chunk_frames)
            context_first=max(0,first-100)
            context_last=min(frames,last+100)
            segment=y[context_first*160:min(len(y),context_last*160)]
            if len(segment)<1024: segment=np.pad(segment,(0,1024-len(segment)))
            with torch.inference_mode():
                mel=self.engine.mel_extractor(torch.from_numpy(segment).float().to(self.device)[None],center=True)
                hidden=self.engine.mel2hidden(mel)[0].cpu().numpy().astype('float32')
            pred=self.engine.decode(hidden,thred=0)
            score=hidden.max(axis=1)
            left=first-context_first
            raw[first:last]=pred[left:left+last-first]
            confidence[first:last]=score[left:left+last-first]
            if return_salience:salience[first:last]=hidden[left:left+last-first]
        rms=librosa.feature.rms(y=y,frame_length=1024,hop_length=160)[0][:frames]
        voiced=(confidence>threshold)&(raw>=65)&(raw<=1100)&(rms>10**(-55/20))&np.isfinite(raw)
        f0=raw.copy()
        f0[~voiced]=np.nan
        result=(np.arange(frames)*.01,raw,f0,confidence,voiced)
        return (result,salience,rms) if return_salience else result
