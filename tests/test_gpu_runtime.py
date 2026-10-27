import tempfile
import unittest
from pathlib import Path

from installer.gpu_runtime import validate_gpu_dependencies


class GpuRuntimeTests(unittest.TestCase):
    def test_stale_or_missing_runtime_is_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root/'runtime.lock'
            lock.write_text('torch==2.7.1+cu128\ntorchaudio==2.7.1+cu128\nsympy==1.14.0\n')
            with self.assertRaisesRegex(ValueError, 'found missing'):
                validate_gpu_dependencies(root, lock)
            for name, version in [('torch', '2.5.1+cu124'), ('torchaudio', '2.7.1+cu128'), ('sympy', '1.14.0')]:
                folder = root/f'{name}.dist-info'
                folder.mkdir()
                (folder/'METADATA').write_text(f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n')
            with self.assertRaisesRegex(ValueError, 'found 2.5.1'):
                validate_gpu_dependencies(root, lock)
            (root/'torch.dist-info/METADATA').write_text('Metadata-Version: 2.1\nName: torch\nVersion: 2.7.1+cu128\n')
            self.assertEqual(validate_gpu_dependencies(root, lock)['torch'], '2.7.1+cu128')


if __name__ == '__main__':
    unittest.main()
