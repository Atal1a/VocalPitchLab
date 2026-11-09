"""Exercise multi-file import and the progress card's queue handoff."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QGuiApplication
from PySide6.QtTest import QTest

from vocalpitchlab.ui.app import Controller, create_engine


class AnalysisQueueUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_repeated_unsupported_file_drop_shows_the_toast_again(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'unsupported.txt'
            source.touch()
            controller = Controller(folder, bootstrap=False)
            engine = create_engine(controller)
            window = engine.rootObjects()[0]
            timer = window.findChild(QObject, 'toastTimer')
            timer.setProperty('interval', 100)
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(source))])
            flags = Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier

            def drop_file():
                self.app.sendEvent(window, QDragEnterEvent(QPoint(500, 300), *flags))
                self.app.sendEvent(window, QDropEvent(QPointF(500, 300), *flags))

            try:
                for _ in range(2):
                    drop_file()
                    self.assertEqual(controller.state['message'], '请选择有效的音频文件。')
                    self.assertTrue(timer.property('running'))
                    self.assertEqual(controller.data['jobs'], [])
                    QTest.qWait(200)
                    self.assertFalse(timer.property('running'))
                    controller.changed.emit()
                    self.assertFalse(timer.property('running'))
            finally:
                controller.shutdown()
                window.close()
                engine.deleteLater()
                self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_batch_card_keeps_showing_the_next_song(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sources = [root / name for name in ('第一首.wav', '第二首.wav', '第三首.wav')]
            for source in sources:
                source.touch()
            controller = Controller(root, bootstrap=False)
            engine = create_engine(controller)
            window = engine.rootObjects()[0]
            card = window.findChild(QObject, 'analysisCard')
            title = window.findChild(QObject, 'analysisJobName')
            status = window.findChild(QObject, 'analysisJobStatus')
            progress = window.findChild(QObject, 'analysisProgressFill')
            try:
                with patch.object(controller, 'start_next'), patch.object(controller, 'selectSong'):
                    mime = QMimeData()
                    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in sources])
                    flags = Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
                    self.app.sendEvent(window, QDragEnterEvent(QPoint(500, 300), *flags))
                    drop = QDropEvent(QPointF(500, 300), *flags)
                    self.app.sendEvent(window, drop)
                    self.assertTrue(drop.isAccepted())
                    first, second, third = controller.data['jobs']

                    controller.active = controller.display_job = first
                    first.update(state='running', message='准备分析')
                    controller.contentChanged.emit()
                    controller.changed.emit()
                    controller.log_file = root / 'worker.log'
                    event = 'VPL_EVENT {"progress":35,"message":"分离和声"}\n'.encode()
                    split = event.index('分'.encode()) + 1
                    controller.process = Mock()
                    controller.process.readAllStandardOutput.side_effect = (event[:split], event[split:])
                    controller.read_progress()
                    controller.read_progress()
                    QTest.qWait(50)
                    self.assertEqual(title.property('text'), sources[0].name)
                    self.assertEqual(status.property('text'), '分离和声')
                    jobs = window.findChild(QObject, 'jobList')
                    running_row = next(row for row in jobs.property('contentItem').childItems()
                                       if row.objectName() == 'jobRow_' + first['id'])
                    row_content = running_row.property('contentItem')
                    row_status = row_content.findChild(QObject, 'jobRowStatus')
                    self.assertEqual(row_status.property('text'), '分离和声')

                    controller.result_file = root / 'result.json'
                    controller.result_file.write_text(json.dumps(dict(song=dict(name=sources[0].stem,
                        duration=1, audio={}, curves={}, main_notes=str(sources[0])))), encoding='utf-8')
                    controller.finished(0, job_done=True)
                    self.app.processEvents()
                    self.assertTrue(card.isVisible())
                    self.assertEqual(title.property('text'), sources[1].name)
                    self.assertEqual(status.property('text'), '等待分析')
                    self.assertEqual(progress.width(), 0)

                    controller.removeDisplayedJob()
                    self.assertNotIn(second, controller.data['jobs'])
                    self.assertIn(third, controller.data['jobs'])
                    self.assertEqual(title.property('text'), sources[2].name)
            finally:
                controller.process = None
                controller.shutdown()
                window.close()
                engine.deleteLater()
                self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
