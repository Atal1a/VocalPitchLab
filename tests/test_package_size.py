import tempfile,unittest
from pathlib import Path
from installer.trim_optional_runtime import browser_file,audit,trim_browser
from installer.package_benchmark import write_include,verify,manifest

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

if __name__=='__main__':unittest.main()
