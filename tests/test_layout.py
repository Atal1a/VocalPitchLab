"""Check relocated resources and real subprocess entry points."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class LayoutTests(unittest.TestCase):
    def test_resource_root(self):
        from vocalpitchlab.runtime.paths import APP_ROOT
        from vocalpitchlab.analysis.main_notes import CONFIG_PATH, current_settings
        self.assertEqual(APP_ROOT, ROOT)
        self.assertEqual(CONFIG_PATH, ROOT/'note-settings.json')
        self.assertTrue(current_settings())
        self.assertTrue((APP_ROOT/'qml/Main.qml').is_file())

    def test_source_manifest(self):
        from installer.application_files import SOURCE_FILES
        expected = {p.relative_to(ROOT).as_posix() for p in (ROOT/'vocalpitchlab').rglob('*.py')} | {'main.py'}
        self.assertEqual(set(SOURCE_FILES), expected)
        self.assertTrue(all((ROOT/name).is_file() for name in SOURCE_FILES))

    def test_internal_imports_resolve(self):
        import importlib.util
        for path in (ROOT/'vocalpitchlab').rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('vocalpitchlab.'):
                    self.assertIsNotNone(importlib.util.find_spec(node.module), node.module)

    def test_background_entry_points_outside_project(self):
        with tempfile.TemporaryDirectory(prefix='vpl layout ') as folder:
            env = dict(os.environ, VPL_DATA_DIR=folder)
            commands = [[], ['--analyze', '--help'], ['--presentation', '--help'], ['--analysis-worker']]
            for args in commands:
                result = subprocess.run([sys.executable, '-I', str(ROOT/'main.py'), *(args or ['--help'])],
                                        cwd=folder, env=env, input='', capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
