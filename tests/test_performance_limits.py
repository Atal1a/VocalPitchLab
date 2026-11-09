import unittest
from installer.performance_limits import cpu_rate
from tests.package_playback_benchmark import distribution


class PerformanceMeasurementTests(unittest.TestCase):
    def test_core_budget_is_normalized_to_total_host_capacity(self):
        self.assertEqual(cpu_rate(.5,24),208)
        self.assertEqual(cpu_rate(1,4),2500)
        self.assertEqual(cpu_rate(24,24),10000)
        for budget in [0,-1,25]:
            with self.assertRaises(ValueError):
                cpu_rate(budget,24)

    def test_latency_summary_keeps_long_stalls(self):
        summary=distribution([16,17,18,60,150])
        self.assertEqual(summary['median_ms'],18)
        self.assertEqual(summary['max_ms'],150)
        self.assertEqual(summary['over_50_ms'],2)
        self.assertEqual(summary['over_100_ms'],1)
        self.assertIsNone(distribution([])['p95_ms'])
