"""Verify live language changes and saved settings through the QML interface."""
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QSignalSpy, QTest

from vocalpitchlab.ui.app import Controller, create_engine


class LocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_switch_language_and_reopen_existing_library(self):
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / 'index.json'
            job = dict(id='example', source='示例.wav', state='failed', message='准备分析',
                       computeStatus='CPU 分析较慢：已指定使用 CPU')
            index.write_text(json.dumps(dict(songs=[], jobs=[job])), encoding='utf-8')
            controller = Controller(folder, bootstrap=False)
            engine = create_engine(controller)
            window = engine.rootObjects()[0]
            window.resize(1060, 720)
            settings = window.findChild(QObject, 'settingsPopup')
            import_button = window.findChild(QObject, 'importButton')
            time_control = window.findChild(QObject, 'timeControl')
            controller.viewJob(job['id'])

            def switch_to(button_name):
                button = window.findChild(QObject, button_name)
                position = button.mapToScene(button.boundingRect().center()).toPoint()
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=position)
                self.app.processEvents()

            try:
                self.assertEqual(import_button.property('text'), '＋ 导入歌曲')
                settings.open()
                QTest.qWait(220)
                translated_content = QSignalSpy(controller.localizedContentChanged)
                switch_to('englishLanguage')
                self.assertEqual(translated_content.count(), 1)
                self.assertEqual(import_button.property('text'), '+ Import songs')
                self.assertEqual(time_control.property('valueText'), '20 s')
                self.assertEqual(controller.jobs[0]['name'], '示例')
                self.assertEqual(controller.jobs[0]['message'], 'Preparing analysis')
                self.assertEqual(controller.state['jobText'], 'Preparing analysis · Slower CPU analysis. CPU mode selected')

                switch_to('chineseLanguage')
                self.assertEqual(import_button.property('text'), '＋ 导入歌曲')
                self.assertEqual(controller.jobs[0]['message'], job['message'])
                switch_to('englishLanguage')
                saved = json.loads(index.read_text(encoding='utf-8'))
                self.assertEqual(saved['settings']['language'], 'en')
                self.assertEqual(saved['jobs'][0], job)
            finally:
                window.close()
                controller.shutdown()
                engine.deleteLater()
                self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

            reopened = Controller(folder, bootstrap=False)
            engine = create_engine(reopened)
            window = engine.rootObjects()[0]
            try:
                self.assertEqual(window.findChild(QObject, 'importButton').property('text'), '+ Import songs')
                self.assertEqual(reopened.jobs[0]['message'], 'Preparing analysis')
            finally:
                window.close()
                reopened.shutdown()
                engine.deleteLater()
                self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
