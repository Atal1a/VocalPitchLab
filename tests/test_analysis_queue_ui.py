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
import numpy as np
import soundfile as sf

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
                    self.assertEqual(controller.state['message'], '请选择支持的音频或视频文件。')
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

                    original = root/'decoded.wav';sf.write(original,np.zeros(44100,dtype='float32'),44100)
                    curve = root/'curve.csv';curve.write_text('time_seconds,midi_float,periodicity_or_probability\n0,57,1\n')
                    notes = root/'notes.json';notes.write_text('{"notes": []}')
                    controller.result_file = root / 'result.json'
                    controller.result_file.write_text(json.dumps(dict(song=dict(name=sources[0].stem,
                        duration=1, audio=dict(original=str(original),vocals=str(original)),
                        curves=dict(crepe_full=str(curve)), main_notes=str(notes),algorithm=dict(separation='original')))), encoding='utf-8')
                    with patch.object(controller,'queue_presentation'), patch.object(controller,'load_audio'):
                        controller.finished(0, job_done=True)
                    self.app.processEvents()
                    self.assertEqual(first['state'],'complete')
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

    def test_only_one_batch_write_and_one_repair_for_damaged_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'take.wav';decoded=root/'original.wav'
            for path in (source,decoded):sf.write(path,np.zeros(44100,dtype='float32'),44100)
            from vocalpitchlab.analysis.analysis_cache import digest_file
            from vocalpitchlab.analysis.recording import source_signature
            curve=root/'curve.csv';curve.write_text('time_seconds,midi_float,periodicity_or_probability\n0,60,1\n')
            notes=root/'notes.json';notes.write_text('{')
            song=dict(song_id='existing',name='take',duration=1,source=str(source),source_sha256=digest_file(source),
                      source_signature=source_signature(source),audio=dict(original=str(decoded),vocals=str(decoded)),
                      curves=dict(crepe_full=str(curve)),main_notes=str(notes),algorithm=dict(separation='original'))
            (root/'index.json').write_text(json.dumps(dict(songs=[song])))
            b=Controller(root,bootstrap=False)
            self.assertIsNone(b.song)
            addition=root/'new.wav';addition.touch()
            try:
                with patch.object(b,'start_next') as start,patch.object(b,'save',wraps=b.save) as save:
                    b.enqueueBatch([str(source),str(source),str(addition),str(root/'wrong.txt')])
                    save.assert_called_once();start.assert_called_once()
                repair,new=b.data['jobs']
                self.assertEqual(repair['target_id'],'existing')
                self.assertEqual(repair['separation'],'original')
                self.assertEqual(new['source'],str(addition))
                self.assertEqual(b.data['songs'],[song])
            finally:
                b.shutdown()

    def test_only_the_matching_job_can_publish_ready_tracks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            original=root/'take.wav';vocals=root/'vocals.wav'
            for path in (original,vocals):sf.write(path,np.zeros(44100,dtype='float32'),44100)
            b=Controller(root,bootstrap=False)
            engine=create_engine(b);window=engine.rootObjects()[0]
            job=dict(id='current',source=str(original),state='running',separation='mel_roformer')
            b.active=b.display_job=job;b.data['jobs']=[job]
            b.log_file=root/'worker.log';b.process=Mock()
            descriptor=dict(name='take',source=str(original),audio=dict(original=str(original),vocals=str(vocals)),
                            algorithm=dict(separation='mel_roformer'))
            def ready(key):
                return ('VPL_STEMS_READY '+json.dumps(dict(id=key,stems=descriptor))+'\n').encode()
            export=window.findChild(QObject,'analysisJobExport')
            try:
                b.process.readAllStandardOutput.side_effect=(ready('unrelated'),ready('current'))
                b.changed.emit();b.read_progress()
                self.assertFalse(export.isVisible())
                b.read_progress()
                self.assertTrue(export.isVisible())
                self.assertEqual(job['state'],'running')
                self.assertIsNone(b.song)
                self.assertEqual(b.jobStemExportOptions('current'),['vocals','instrumental'])
            finally:
                b.process=None;b.active=None
                b.shutdown();window.close();engine.deleteLater()
                self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
