"""Reject stale CUDA dependencies before assembling a delivery directory."""
import importlib.metadata
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GPU_DEPENDENCIES = ('torch', 'torchaudio', 'sympy')


def validate_gpu_dependencies(site_packages, lock=None):
    lock = Path(lock) if lock is not None else ROOT/'resources/reproducible/runtime.lock'
    expected = {}
    for line in lock.read_text(encoding='utf-8').splitlines():
        match = re.match(r'([\w.-]+)==([^\s]+)', line)
        if match:
            expected[match[1].lower().replace('_', '-')] = match[2]
    installed = {
        d.metadata['Name'].lower().replace('_', '-'): d.version
        for d in importlib.metadata.distributions(path=[str(site_packages)])
    }
    for name in GPU_DEPENDENCIES:
        if name not in expected:
            raise ValueError('GPU dependency missing from runtime lock: ' + name)
        if installed.get(name) != expected[name]:
            raise ValueError(
                f'GPU dependency {name}: expected {expected[name]}, '
                f'found {installed.get(name, "missing")}. Rebuild dependencies first.')
    return {name: installed[name] for name in GPU_DEPENDENCIES}
