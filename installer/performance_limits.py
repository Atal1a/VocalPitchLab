"""Limits for a disposable benchmark worker, never the desktop or another app."""
import ctypes
import os


def cpu_rate(core_budget, logical_cpus):
    if not 0 < core_budget <= logical_cpus:
        raise ValueError('CPU core budget must be positive and no larger than the host CPU count')
    rate = round(10000 * core_budget / logical_cpus)
    if not 1 <= rate <= 10000:
        raise ValueError('CPU budget is too small for the Windows quota resolution')
    return rate


def apply_worker_limits(cores=None, core_budget=None):
    """Apply only in a fresh worker that exits after the benchmark.

    Job quotas cover the system's CPU capacity, not just the affinity mask.
    Keeping the returned handle alive also covers future analysis children.
    """
    import psutil
    process = psutil.Process()
    allowed = process.cpu_affinity() if hasattr(process, 'cpu_affinity') else []
    logical = psutil.cpu_count() or 1
    result = dict(host_logical_cpus=logical, affinity=allowed, cpu_core_budget=None,
                  cpu_rate_per_10000=None, ram_limit_applied=False)
    if cores is not None:
        if not 1 <= cores <= len(allowed):
            raise ValueError('Requested CPU count is outside the available affinity mask')
        process.cpu_affinity(allowed[:cores])
        result['affinity'] = process.cpu_affinity()
    handle = None
    if core_budget is not None:
        if os.name != 'nt':
            raise RuntimeError('CPU time quotas require Windows Job Objects')
        if logical > 64:
            raise RuntimeError('CPU quota normalization across processor groups is not supported')
        rate = cpu_rate(core_budget, logical)
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]

        class RateControl(ctypes.Structure):
            _fields_ = [('flags', wintypes.DWORD), ('rate', wintypes.DWORD)]

        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            control = RateControl(0x1 | 0x4, rate)  # ENABLE | HARD_CAP
            if not kernel.SetInformationJobObject(handle, 15, ctypes.byref(control), ctypes.sizeof(control)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            kernel.CloseHandle(handle)
            raise
        result.update(cpu_core_budget=rate * logical / 10000, cpu_rate_per_10000=rate)
    return result, handle
