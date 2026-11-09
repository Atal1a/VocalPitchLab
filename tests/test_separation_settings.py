"""Cover separation preferences and the modes stored in analysis jobs."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtGui import QGuiApplication

from vocalpitchlab.ui.app import Controller


class SeparationSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_four_combinations_are_saved_with_each_job(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = Controller(folder, bootstrap=False)
            self.addCleanup(controller.deleteLater)
            try:
                self.assertEqual(controller.default_separation, 'mel_bs')
                combinations = [(True, 'mel_bs', 'mel_bs'), (True, 'mel_roformer', 'mel_roformer'),
                                (False, 'mel_bs', 'bs_only'), (False, 'mel_roformer', 'original')]
                with patch.object(controller, 'start_next'):
                    for vocal, harmony_model, mode in combinations:
                        controller.setting('vocalSeparation', vocal)
                        controller.setting('separationModel', harmony_model)
                        source = Path(folder) / (mode + '.wav')
                        source.touch()
                        controller.enqueue(str(source))
                self.assertEqual([job['separation'] for job in controller.data['jobs']],
                                 [mode for _, _, mode in combinations])
            finally:
                controller.shutdown()
            reopened = Controller(folder, bootstrap=False)
            try:
                self.assertEqual(reopened.default_separation, 'original')
            finally:
                reopened.shutdown()

    def test_existing_harmony_preference_carries_over(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'index.json').write_text(json.dumps(dict(songs=[], settings=dict(
                separationModel='mel_roformer', pipelineVersion='lead-default-v1'))), encoding='utf-8')
            controller = Controller(folder, bootstrap=False)
            try:
                self.assertTrue(controller.settings['vocalSeparation'])
                self.assertEqual(controller.default_separation, 'mel_roformer')
            finally:
                controller.shutdown()
