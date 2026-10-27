import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from types import SimpleNamespace
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from vocalpitchlab.ui.app import PitchView


class PitchHoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.view = PitchView()
        self.view.setWidth(800)
        self.view.setHeight(360)
        self.backend = SimpleNamespace(
            song={'duration': 20}, span=10, low=60, high=84, t=0,
            state={'dark': True}, settings={'hoverNotes': True, 'liveNotes': False, 'liveCurve': False},
            show_blocks=True, show_curve=False, preview_note=None, preview_until=0,
            loop=False, notes=[], x_range=lambda: (0, 10),
            primary='test', series={'test': (np.array([0., 60.]), np.array([69., 69.]))},
            loudness=(np.array([0., 60.]), np.array([.5, .5])), curve_reliability={},
        )
        self.view._controller = self.backend
        self.matches = []
        draw = self.view.draw_block

        def capture(painter, rect, dark, selected=False):
            if selected:
                self.matches.append(rect.left())
            draw(painter, rect, dark, selected)

        self.view.draw_block = capture

    def render(self, point):
        self.matches = []
        self.view.hover_point = point
        image = QImage(800, 360, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            self.view.paint(painter)
        finally:
            painter.end()
        return image

    def block(self, start, midi=69):
        return dict(start=start, end=start+1, duration=1, midi=midi)

    def key_point(self, midi=69):
        x0, y0, width, height = self.view.geometry_values()
        return (30, y0+(self.backend.high-midi)/(self.backend.high-self.backend.low)*height)

    def test_key_hover_highlights_all_visible_matches_and_the_whole_row(self):
        self.backend.notes = [self.block(7), self.block(4), self.block(2, 70)]
        baseline = self.render(None)
        image = self.render(self.key_point())
        x0, y0, width, height = self.view.geometry_values()
        self.assertEqual(sorted(self.matches), [x0+4/10*width, x0+7/10*width])
        # The row tint continues after the final note, while neighboring rows stay unchanged.
        row = round(self.key_point()[1])
        changed = sum(image.pixel(x, row) != baseline.pixel(x, row)
                      for x in range(int(x0+10), int(x0+4/10*width-10)))
        self.assertGreater(changed, 30)
        self.assertNotEqual(image.pixel(760, row), baseline.pixel(760, row))
        adjacent_row=round(self.key_point(68)[1])
        self.assertEqual(image.pixel(760, adjacent_row), baseline.pixel(760, adjacent_row))

    def test_keyboard_hover_leave_restores_all_blocks_and_row(self):
        self.backend.notes = [self.block(4), self.block(7)]
        baseline = self.render(None)
        self.render(self.key_point())
        self.view.hoverLeaveEvent(None)
        self.assertIsNone(self.view.hover_point)
        self.assertEqual(self.render(self.view.hover_point), baseline)

    def test_offscreen_or_different_pitch_does_not_create_guide(self):
        self.backend.notes = [self.block(15), self.block(4, 70)]
        baseline = self.render(None)
        image = self.render(self.key_point())
        self.assertEqual(self.matches, [])
        self.assertEqual(image.copy(68, 50, 720, 298), baseline.copy(68, 50, 720, 298))
        self.assertNotEqual(image.copy(3, 50, 55, 298), baseline.copy(3, 50, 55, 298))

    def test_hiding_blocks_leaves_only_the_key_highlight(self):
        self.backend.notes = [self.block(4)]
        self.backend.show_blocks = False
        baseline = self.render(None)
        image = self.render(self.key_point())
        self.assertEqual(image.copy(68, 50, 720, 298), baseline.copy(68, 50, 720, 298))
        self.assertNotEqual(image.copy(3, 50, 55, 298), baseline.copy(3, 50, 55, 298))

    def test_disabling_hover_suppresses_all_hover_effects(self):
        self.backend.notes = [self.block(4)]
        self.backend.settings['hoverNotes'] = False
        self.assertEqual(self.render(self.key_point()), self.render(None))

    def test_overview_highlights_all_matches_without_rebuilding_cache(self):
        self.backend.song['duration'] = 60
        self.backend.span = 60
        self.backend.x_range = lambda: (0, 60)
        self.backend.notes = [self.block(4), self.block(40), self.block(20, 70)]
        self.render(None)
        cached = self.view.layer
        self.render(self.key_point())
        x0, y0, width, height = self.view.geometry_values()
        self.assertEqual(self.matches, [x0+4/60*width, x0+40/60*width])
        self.assertIs(self.view.layer, cached)

    def test_overview_keeps_the_pitch_curve_above_highlighted_blocks(self):
        self.backend.song['duration'] = 60
        self.backend.span = 60
        self.backend.x_range = lambda: (0, 60)
        self.backend.notes = [self.block(4)]
        self.backend.show_curve = True
        image = self.render(self.key_point())
        x0, y0, width, height = self.view.geometry_values()
        x = round(x0+4.5/60*width)
        y = round(self.key_point()[1])
        # A blue curve remains visibly brighter than the selected block's fill.
        self.assertGreater(image.pixelColor(x, y).blue(), image.pixelColor(x, y+2).blue())

    def test_note_block_hover_still_connects_back_to_keyboard(self):
        self.backend.notes = [self.block(4)]
        x0, y0, width, height = self.view.geometry_values()
        self.render((x0+4.5/10*width, self.key_point()[1]))
        self.assertEqual(self.matches, [x0+4/10*width])


if __name__ == '__main__':
    unittest.main()
