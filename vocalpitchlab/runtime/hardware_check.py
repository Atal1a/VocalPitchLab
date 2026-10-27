"""Small inference smoke check; runs inside an analysis worker, never the UI."""
import os


def probe(torch_module=None):
    if torch_module is None:
        import torch as torch_module
    t = torch_module
    result = dict(device='cpu', torch=str(t.__version__),
                  cuda_runtime=t.version.cuda, reason='', gpu=None)
    if os.environ.get('VPL_DEVICE') == 'cpu':
        result['reason'] = '已指定使用 CPU'
        return result
    try:
        if not t.cuda.is_available():
            result['reason'] = '未检测到可用的 NVIDIA GPU 加速，请检查显卡和驱动'
            return result
        result['gpu'] = t.cuda.get_device_name(0)
        result['capability'] = list(t.cuda.get_device_capability(0))
        result['vram_bytes'] = t.cuda.get_device_properties(0).total_memory
        # Diagnostic only: PTX can make a GPU usable without an exact sm_ entry.
        try:
            result['compiled_architectures'] = list(t.cuda.get_arch_list())
        except Exception:
            pass
        with t.no_grad():
            a = t.ones((16, 16), device='cuda')
            b = a @ a
            c = t.nn.functional.conv1d(t.ones((1, 1, 32), device='cuda'),
                                       t.ones((1, 1, 3), device='cuda'))
            t.cuda.synchronize()
            if not bool(t.isfinite(b).all().item() and t.isfinite(c).all().item()):
                raise RuntimeError('GPU produced non-finite values')
        result['device'] = 'cuda'
        result['reason'] = 'GPU 运算自检通过'
    except Exception as exc:
        result['reason'] = 'GPU 运算自检未通过，请检查驱动或显卡兼容性'
        result['error'] = f'{type(exc).__name__}: {exc}'
        message = str(exc).lower()
        if any(token in message for token in (
                'no kernel image is available', 'invalid device function',
                'not compatible with the current pytorch')):
            result['reason'] = '当前安装包的 GPU 运行库不支持此显卡，请安装新版完整包'
            result['failure_kind'] = 'unsupported_gpu_architecture'
        elif 'out of memory' in message:
            result['reason'] = 'GPU 自检时显存不足，暂用 CPU，请关闭占用显存的程序后重试'
            result['failure_kind'] = 'out_of_memory'
        elif any(token in message for token in (
                'driver version is insufficient', 'driver on your system is too old')):
            result['reason'] = '显卡驱动版本过旧，请更新 NVIDIA 驱动后重试'
            result['failure_kind'] = 'driver_too_old'
    return result


if __name__ == '__main__':
    import json
    print(json.dumps(probe(), ensure_ascii=False, indent=2))
