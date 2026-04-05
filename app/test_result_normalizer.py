from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.services.result_normalizer import normalize_backtest_result


FIXTURE_PATH = Path(__file__).with_name("test_fixture_sample_parsed_result.json")


class ResultNormalizerTests(unittest.TestCase):
    def test_normalize_parsed_result_builds_summary_and_trade_aliases(self) -> None:
        raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        normalized = normalize_backtest_result(raw)

        self.assertAlmostEqual(normalized["summary"]["maxDrawdown"], 7.53117816, places=4)
        self.assertAlmostEqual(normalized["summary"]["totalProfitPct"], 15.4218, places=4)
        self.assertAlmostEqual(normalized["summary"]["profitFactor"], 1.5211646498, places=4)
        self.assertAlmostEqual(normalized["summary"]["winRate"], 41.54, places=2)
        self.assertIn("sharpeRatio", normalized["summary"])
        self.assertIn("sharpe_ratio", normalized["summary"])
        self.assertIn("sharpe_ratio", normalized["overview"])
        self.assertAlmostEqual(normalized["overview"]["profit_percent"], 15.4218, places=4)
        self.assertAlmostEqual(normalized["overview"]["win_rate"], 41.54, places=2)
        self.assertAlmostEqual(normalized["overview"]["max_drawdown"], 0.0753117816, places=6)

        trade = normalized["trades"][0]
        self.assertEqual(trade["openDate"], "2025-10-05 01:55:00+00:00")
        self.assertEqual(trade["closeDate"], "2025-10-05 05:50:00+00:00")
        self.assertEqual(trade["exitReason"], "exit_signal")
        self.assertAlmostEqual(trade["profit"], 0.72418098, places=6)
        self.assertAlmostEqual(trade["profitPct"], 1.4525305571, places=6)
        self.assertAlmostEqual(trade["minRate"], 4480.0, places=4)
        self.assertAlmostEqual(trade["maxRate"], 4588.98, places=4)

    def test_normalize_parsed_result_repairs_overscaled_profit_percent(self) -> None:
        raw = {
            "overview": {
                "total_trades": 10,
                "profit_total": -0.487895,
                "profit_total_abs": -24.39475,
                "profit_percent": -4878.95,
                "win_rate": 0.4,
                "max_drawdown": 0.125,
                "starting_balance": 50.0,
                "final_balance": 25.60525,
            },
            "trades": [
                {"profit_abs": -2.0, "profit_pct": -4.0},
                {"profit_abs": 1.0, "profit_pct": 2.0},
            ],
            "per_pair": [
                {
                    "pair": "ETH/USDT",
                    "trades": 10,
                    "profit_total": -0.487895,
                    "profit_percent": -4878.95,
                    "profit_total_abs": -24.39475,
                }
            ],
        }

        normalized = normalize_backtest_result(raw)

        self.assertAlmostEqual(normalized["summary"]["totalProfitPct"], -48.7895, places=4)
        self.assertAlmostEqual(normalized["overview"]["profit_percent"], -48.7895, places=4)
        self.assertAlmostEqual(normalized["overview"]["win_rate"], 40.0, places=4)
        self.assertAlmostEqual(normalized["summary"]["maxDrawdown"], 12.5, places=4)
        self.assertAlmostEqual(normalized["per_pair"][0]["profit_percent"], -48.7895, places=4)

    def test_normalize_parsed_result_extracts_pair_keys_from_object_fields(self) -> None:
        raw = {
            "summary": {
                "bestPair": {"key": "ETH/USDT", "profit_total_pct": 15.42},
                "worstPair": {"pair": "BTC/USDT", "profit_total_pct": -3.1},
            },
            "run_metadata": {
                "best_pair": {"key": "ETH/USDT"},
                "worst_pair": {"pair": "BTC/USDT"},
            },
        }

        normalized = normalize_backtest_result(raw)

        self.assertEqual(normalized["summary"]["bestPair"], "ETH/USDT")
        self.assertEqual(normalized["summary"]["worstPair"], "BTC/USDT")
        self.assertEqual(normalized["overview"]["best_pair"], "ETH/USDT")
        self.assertEqual(normalized["overview"]["worst_pair"], "BTC/USDT")

    def test_normalize_parsed_result_extracts_pair_keys_from_stringified_objects(self) -> None:
        raw = {
            "summary": {
                "bestPair": "{'key': 'ETH/USDT', 'profit_total_pct': 15.42}",
                "worstPair": "{'pair': 'BTC/USDT', 'profit_total_pct': -3.1}",
            },
            "overview": {
                "best_pair": "{'key': 'ETH/USDT', 'profit_total_pct': 15.42}",
                "worst_pair": "{'pair': 'BTC/USDT', 'profit_total_pct': -3.1}",
            },
        }

        normalized = normalize_backtest_result(raw)

        self.assertEqual(normalized["summary"]["bestPair"], "ETH/USDT")
        self.assertEqual(normalized["summary"]["worstPair"], "BTC/USDT")
        self.assertEqual(normalized["overview"]["best_pair"], "ETH/USDT")
        self.assertEqual(normalized["overview"]["worst_pair"], "BTC/USDT")

    def test_missing_critical_metrics_are_not_forced_to_zero_and_emit_warnings(self) -> None:
        raw = {
            "overview": {"total_trades": 4},
            "summary_metrics": {},
            "run_metadata": {},
            "diagnostics": {},
        }

        normalized = normalize_backtest_result(raw)

        self.assertIsNone(normalized["summary"]["avgProfitPct"])
        self.assertIsNone(normalized["summary"]["totalProfitShort"])
        self.assertIsNone(normalized["summary"]["totalProfitShortPct"])
        warnings = normalized["diagnostics"]["warnings"]
        self.assertTrue(any("Missing metric: summary.avgProfitPct" in warning for warning in warnings))
        self.assertTrue(any("Missing metric: balance.profit_total_short_abs" in warning for warning in warnings))

    def test_true_zero_short_metrics_remain_zero(self) -> None:
        raw = {
            "balance_metrics": {
                "starting_balance": 100.0,
                "final_balance": 102.0,
                "profit_total_short_abs": 0.0,
                "profit_total_short": 0.0,
                "profit_total_long_abs": 2.0,
                "profit_total_long": 0.02,
            },
            "run_metadata": {"trade_count_short": 0},
            "summary_metrics": {"profit_mean_pct": 0.5},
            "diagnostics": {},
        }

        normalized = normalize_backtest_result(raw)

        self.assertEqual(normalized["summary"]["totalProfitShort"], 0.0)
        self.assertEqual(normalized["summary"]["totalProfitShortPct"], 0.0)
        self.assertEqual(normalized["balance_metrics"]["profit_total_short_abs"], 0.0)
        self.assertEqual(normalized["balance_metrics"]["profit_total_short_pct"], 0.0)

    def test_metric_mismatches_are_corrected_with_diagnostics_warning(self) -> None:
        raw = {
            "summary": {
                "totalProfitPct": 9900.0,
                "avgProfitPct": 9.0,
            },
            "balance_metrics": {
                "starting_balance": 100.0,
                "final_balance": 110.0,
                "profit_total_long_abs": 12.0,
                "profit_total_long": 0.12,
                "profit_total_short_abs": -2.0,
                "profit_total_short": -0.02,
                "profit_total_short_pct": -25.0,
            },
            "summary_metrics": {
                "profit_mean_pct": 1.5,
            },
            "run_metadata": {"trade_count_short": 2},
            "diagnostics": {},
        }

        normalized = normalize_backtest_result(raw)

        self.assertAlmostEqual(normalized["summary"]["totalProfitPct"], 10.0, places=4)
        self.assertAlmostEqual(normalized["summary"]["avgProfitPct"], 1.5, places=4)
        self.assertAlmostEqual(normalized["balance_metrics"]["profit_total_short_pct"], -2.0, places=4)
        warnings = normalized["diagnostics"]["warnings"]
        self.assertTrue(any("Corrected metric mismatch: summary.avgProfitPct" in warning for warning in warnings))
        self.assertTrue(any("Corrected metric mismatch: balance.profit_total_short_pct" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
