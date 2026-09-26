"""Hardware-adaptive separation execution; model settings stay unchanged."""
from functools import lru_cache

VERSION='amp-sdpa-v1'

def eligible(device,capability,name):
    # GTX Turing variants lack Tensor Cores despite sharing compute capability.
    return device=='cuda' and tuple(capability)>=(7,0) and 'GTX' not in name.upper()

@lru_cache(maxsize=4)
def select(device):
    import torch
    result=dict(policy=VERSION,mode='fp32',capability=None)
    if device!='cuda':return result
    try:
        capability=torch.cuda.get_device_capability()
        result['capability']=list(capability)
        if not eligible(device,capability,torch.cuda.get_device_name()):return result
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.float16):
            x=torch.ones((64,64),device='cuda');y=x@x
            q=torch.ones((1,4,64,32),device='cuda',dtype=torch.float16)
            z=torch.nn.functional.scaled_dot_product_attention(q,q,q)
            torch.cuda.synchronize()
            if not bool(torch.isfinite(y).all() and torch.isfinite(z).all()):return result
        result['mode']='amp'
    except (RuntimeError,NotImplementedError):
        result['mode']='fp32'
    return result

def configure_attention(instance):
    from audio_separator.separator.uvr_lib_v5.roformer.attend import Attend,FlashAttentionConfig
    for module in instance.model_run.modules():
        if isinstance(module,Attend):
            module.cuda_config=FlashAttentionConfig(True,True,True)

def precision_failure(error):
    if isinstance(error,NotImplementedError):return True
    message=str(error).lower()
    return any(token in message for token in [
        'no available kernel','no viable backend','not supported for half',
        "not implemented for 'half'",'not supported for float16',
        'cublas_status_not_supported','no kernel image is available',
        'non-finite','nonfinite','contains nan','contains inf'])
