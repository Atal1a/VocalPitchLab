import tempfile,unittest
from pathlib import Path
from installer.trim_optional_runtime import browser_file,audit,trim_browser
from installer.package_benchmark import write_include,verify,manifest,verify_assets,digest
from installer.prepare_github_assets import prepare as prepare_github_assets

class PackageSizeTests(unittest.TestCase):
    def test_browser_rules_preserve_runtime_and_notices(self):
        for path in ('Qt6WebEngineCore.dll','QtWebView.pyd','qml/QtWebEngine/qmldir','resources/icudtl.dat'):
            self.assertTrue(browser_file(Path(path)),path)
        for path in ('Qt6Quick.dll','Qt6Multimedia.dll','opengl32sw.dll','qml/QtQuick/Dialogs/qmldir','LICENSE-WebEngine.txt','translations/qtbase_zh_CN.qm'):
            self.assertFalse(browser_file(Path(path)),path)
    def test_audit_rejects_live_import_before_deletion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'qml').mkdir();(root/'qml/Main.qml').write_text('import QtWebEngine')
            with self.assertRaises(RuntimeError):audit(root)
    def test_trim_refuses_external_directory(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):trim_browser(Path(d))
    def test_solid_boundaries_and_unique_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rows=[dict(path='a.py',component='application'),dict(path='b.py',component='application'),dict(path='models/m.pt',component='models')]
            target=root/'files.iss';write_include(root,rows,target,True)
            text=target.read_text(encoding='utf-8-sig')
            self.assertEqual(text.count('solidbreak'),2);self.assertEqual(text.count('Source:'),3)
    def test_manifest_excludes_private_files_but_keeps_licenses(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in ('.env','.git/config','CLEAN_BUILD.md','runtime/__pycache__/x.pyc','LICENSE','models/model.pt'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
            self.assertEqual({r['path'] for r in manifest(root)},{'LICENSE','models/model.pt'})
    def test_verify_rejects_changed_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'x').write_text('changed')
            with self.assertRaises(RuntimeError):verify(root,[dict(path='x',sha256='bad')])

    def test_resume_verifies_saved_assets_and_rejects_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);asset=root/'setup.exe';asset.write_bytes(b'original')
            rows=[dict(name=asset.name,bytes=asset.stat().st_size,sha256=digest(asset))]
            verify_assets(root,rows)
            asset.write_bytes(b'modified')
            with self.assertRaises(RuntimeError):verify_assets(root,rows)
            asset.unlink()
            with self.assertRaises(RuntimeError):verify_assets(root,rows)
    def test_resume_requires_asset_records_and_rejects_extra_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaises(RuntimeError):verify_assets(root,None)
            asset=root/'setup.exe';asset.write_bytes(b'original')
            rows=[dict(name=asset.name,bytes=asset.stat().st_size,sha256=digest(asset))]
            (root/'unexpected.bin').write_bytes(b'extra')
            with self.assertRaises(RuntimeError):verify_assets(root,rows)

    def test_github_assets_include_both_editions_and_the_update(self):
        prefix = 'VocalPitchLab-1.3.0-windows-x64'
        attachments = {
            f'{prefix}-cpu-offline-setup.exe': 'cpu',
            f'{prefix}-setup.exe': 'nvidia',
            f'{prefix}-setup-1.bin': 'nvidia',
            f'{prefix}-setup-2.bin': 'nvidia',
            f'{prefix}-setup-3.bin': 'nvidia',
            f'{prefix}-update-from-1.2.0.exe': 'update-from-1.2.0',
            'VocalPitchLab-1.3.0-source.zip': '',
        }
        for nested in (True, False):
            with self.subTest(nested=nested), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                for name, subfolder in attachments.items():
                    target = (root / subfolder if nested else root) / name
                    target.parent.mkdir(exist_ok=True)
                    target.write_bytes(b'fixture')
                rows = prepare_github_assets(root)
                self.assertEqual({row['name'] for row in rows}, attachments.keys())
                self.assertTrue(all((root / row['path']).is_file() for row in rows))
                instructions = (root / '安装说明.txt').read_text(encoding='utf-8-sig')
                self.assertIn(f'{prefix}-cpu-offline-setup.exe', instructions)
                self.assertIn(f'{prefix}-update-from-1.2.0.exe', instructions)
                self.assertNotIn(f'{prefix}-offline-setup.exe', instructions)
                second_volume = (root / 'nvidia' if nested else root) / f'{prefix}-setup-2.bin'
                second_volume.unlink()
                with self.assertRaisesRegex(SystemExit, 'Volume numbering is incomplete'):
                    prepare_github_assets(root)

if __name__=='__main__':unittest.main()
