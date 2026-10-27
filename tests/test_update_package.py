import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installer'))
from build_update import plan_update, safe_path, validate_removals


def row(path, content):
    return dict(path=path, sha256=hashlib.sha256(content.encode()).hexdigest(), bytes=len(content))


class UpdatePlanTests(unittest.TestCase):
    def test_reuses_environment_and_tracks_deletions(self):
        env = row('runtime/python.exe', 'runtime')
        old = [env, row('main.py', 'old'), row('runtime/unused.dll', 'optional')]
        new = [env, row('main.py', 'new'), row('resources/version.json', '1')]
        changed, removed, checks = plan_update(old, new)
        self.assertEqual([r['path'] for r in changed], ['main.py', 'resources/version.json'])
        self.assertEqual([r['path'] for r in removed], ['runtime/unused.dll'])
        self.assertEqual(next(r for r in checks if r['path']=='resources/version.json')['old'], '-')
        self.assertEqual(next(r for r in checks if r['path']=='runtime/unused.dll')['new'], '-')
        self.assertEqual(checks[0]['old'], checks[0]['new'])

    def test_runtime_and_model_replacement_requires_full_package(self):
        for path in ('runtime/python.exe', 'models/pitch.pt', 'vendor/code.py', 'bin/ffmpeg.exe'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                plan_update([row(path, 'old')], [row(path, 'new')])

    def test_explicit_runtime_update_reuses_models_and_tracks_old_runtime_for_rollback(self):
        model=row('models/pitch.pt','weight')
        old=[model,row('runtime/torch.dll','old'),row('runtime/old.dist-info/METADATA','old')]
        new=[model,row('runtime/torch.dll','new'),row('runtime/new.dist-info/METADATA','new')]
        changed,removed,checks=plan_update(old,new,include_runtime=True)
        self.assertEqual(len(changed),2)
        self.assertEqual(removed[0]['path'],'runtime/old.dist-info/METADATA')
        self.assertTrue(any(r['path']==removed[0]['path'] and r['new']=='-' for r in checks))
        validate_removals(removed,[],include_runtime=True)
        for path in ('models/pitch.pt','vendor/code.py','bin/ffmpeg.exe'):
            with self.subTest(path=path),self.assertRaises(ValueError):
                plan_update([row(path,'old')],[row(path,'new')],include_runtime=True)

    def test_rejects_unsafe_windows_paths(self):
        for path in ('../x', 'C:/x', '//server/x', 'a:x', 'x\tfile', 'a//x', 'a/./b', 'NUL.txt', 'a/x.', 'a/x ', "a'x", '{app}/x'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_path(path)
        self.assertEqual(safe_path('qml/中文文件.qml'), 'qml/中文文件.qml')

    def test_runtime_update_allows_only_reviewed_vendor_record_metadata(self):
        path='vendor/separation-runtime/audio_separator-0.47.0.dist-info/RECORD'
        self.assertEqual(len(plan_update([row(path,'old')],[row(path,'new')],True)[0]),1)
        for candidate in (path, path.replace('RECORD','METADATA'),
                          path.replace('0.47.0','0.48.0')):
            with self.subTest(path=candidate),self.assertRaises(ValueError):
                plan_update([row(candidate,'old')],[row(candidate,'new')],candidate!=path)

    def test_rejects_case_collisions_and_bad_hashes(self):
        with self.assertRaises(ValueError):
            plan_update([], [row('Main.py', 'a'), row('main.py', 'b')])
        with self.assertRaises(ValueError):
            plan_update([], [dict(path='main.py', sha256='bad')])

    def test_dependency_removal_needs_exact_audit(self):
        obsolete=row('runtime/unused.dll','old')
        with self.assertRaises(ValueError):validate_removals([obsolete],[])
        with self.assertRaises(ValueError):validate_removals([obsolete],[row('runtime/unused.dll','other')])
        validate_removals([obsolete],[obsolete])
        model=row('models/pitch.pt','weight')
        with self.assertRaises(ValueError):validate_removals([model],[model])


if __name__ == '__main__':
    unittest.main()
