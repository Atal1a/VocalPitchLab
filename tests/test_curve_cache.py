from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from vocalpitchlab.analysis import presentation_results as results


class CurveCacheTests(unittest.TestCase):
    def test_round_trip_and_rebuild_after_content_changes_or_truncation(self):
        with TemporaryDirectory() as folder:
            curve=Path(folder)/'pitch.csv'
            source='time_seconds,midi_float,rmvpe_max_salience\n0,60.123456789012,0.9\n0.01,,0.001\n'
            curve.write_text(source, encoding='utf-8-sig')
            expected=results.parse_curve(curve.read_bytes())
            results.read_curve(curve)
            with patch.object(results,'parse_curve',side_effect=AssertionError('Cache must bypass CSV parsing')):
                for wanted,actual in zip(expected,results.read_curve(curve)):
                    np.testing.assert_array_equal(wanted,actual)
            curve.write_text(source.replace('60.', '61.'), encoding='utf-8-sig')
            self.assertAlmostEqual(results.read_curve(curve)[1][0],61.123456789012)
            curve.with_suffix('.curve.npz').write_bytes(b'PK\x03\x04')
            for wanted,actual in zip(results.parse_curve(curve.read_bytes()),results.read_curve(curve)):
                np.testing.assert_array_equal(wanted,actual)
            with patch.object(results,'parse_curve',side_effect=AssertionError('Truncated cache was not replaced')):
                results.read_curve(curve)

    def test_unknown_binary_version_does_not_override_csv(self):
        with TemporaryDirectory() as folder:
            curve=Path(folder)/'pitch.csv'
            curve.write_text('time_seconds,midi_float,periodicity_or_probability\n0,60,1\n', encoding='utf-8')
            results.read_curve(curve)
            with patch.object(results,'CURVE_CACHE_VERSION',2), patch.object(results,'parse_curve',wraps=results.parse_curve) as parse:
                results.read_curve(curve)
                parse.assert_called_once()
