"""Ensure distribution filtering catches cached paths without removing source."""
import shutil
import tempfile
import unittest
from pathlib import Path

from installer.privacy_check import ignore_private_files, inspect


class PackagePrivacyTests(unittest.TestCase):
    def test_copy_excludes_private_documents_and_keeps_runtime_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source'
            for name in ['runtime/lib/example.py', 'runtime/lib/__pycache__/example.pyc',
                         'assets/BRAND.md', 'PERFORMANCE_PREVIEW.md', 'LICENSE',
                         'THIRD_PARTY_NOTICES.md', 'models/example.pt',
                         'vendor/separation-runtime/bin/audio-separator.exe']:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('example', encoding='utf-8')
            target = root / 'package'
            shutil.copytree(source, target, ignore=ignore_private_files)
            self.assertTrue(inspect(target)['passed'])
            self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()},
                             {'runtime/lib/example.py', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'models/example.pt'})

    def test_scan_finds_paths_without_echoing_private_values(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'settings.json').write_text('C:/Users/PrivateTest/build', encoding='utf-8')
            report = inspect(root, [r'c:\users\privatetest'])
            self.assertFalse(report['passed'])
            self.assertEqual(report['findings'][0]['path'], 'settings.json')
            self.assertNotIn('PrivateTest', str(report))


if __name__ == '__main__':
    unittest.main()
