"""Check sampled piano rendering and the fallback without requiring speakers."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import soundfile as sf
from PySide6.QtGui import QGuiApplication

from vocalpitchlab.audio.sample_piano import ANCHORS, SAMPLE_RATE, Voice
from vocalpitchlab.runtime.paths import APP_ROOT
from vocalpitchlab.ui.app import Controller


class SamplePianoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_sample_bank_covers_piano_range(self):
        self.assertEqual((ANCHORS[0], ANCHORS[-1]), (21, 108))
        for note in ANCHORS:
            path = APP_ROOT/'assets'/'piano'/f'{note}.flac'
            info = sf.info(path)
            self.assertEqual((info.samplerate, info.channels, info.subtype), (SAMPLE_RATE, 1, 'PCM_16'))
            self.assertGreater(info.duration, 2)

    def test_held_note_and_quick_click_release(self):
        sample = np.full(SAMPLE_RATE*3, 1000, dtype=np.int16)
        positions = np.arange(SAMPLE_RATE//100)
        held = Voice(sample, 1., SAMPLE_RATE, 110)
        for _ in range(100):
            self.assertTrue(np.all(held.read(positions)>0))
        self.assertFalse(held.done)
        held.release()
        self.assertEqual(held.release_at, SAMPLE_RATE)
        for _ in range(9):
            output = held.read(positions)
        self.assertTrue(held.done)
        self.assertEqual(output[-1], 0.)

        click = Voice(sample, 1., SAMPLE_RATE, 110)
        click.release()
        self.assertTrue(np.all(click.read(positions)>0))
        self.assertEqual(click.release_at, SAMPLE_RATE//25)

    def test_unavailable_sample_backend_uses_system_piano(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = Controller(Path(folder), bootstrap=False)
            try:
                with patch('vocalpitchlab.audio.sample_piano.SamplePiano.warm', side_effect=OSError), \
                     patch('vocalpitchlab.audio.piano.Piano') as midi:
                    controller.preparePiano()
                self.assertIs(controller.piano, midi.return_value)
                midi.return_value.set_volume.assert_called_once_with(controller.settings['pianoVolume'])
                midi.return_value.warm.assert_called_once()
            finally:
                controller.shutdown()
