"""Reject mixed or stale inference runtimes before assembling a delivery directory."""
import importlib.metadata
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GPU_DEPENDENCIES = ('torch', 'torchaudio', 'sympy')


def validate_gpu_dependencies(site_packages, lock=None):
    return validate_runtime_dependencies(site_packages, 'nvidia', lock)


def validate_runtime_dependencies(site_packages, runtime, lock=None):
    lock_name = {'nvidia': 'runtime.lock', 'cpu': 'runtime-cpu.lock'}[runtime]
    lock = Path(lock) if lock is not None else ROOT/'resources/reproducible'/lock_name
    expected = {}
    for line in lock.read_text(encoding='utf-8').splitlines():
        match = re.match(r'([\w.-]+)==([^\s]+)', line)
        if match:
            expected[match[1].lower().replace('_', '-')] = match[2]
    installed = {name: [] for name in GPU_DEPENDENCIES}
    for distribution in importlib.metadata.distributions(path=[str(site_packages)]):
        name = distribution.metadata['Name'].lower().replace('_', '-')
        if name in installed:
            installed[name].append(distribution.version)
    for name in GPU_DEPENDENCIES:
        if name not in expected:
            raise ValueError('Dependency missing from runtime lock: ' + name)
        if installed[name] != [expected[name]]:
            raise ValueError(
                f'{runtime} dependency {name}: expected {expected[name]}, '
                f'found {", ".join(installed[name]) or "missing"}. Rebuild dependencies first.')
    if runtime == 'cpu':
        cuda = ('torch_cuda', 'c10_cuda', 'cudart', 'cublas', 'cudnn', 'cufft', 'cusparse', 'nvrtc')
        if any(p.name.lower().startswith(cuda) for p in (site_packages/'torch/lib').glob('*.dll')):
            raise ValueError('The CPU dependency directory contains CUDA libraries')
    return {name: installed[name][0] for name in GPU_DEPENDENCIES}
