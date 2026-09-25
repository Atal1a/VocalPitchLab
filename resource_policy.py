"""Conservative resource policy; only allocation failures trigger retries."""
import os,gc
_configured=False
_hardware=None

def cpu_fallback():
    import json
    print('VPL_EVENT '+json.dumps(dict(computeStatus='显存不足，部分阶段使用 CPU，分析较慢'),ensure_ascii=False),flush=True)

def hardware():
    global _hardware
    if _hardware is None:
        from hardware_check import probe
        _hardware=probe()
        import json
        status='GPU 加速' if _hardware['device']=='cuda' else 'CPU 分析较慢：'+_hardware['reason']
        print('VPL_EVENT '+json.dumps(dict(hardware=_hardware,computeStatus=status),ensure_ascii=False),flush=True)
    return _hardware
def device():
    global _configured
    import torch
    selected=hardware()['device']
    if selected=='cuda' and not _configured:
        limit=float(os.environ.get('VPL_CUDA_MEMORY_GIB','0'))
        if limit>0:torch.cuda.set_per_process_memory_fraction(min(1,limit*1024**3/torch.cuda.get_device_properties(0).total_memory))
        _configured=True
    return selected
def is_oom(error):
    import torch
    return isinstance(error,torch.cuda.OutOfMemoryError) or ('cuda' in str(error).lower() and 'out of memory' in str(error).lower())
def clear():
    import torch
    gc.collect()
    if torch.cuda.is_available():torch.cuda.empty_cache()
def batches(dev):
    if dev=='cpu':return [32]
    import torch
    free,_=torch.cuda.mem_get_info()
    start=256 if free>=8*1024**3 else 64
    return [start,32,8]
def separation_segments(dev):
    if dev=='cpu':return [256]
    import torch
    free,_=torch.cuda.mem_get_info()
    return [None,512,256] if free>=8*1024**3 else [512,256]
