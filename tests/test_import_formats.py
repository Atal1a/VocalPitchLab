"""Keep the import whitelist, the dialog filter and the FFmpeg probe in agreement."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ImportFormatTests(unittest.TestCase):
    def test_whitelist_covers_audio_and_video(self):
        from vocalpitchlab.ui.app import FORMATS, VIDEO_FORMATS
        self.assertEqual(VIDEO_FORMATS, {'.mp4', '.mov', '.m4v'})
        self.assertEqual(FORMATS, {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma', '.aiff'} | VIDEO_FORMATS)

    def test_dialog_filter_lists_every_format(self):
        from vocalpitchlab.ui.app import FORMATS
        qml = (ROOT / 'qml/Main.qml').read_text(encoding='utf-8')
        dialog = re.search(r'id: audioDialog;.*?nameFilters: \[qsTr\("([^"]+)"\)\]', qml, re.S).group(1)
        self.assertEqual(set(re.findall(r'\*(\.[a-z0-9]+)', dialog)), FORMATS)

    def test_audio_stream_count(self):
        from vocalpitchlab.audio.audio_io import audio_stream_count, ffmpeg_path
        try:
            ffmpeg = ffmpeg_path()
        except (OSError, RuntimeError):
            self.skipTest('FFmpeg is unavailable')
        source = ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo']
        with tempfile.TemporaryDirectory() as folder:
            def build(name, *args):
                target = Path(folder) / name
                subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', *args, str(target)], check=True)
                return target
            self.assertEqual(audio_stream_count(build('one.mp4', *source, '-t', '1', '-c:a', 'aac')), 1)
            self.assertEqual(audio_stream_count(build('two.mp4', *source, *source,
                                                      '-map', '0:a', '-map', '1:a', '-t', '1', '-c:a', 'aac')), 2)
            self.assertEqual(audio_stream_count(build('silent.mp4',
                                                      '-f', 'lavfi', '-i', 'color=c=black:s=64x64:d=1',
                                                      '-c:v', 'mpeg4')), 0)


if __name__ == '__main__':
    unittest.main()
