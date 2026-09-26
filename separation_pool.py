"""Bounded CPU model cache for one sequential analysis worker, never the GUI."""
from collections import OrderedDict

_enabled=False
_models=OrderedDict()
MAX_BYTES=1280*1024**2
MIN_FREE_BYTES=8*1024**3

def available_memory():
    import os,ctypes
    if os.name!='nt':return 0
    class Status(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ['total','free','page','free_page','virtual','free_virtual','extra']]
    s=Status();s.length=ctypes.sizeof(s)
    return s.free if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)) else 0

def enable(value=True):
    global _enabled
    _enabled=value
    if not value:clear()

def clear():
    _models.clear()
    import gc
    gc.collect()

def take(key):
    if not _enabled:return None
    if available_memory()<MIN_FREE_BYTES:
        clear();return None
    value=_models.pop(key,None)
    return value[0] if value else None

def put(key,model):
    if not _enabled or key[0]!='cuda':return False
    instance=model.model_instance
    network=instance.model_run
    size=sum(t.numel()*t.element_size() for t in list(network.parameters())+list(network.buffers()))
    if size>MAX_BYTES or available_memory()<MIN_FREE_BYTES+size:
        clear();return False
    # Clear per-song arrays before retaining the model; keep no GPU weights idle.
    instance.clear_file_specific_paths()
    instance.vpl_decoded_mix=None
    try:network.to('cpu')
    except (RuntimeError,MemoryError):
        clear();return False
    _models.pop(key,None)
    while _models and (len(_models)>=2 or sum(v[1] for v in _models.values())+size>MAX_BYTES):
        _models.popitem(last=False)
    _models[key]=(model,size)
    return True

def info():return dict(count=len(_models),tensor_bytes=sum(v[1] for v in _models.values()))
