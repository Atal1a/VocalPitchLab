"""Run with the candidate's bundled Python; require real CUDA execution."""
import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('app', type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
app = args.app.resolve()
sys.path.insert(0, str(app))

import torch
import torchaudio
from vocalpitchlab.runtime.hardware_check import probe

if not Path(torch.__file__).resolve().is_relative_to(app/'runtime'):
    raise RuntimeError('GPU check imported dependencies outside the candidate runtime')
if torch.__version__ != '2.7.1+cu128' or torchaudio.__version__ != '2.7.1+cu128':
    raise RuntimeError('Unexpected GPU dependency versions')
if torch.version.cuda != '12.8':
    raise RuntimeError('Expected the CUDA 12.8 build')

result = probe()
if result['device'] != 'cuda':
    raise RuntimeError(json.dumps(result, ensure_ascii=False))
if 'sm_120' not in result.get('compiled_architectures', []):
    raise RuntimeError('The candidate lacks native RTX 50-series kernels')

with torch.no_grad():
    samples = torch.sin(torch.arange(16000, device='cuda') * (2 * torch.pi * 440 / 16000))
    spectrum = torch.stft(samples, n_fft=1024, return_complex=True,
                          window=torch.hann_window(1024, device='cuda'))
    resampled = torchaudio.functional.resample(samples, 16000, 22050)
    torch.cuda.synchronize()
    if not bool(torch.isfinite(spectrum).all() and torch.isfinite(resampled).all()):
        raise RuntimeError('Audio CUDA operations produced non-finite results')
result.update(torchaudio=torchaudio.__version__, audio_cuda_operations=True,
              blackwell_native_kernels=True,
              blackwell_hardware_tested=result['capability'][0] == 12)
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
