import os
import unittest
from unittest.mock import MagicMock, patch

from vocalpitchlab.runtime.hardware_check import probe


class HardwareCheckTests(unittest.TestCase):
    def torch(self, capability=(12, 0)):
        t = MagicMock()
        t.__version__ = '2.7.1+cu128'
        t.version.cuda = '12.8'
        t.cuda.is_available.return_value = True
        t.cuda.get_device_name.return_value = 'NVIDIA GeForce RTX 5070 Ti'
        t.cuda.get_device_capability.return_value = capability
        t.cuda.get_device_properties.return_value.total_memory = 16 * 1024**3
        t.cuda.get_arch_list.return_value = ['sm_89', 'sm_120']
        t.isfinite.return_value.all.return_value.item.return_value = True
        return t

    def test_success_runs_kernels_even_without_exact_architecture_entry(self):
        t = self.torch()
        t.cuda.get_arch_list.return_value = ['sm_90']
        with patch.dict(os.environ, {'VPL_DEVICE': 'cuda'}):
            result = probe(t)
        self.assertEqual(result['device'], 'cuda')
        t.ones.assert_called()
        t.nn.functional.conv1d.assert_called_once()
        t.cuda.synchronize.assert_called_once()

    def test_kernel_failure_keeps_cpu_and_reports_package_fix(self):
        t = self.torch()
        t.ones.side_effect = RuntimeError('CUDA error: no kernel image is available for execution on the device')
        with patch.dict(os.environ, {'VPL_DEVICE': 'cuda'}):
            result = probe(t)
        self.assertEqual(result['device'], 'cpu')
        self.assertEqual(result['failure_kind'], 'unsupported_gpu_architecture')
        self.assertIn('完整包', result['reason'])
        self.assertIn('no kernel image', result['error'])
        self.assertEqual(result['capability'], [12, 0])
        self.assertIn('sm_120', result['compiled_architectures'])

    def test_oom_and_old_driver_have_distinct_reasons(self):
        for message, kind in [('CUDA out of memory', 'out_of_memory'),
                              ('CUDA driver version is insufficient for CUDA runtime version', 'driver_too_old')]:
            with self.subTest(message=message):
                t = self.torch()
                t.ones.side_effect = RuntimeError(message)
                with patch.dict(os.environ, {'VPL_DEVICE': 'cuda'}):
                    result = probe(t)
                self.assertEqual(result['device'], 'cpu')
                self.assertEqual(result['failure_kind'], kind)

    def test_forced_cpu_does_not_initialize_cuda(self):
        t = self.torch()
        with patch.dict(os.environ, {'VPL_DEVICE': 'cpu'}):
            result = probe(t)
        self.assertEqual(result['device'], 'cpu')
        t.cuda.is_available.assert_not_called()

    def test_diagnostic_failure_does_not_disable_working_gpu(self):
        t = self.torch()
        t.cuda.get_arch_list.side_effect = RuntimeError('diagnostic unavailable')
        with patch.dict(os.environ, {'VPL_DEVICE': 'cuda'}):
            result = probe(t)
        self.assertEqual(result['device'], 'cuda')


if __name__ == '__main__':
    unittest.main()
