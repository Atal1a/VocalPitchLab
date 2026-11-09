import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

from vocalpitchlab.analysis.analysis_cache import digest_file
from vocalpitchlab.audio.stem_export import export_wav, stem_sources


class StemExportTests(unittest.TestCase):
    def test_rebuilt_vocal_stage_uses_audio_from_the_original_analysis(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            stages = root / 'results' / 'stages'
            stage = stages / 'vocals' / 'key'
            lead = stages / 'lead' / 'key' / 'w-lead' / 'vocals.wav'
            previous = stage / 'w-old' / 'vocals.wav'
            rebuilt = stage / 'w-new' / 'vocals.wav'
            original = root / 'original.wav'
            for path, level in ((lead, .25), (previous, .5), (rebuilt, .75), (original, 1.)):
                path.parent.mkdir(parents=True, exist_ok=True)
                sf.write(path, np.full((65537, 2), level, dtype='float32'), 44100, subtype='FLOAT')
            record = dict(path=rebuilt.relative_to(stage).as_posix(), size=rebuilt.stat().st_size,
                          sha256=digest_file(rebuilt))
            (stage / 'complete.json').write_text(json.dumps(dict(files=dict(audio=record))), encoding='utf-8')
            song = dict(audio=dict(original=str(original), vocals=str(lead)), algorithm=dict(separation='mel_bs'),
                        stage_cache=dict(vocals=dict(key='key', content=dict(audio=digest_file(previous)))))
            with patch('vocalpitchlab.audio.stem_export.digest_file', wraps=digest_file) as digest:
                tracks = stem_sources(song)
                digest.assert_not_called()
                for track, level in (('instrumental', .5), ('backing-vocals', .25)):
                    destination = root / (track + '.wav')
                    export_wav(destination, tracks[track])
                    samples, rate = sf.read(destination, dtype='float32')
                    self.assertEqual(rate, 44100)
                    np.testing.assert_array_equal(samples, np.full((65537, 2), level, dtype='float32'))

    def test_empty_audio_and_short_writes_preserve_the_destination(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, destination = root / 'input.wav', root / 'output.wav'
            destination.write_bytes(b'previous export')
            with sf.SoundFile(source, 'w', 44100, 2, subtype='FLOAT'):
                pass
            with self.assertRaisesRegex(ValueError, 'Empty audio'):
                export_wav(destination, (source,))
            self.assertEqual(destination.read_bytes(), b'previous export')

            sf.write(source, np.zeros((2, 2), dtype='float32'), 44100, subtype='FLOAT')
            with patch.object(sf.SoundFile, 'write', side_effect=AssertionError):
                with self.assertRaisesRegex(OSError, 'Incomplete WAV write'):
                    export_wav(destination, (source,))
            self.assertEqual(destination.read_bytes(), b'previous export')
            self.assertEqual(list(root.glob('.vpl-*')), [])
