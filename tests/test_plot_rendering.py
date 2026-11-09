"""Scrolling render equivalence, cache invalidation and playback notifications."""
from ctypes import c_void_p
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import tempfile
import time
import unittest
from unittest.mock import Mock, call, patch
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QWindow
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickWindow
from vocalpitchlab.audio.piano import Piano
from vocalpitchlab.ui.app import Controller, PitchView, create_engine
from vocalpitchlab.ui.plot_layers import ImageCache


class RenderCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        times = np.arange(0, 240, .01)
        values = 66 + np.sin(times*3) * 3
        values[(times % 3) > 2.8] = np.nan
        values[1234] = np.nan  # Even a single missing frame must remain a gap.
        self.backend = SimpleNamespace(
            song={'duration': 240}, span=20., low=60., high=72., t=50.,
            dark=True, playback={'mainNote': '—', 'pitch': '—'},
            settings={'hoverNotes': True, 'liveNotes': False, 'liveCurve': False, 'cleanCurve': True},
            show_blocks=False, show_curve=True, preview_note=None, preview_until=0,
            loop=False, notes=[], primary='test', series={'test': (times, values)},
            loudness=(times, .5 + .4*np.sin(times)),
            curve_reliability={'test': (times, .6 + .4*np.cos(times))},
        )
        self.backend.x_range = lambda: (self.backend.t, self.backend.t+self.backend.span)
        self.view = PitchView()
        self.view._controller = self.backend
        self.view.setWidth(800)
        self.view.setHeight(360)

    def curve_image(self, reference=False):
        image = QImage(800, 360, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        b = self.backend
        x0, y0, width, height = self.view.geometry_values()
        left, right = b.x_range()
        x = lambda t: x0+(t-left)/b.span*width
        y = lambda v: y0+(b.high-v)/(b.high-b.low)*height
        painter.setClipRect(x0, y0, width, height)
        try:
            if reference:
                times, values = self.view.curve_samples(b.primary, b.span, width)
                a, c = np.searchsorted(times, [left, right])
                self.view.draw_curve(painter, times[max(0, a-1):c+1], values[max(0, a-1):c+1], x, y, b.dark)
            else:
                self.view.draw_detail_curve(painter, b.span, width, height, left, right, x, b.dark)
        finally:
            painter.end()
        return image

    def assert_matches_reference(self):
        cached, reference = self.curve_image(), self.curve_image(reference=True)
        a = np.frombuffer(cached.constBits(), np.uint8).astype(np.int16)
        b = np.frombuffer(reference.constBits(), np.uint8).astype(np.int16)
        delta = np.abs(a-b)
        # Translating cached coordinates can change subpixel antialias rounding.
        self.assertLess(float(delta.mean()), .5)
        alpha_a, alpha_b = a.reshape(360, 800, 4)[:, :, 3], b.reshape(360, 800, 4)[:, :, 3]
        self.assertLess(abs(float(alpha_a.sum()-alpha_b.sum()))/max(1, alpha_b.sum()), .015)
        # Stroke locations may differ at their antialiased edges, at most one pixel.
        near_a, near_b = np.zeros_like(alpha_a, dtype=bool), np.zeros_like(alpha_b, dtype=bool)
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                near_a |= np.roll(alpha_a > 0, (dy, dx), (0, 1))
                near_b |= np.roll(alpha_b > 0, (dy, dx), (0, 1))
        self.assertFalse(np.any((alpha_a > 8) & ~near_b))
        self.assertFalse(np.any((alpha_b > 8) & ~near_a))
        return cached

    def test_scrolling_and_seeking_preserve_curve_styles_and_gaps(self):
        for span in [3., 20., 39., 120.]:
            self.backend.span = span
            for position in [0., .017, 12., 51.25, 90., 12.]:
                with self.subTest(span=span, position=position):
                    self.backend.t = position
                    self.assert_matches_reference()

    def test_replacement_data_and_view_changes_do_not_reuse_stale_lines(self):
        original = self.assert_matches_reference()
        times = self.backend.loudness[0]
        self.backend.loudness = (times, np.ones(len(times)))
        self.assertNotEqual(original, self.assert_matches_reference())
        self.backend.curve_reliability = {'test': (times, np.full(len(times), .4))}
        self.assert_matches_reference()
        self.backend.settings['cleanCurve'] = False
        self.assert_matches_reference()
        self.backend.low = 62.
        self.backend.dark = False
        self.assert_matches_reference()
        self.backend.series['test'] = (times.copy(), np.full(len(times), 65.))
        self.assert_matches_reference()

    def test_gap_is_not_bridged(self):
        times = np.arange(0, 3, .01)
        values = np.full(len(times), 66.)
        values[100:200] = np.nan
        self.backend.series['test'] = (times, values)
        self.backend.t = 0.
        self.backend.span = 3.
        image = self.curve_image()
        x0, y0, width, height = self.view.geometry_values()
        self.assertEqual(image.pixelColor(round(x0+width*.5), round(y0+height*.5)).alpha(), 0)
        self.assertGreater(image.pixelColor(round(x0+width*.2), round(y0+height*.5)).alpha(), 0)

    def test_chunk_storage_stays_bounded_when_seeking(self):
        self.backend.span = 3.
        for position in np.arange(0, 235, 4):
            self.backend.t = position
            self.curve_image()
        self.assertLessEqual(len(self.view.detail_chunks), 64)
        self.backend.t = 0.
        self.assert_matches_reference()

    def test_large_overview_uses_segments_instead_of_an_oversized_image(self):
        self.backend.song = {'duration': 400}
        self.backend.span = 40
        self.view.setWidth(1200)
        self.view.setHeight(900)
        self.view.long_curve_layer = lambda *args: self.fail('Oversized overview image')
        image = QImage(1200, 900, QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        try:
            self.view.paint(painter)
        finally:
            painter.end()

    def test_scene_graph_tiles_survive_pan_seek_and_data_replacement(self):
        b = self.backend
        b.notes = [dict(start=50.,end=51.,duration=1.,midi=66,note='F#4')]
        window = QQuickWindow();window.resize(800,360)
        self.view.setParentItem(window.contentItem())
        try:
            window.show();self.view.request_frame();QTest.qWait(50)
            image = window.grabWindow()
            self.assertFalse(image.isNull())
            self.assertTrue(self.view.layers.active)
            first = dict(self.view.layers.tiles)
            builds = self.view.layers.tile_builds
            self.backend.t += .01
            self.view.request_frame();QTest.qWait(20)
            # Native transforms reuse the same images and scene graph items.
            shared = set(first)&set(self.view.layers.tiles)
            self.assertTrue(shared)
            for index in shared:
                self.assertIs(first[index][-1],self.view.layers.tiles[index][-1])
            # A single next tile may be prefetched on a warm frame.
            self.assertLessEqual(self.view.layers.tile_builds-builds,1)
            b.t = 170.
            self.view.request_frame();QTest.qWait(20)
            self.assertLessEqual(self.view.layers.images.bytes,24*1024**2)
            b.dark = False
            self.view.request_frame();QTest.qWait(20)
            self.assertGreater(window.grabWindow().pixelColor(100,60).red(),200)
            b.series['test'] = (np.array([0.,240.]),np.array([68.,68.]))
            self.view.request_frame();QTest.qWait(20)
            self.assertIs(self.view.layers.sources[2],b.series['test'][1])
            b.song = None
            self.view.request_frame();QTest.qWait(10)
            self.assertEqual(self.view.layers.images.bytes,0)
            self.assertFalse(self.view.layers.active)
        finally:
            self.view.setParentItem(None);window.close()

    def test_tiled_curve_pixels_remain_close_to_the_reference(self):
        self.backend.t = 50.
        self.backend.span = 20.
        self.backend.show_blocks = True
        self.backend.notes = [dict(start=51.,end=52.,duration=1.,midi=66,note='F#4'),
                              dict(start=55.,end=56.,duration=1.,midi=66,note='F#4')]
        self.backend.loop_a = 52.
        self.backend.loop_b = 55.
        window = QQuickWindow();window.resize(800,360)
        reference = PitchView();reference._controller = self.backend
        reference.setWidth(800);reference.setHeight(360)
        self.view.setParentItem(window.contentItem())
        try:
            window.show();QTest.qWait(50)
            for hover,loop in [(None,False),((30,199),False),((122,199),False),(None,True),(None,False)]:
                with self.subTest(hover=hover,loop=loop):
                    self.backend.loop = loop
                    QTest.mouseMove(window,QPoint(*hover) if hover else QPoint(799,359))
                    reference.hover_point = hover
                    self.view.request_frame();QTest.qWait(30)
                    actual = window.grabWindow().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                    expected = QImage(800,360,QImage.Format.Format_ARGB32_Premultiplied)
                    expected.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(expected);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    try:reference.paint(painter)
                    finally:painter.end()
                    # Compare the plot, excluding the independently antialiased playhead.
                    a = np.frombuffer(actual.constBits(),np.uint8).reshape(360,800,4).astype(int)
                    b = np.frombuffer(expected.constBits(),np.uint8).reshape(360,800,4).astype(int)
                    delta = abs(a[50:348,72:788,:3]-b[50:348,72:788,:3])
                    self.assertLess(float(delta.mean()),2.)
                    # Neighboring pixels at a tile boundary must not contain an empty strip.
                    for x in [72,292,512,732]:
                        self.assertLess(float(abs(a[50:348,x:x+2,:3]-b[50:348,x:x+2,:3]).mean()),3.)
                    # Empty parts of the hovered row and loop region retain their tint.
                    self.assertLessEqual(int(abs(a[202,700,:3]-b[202,700,:3]).max()),2)
                    self.assertLessEqual(int(abs(a[80,200,:3]-b[80,200,:3]).max()),2)
        finally:
            self.view.setParentItem(None);window.close()

    def test_image_cache_evicts_by_bytes(self):
        cache = ImageCache(limit=1024)
        for i in range(10):
            cache.get(i,lambda:QImage(8,8,QImage.Format.Format_ARGB32_Premultiplied))
        self.assertLessEqual(cache.bytes,1024)
        self.assertNotIn(0,cache.images)

    def test_tile_allocation_failure_releases_images_and_keeps_the_plot_visible(self):
        window = QQuickWindow();window.resize(800,360)
        self.view.setParentItem(window.contentItem())
        try:
            window.show();QTest.qWait(30)
            self.assertTrue(self.view.layers.active)
            self.backend.dark = False
            with patch.object(self.view.layers,'_image',side_effect=MemoryError('allocation')) as create:
                self.view.request_frame();self.view.request_frame()
                self.assertEqual(create.call_count,1)
            self.assertTrue(self.view.layer_allocation_failed)
            self.assertTrue(self.view.layers.statistics()['allocation_fallback'])
            self.assertFalse(self.view.layers.active)
            self.assertEqual(self.view.layers.images.bytes,0)
            QTest.qWait(30)
            image = window.grabWindow()
            self.assertFalse(image.isNull())
            self.assertGreater(image.pixelColor(100,60).red(),200)
        finally:
            self.view.setParentItem(None);window.close()


class FakePlayer:
    def __init__(self):
        self.state = QMediaPlayer.PlaybackState.StoppedState
        self.ms = 0

    def playbackState(self): return self.state
    def mediaStatus(self): return QMediaPlayer.MediaStatus.BufferedMedia
    def position(self): return self.ms
    def setPosition(self, value): self.ms = value
    def play(self): self.state = QMediaPlayer.PlaybackState.PlayingState
    def pause(self): self.state = QMediaPlayer.PlaybackState.PausedState
    def stop(self): self.state = QMediaPlayer.PlaybackState.StoppedState


class PlaybackNotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.controller = Controller(self.folder.name, bootstrap=False)
        self.controller.player = FakePlayer()
        self.controller.vocal_player = FakePlayer()
        self.controller.song = {'name': 'Test', 'duration': 120}
        self.frames = []
        self.changes = []
        self.controller.frameChanged.connect(lambda: self.frames.append(self.controller.t))
        self.controller.changed.connect(lambda: self.changes.append(self.controller.t))

    def tearDown(self):
        self.controller.shutdown()
        self.folder.cleanup()

    def play(self):
        b = self.controller
        b.player.play()
        b.playback_changed(b.player.playbackState())
        b.position(1000)
        self.frames.clear()
        self.changes.clear()

    def test_frames_do_not_invalidate_settings_or_library_state(self):
        self.play()
        b = self.controller
        b.presentation.reset(1., time.monotonic()-.2)
        b.tick()
        self.assertGreater(b.playback['position'], 1.1)
        self.assertEqual(len(self.frames), 1)
        self.assertEqual(self.changes, [])
        b.position(1210)
        self.assertEqual(len(self.frames), 1)  # Media notifications share the frame timer.

    def test_seek_and_paused_positions_notify_immediately(self):
        self.play()
        b = self.controller
        b.seek(24.5)
        self.assertEqual(b.playback['position'], 24.5)
        self.assertEqual(self.frames, [24.5])
        b.player.pause()
        b.playback_changed(b.player.playbackState())
        self.frames.clear()
        b.position(25000)
        self.assertEqual(self.frames, [25.])

    def test_pause_hide_and_restore_control_the_frame_timer(self):
        self.assertFalse(self.controller.timer.isActive())
        self.play()
        b = self.controller
        self.assertTrue(b.timer.isActive())
        b.setPresentationVisible(False)
        self.assertFalse(b.timer.isActive())
        b.position(12000)
        b.setPresentationVisible(True)
        self.assertTrue(b.timer.isActive())
        self.assertAlmostEqual(b.t, 12., delta=.02)
        b.player.pause()
        b.playback_changed(b.player.playbackState())
        self.assertFalse(b.timer.isActive())

    def test_loop_still_seeks_on_the_frame_clock(self):
        self.play()
        b = self.controller
        b.loop = True
        b.loop_a = 2.
        b.loop_b = 4.
        b.presentation.reset(4.1, time.monotonic())
        b.tick()
        self.assertEqual(b.t, 2.)
        self.assertEqual(b.player.position(), 2000)
        self.assertEqual(b.vocal_player.position(), 2000)

    def test_texture_layers_leave_chart_pointer_interactions_available(self):
        b = self.controller
        times = np.arange(0,120,.01)
        b.primary = 'rmvpe_tracked'
        b.series = {b.primary:(times,np.full(len(times),66.))}
        window = QQuickWindow();window.resize(800,360)
        view = PitchView();view.setWidth(800);view.setHeight(360)
        view.controller = b;view.setParentItem(window.contentItem())
        with patch('vocalpitchlab.audio.piano.ctypes.WinDLL', create=True):
            b.piano = Piano(b)
        piano = b.piano
        piano.handle = c_void_p(1)
        piano.send = Mock()
        try:
            window.show();QTest.qWait(40)
            self.assertTrue(view.layers.active)
            QTest.mouseClick(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(200,200))
            self.assertGreater(b.t,0)
            QTest.mousePress(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(200,200))
            self.assertIsNotNone(view.drag)
            QTest.mouseMove(window,QPoint(400,200))
            QTest.mouseRelease(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(400,200))
            self.assertIsNone(view.drag)
            self.assertTrue(b.loop)
            self.assertGreater(b.loop_b,b.loop_a)
            key = QPoint(30,200)
            QTest.mousePress(window,Qt.MouseButton.LeftButton,pos=key)
            note = piano.note
            self.assertEqual(piano.send.call_args_list,[call(0x90,note,110),call(0x91,note,110)])
            QTest.qWait(900)
            self.assertEqual(piano.note,note)
            self.assertEqual(b.preview_note,note)
            self.assertGreater(b.preview_until,time.monotonic())
            QTest.mouseMove(window,QPoint(400,200))
            self.assertEqual(piano.note,note)
            self.assertIsNone(view.drag)
            QTest.mouseRelease(window,Qt.MouseButton.LeftButton,pos=QPoint(400,200))
            self.assertEqual(piano.send.call_args_list[-2:],[call(0x80,note,0),call(0x81,note,0)])
            self.assertIsNone(piano.note)
            self.assertIsNone(b.preview_note)

            b.setPianoVolume(1.)
            self.assertEqual(piano.send.call_args_list[-2:],[call(0xB0,7,127),call(0xB1,7,90)])
            QTest.mousePress(window,Qt.MouseButton.LeftButton,pos=key)
            self.assertEqual(piano.send.call_args_list[-2:],[call(0x90,note,127),call(0x91,note,127)])
            self.app.sendEvent(window,QEvent(QEvent.Type.WindowDeactivate))
            self.assertIsNone(piano.note)
            QTest.mouseRelease(window,Qt.MouseButton.LeftButton,pos=key)

            piano.handle = c_void_p()
            piano.loading = True
            QTest.mousePress(window,Qt.MouseButton.LeftButton,pos=key)
            self.assertIsNotNone(piano.pending)
            QTest.mouseRelease(window,Qt.MouseButton.LeftButton,pos=key)
            self.assertIsNone(piano.pending)
        finally:
            view.setParentItem(None);window.close()

    def test_reduce_load_switch_unloads_the_blur_and_saves_the_setting(self):
        b = self.controller
        b.settings.update(curve=False, blocks=False)
        b.show_curve = b.show_blocks = False
        engine = create_engine(b)
        window = engine.rootObjects()[0]
        try:
            blur = window.findChild(QObject, 'sidebarBlur')
            self.assertIsNotNone(blur.property('item'))
            popup = window.findChild(QObject, 'settingsPopup')
            popup.open()
            QTest.qWait(220)
            switch = window.findChild(QObject, 'reduceLoadSwitch')
            for enabled in (True, False):
                center = switch.mapToScene(QPointF(switch.width()/2, switch.height()/2))
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center.toPoint())
                QTest.qWait(30)
                self.assertEqual(blur.property('item') is None, enabled)
                self.assertIs(json.loads(b.path.read_text(encoding='utf-8'))['settings']['reduceLoad'], enabled)
        finally:
            window.close()

    def test_qml_progress_and_window_visibility_follow_the_new_notifications(self):
        b = self.controller
        b.show_curve = b.show_blocks = False
        warnings = []
        previous_handler = qInstallMessageHandler(lambda kind, context, text: warnings.append(text) if '.qml:' in text else None)
        try:
            engine = create_engine(b)
            self.assertTrue(engine.rootObjects())
            window = engine.rootObjects()[0]
            try:
                QTest.qWait(30)
                seek_bar = window.findChild(QObject, 'seekBar')
                b.seek(24.5)
                QTest.qWait(30)
                self.assertAlmostEqual(seek_bar.property('value'), 24.5)
                self.play()
                window.setVisibility(QWindow.Visibility.Minimized)
                QTest.qWait(30)
                self.assertFalse(b.timer.isActive())
                b.position(12000)
                window.setVisibility(QWindow.Visibility.Windowed)
                QTest.qWait(30)
                self.assertTrue(b.timer.isActive())
                self.assertGreaterEqual(seek_bar.property('value'), 12.)
                self.assertEqual(warnings, [])
            finally:
                window.close()
        finally:
            qInstallMessageHandler(previous_handler)


if __name__ == '__main__':
    unittest.main()
