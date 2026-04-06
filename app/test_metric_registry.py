from __future__ import annotations

import unittest

from app.services.results.comparison_metrics import compare_overviews
from app.services.results.metric_registry import build_metric_snapshot


class MetricRegistryTests(unittest.TestCase):
    def test_build_metric_snapshot_normalizes_percent_rate_and_drawdown_values(self) -> None:
        result = {
            "overview": {
                "profit_total": 0.1542183016,
                "profit_total_abs": 7.71091508,
                "profit_percent": 15.4218,
                "win_rate": 0.4154,
                "max_drawdown": 0.0753117816,
                "profit_factor": 1.5211646498,
                "starting_balance": 50.0,
                "final_balance": 57.71091508,
                "total_trades": 21,
            }
        }

        snapshot = build_metric_snapshot(result)

        self.assertAlmostEqual(snapshot["profit_percent"], 15.4218, places=4)
        self.assertAlmostEqual(snapshot["win_rate"], 41.54, places=2)
        self.assertAlmostEqual(snapshot["max_drawdown"], 7.53117816, places=4)
        self.assertAlmostEqual(snapshot["profit_total_abs"], 7.71091508, places=4)
        self.assertEqual(snapshot["total_trades"], 21)

    def test_compare_overviews_uses_registry_normalization(self) -> None:
        overview_a = {
            "profit_total": 0.10,
            "profit_total_abs": 5.0,
            "win_rate": 0.50,
            "max_drawdown": 0.08,
            "profit_factor": 1.2,
            "starting_balance": 50.0,
            "final_balance": 55.0,
            "total_trades": 10,
        }
        overview_b = {
            "profit_total": 0.20,
            "profit_total_abs": 10.0,
            "win_rate": 0.60,
            "max_drawdown": 0.10,
            "profit_factor": 1.5,
            "starting_balance": 50.0,
            "final_balance": 60.0,
            "total_trades": 12,
        }

        diff = compare_overviews(overview_a, overview_b)

        self.assertAlmostEqual(diff["win_rate"]["a"], 50.0, places=2)
        self.assertAlmostEqual(diff["win_rate"]["b"], 60.0, places=2)
        self.assertAlmostEqual(diff["win_rate"]["diff"], 10.0, places=2)
        self.assertAlmostEqual(diff["max_drawdown"]["a"], 8.0, places=2)
        self.assertAlmostEqual(diff["max_drawdown"]["b"], 10.0, places=2)
        self.assertAlmostEqual(diff["max_drawdown"]["diff"], 2.0, places=2)


if __name__ == "__main__":
    unittest.main()
