import json
import tempfile
import unittest
from pathlib import Path
from vocalpitchlab.runtime.playback import configure_backend


class PlaybackModeTests(unittest.TestCase):
    def configure(self,value,env=None,platform='win32'):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'library';path.mkdir()
            (path/'index.json').write_text(value,encoding='utf-8')
            env={} if env is None else env
            configure_backend(folder,env,platform)
            return env

    def test_saved_compatibility_uses_windows(self):
        env=self.configure(json.dumps(dict(settings=dict(compatiblePlayback=True))))
        self.assertEqual(env.get('QT_MEDIA_BACKEND'),'windows')

    def test_existing_library_keeps_default(self):
        for value in ['{}','{"settings":{}}','{"settings":{"compatiblePlayback":false}}',
                      '{"settings":{"compatiblePlayback":"false"}}','broken','[]','{"settings":null}']:
            with self.subTest(value=value):
                self.assertNotIn('QT_MEDIA_BACKEND',self.configure(value))

    def test_missing_library_keeps_default(self):
        with tempfile.TemporaryDirectory() as folder:
            env={};configure_backend(folder,env,'win32')
            self.assertNotIn('QT_MEDIA_BACKEND',env)

    def test_explicit_override_wins(self):
        env=self.configure('{"settings":{"compatiblePlayback":true}}',{'QT_MEDIA_BACKEND':'ffmpeg'})
        self.assertEqual(env['QT_MEDIA_BACKEND'],'ffmpeg')

    def test_other_platforms_keep_their_native_selection(self):
        for platform in ['linux','darwin']:
            self.assertNotIn('QT_MEDIA_BACKEND',self.configure('{"settings":{"compatiblePlayback":true}}',platform=platform))


if __name__=='__main__':unittest.main()
