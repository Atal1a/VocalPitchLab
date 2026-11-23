"""Keep the import whitelist, the dialog filter and the FFmpeg probe in agreement."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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
        dialog = re.search(r'id: audioDialog\b.*?nameFilters: \[qsTr\("([^"]+)"\)\]', qml, re.S).group(1)
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
            picture = ['-f', 'lavfi', '-i', 'color=c=black:s=64x64:d=1']
            for suffix in ('mp4', 'mov', 'm4v'):
                video = build(f'one.{suffix}', *picture, *source, '-t', '1', '-c:v', 'mpeg4', '-c:a', 'aac')
                self.assertEqual(audio_stream_count(video), 1)
            two = build('two.mp4', *picture, *source, *source, '-map', '0:v', '-map', '1:a',
                        '-map', '2:a', '-t', '1', '-c:v', 'mpeg4', '-c:a', 'aac')
            self.assertEqual(audio_stream_count(two), 2)
            self.assertEqual(audio_stream_count(build('silent.mp4', *picture, '-c:v', 'mpeg4')), 0)

    def test_worker_reports_video_without_audio_before_analysis(self):
        from vocalpitchlab.analysis.analysis_worker import run_jobs
        for stems_only in (False, True):
            request = dict(id='test-video', source='silent.MP4', result_file='unused.json', stems_only=stems_only)
            output = StringIO()
            with self.subTest(stems_only=stems_only), patch('sys.stdin', [json.dumps(request)]), redirect_stdout(output):
                with patch('vocalpitchlab.audio.audio_io.audio_stream_count', return_value=0) as probe:
                    self.assertEqual(run_jobs(), 1)
                probe.assert_called_once_with(Path(request['source']))
                prefix, payload = output.getvalue().strip().split(' ', 1)
                self.assertEqual(prefix, 'VPL_JOB_DONE')
                self.assertEqual(json.loads(payload), dict(id='test-video', code=1, error='这个文件没有音轨，请换一个文件。'))


if __name__ == '__main__':
    unittest.main()
