from __future__ import annotations

import unittest

from app.ai import model_metrics_store
from app.core import config
from app.services.ai_chat import loop_service
from app.services.results.comparison_metrics import compare_results
from app.services.results.metric_registry import CORE_RESULT_METRICS, build_metric_snapshot


class ResultsCanonicalizationTest(unittest.TestCase):
    def test_core_metric_snapshot_and_comparison_follow_registry(self) -> None:
        result_a = {
            "summary": {
                "startingBalance": 1000,
                "finalBalance": 1100,
                "totalProfit": 100,
                "totalProfitPct": 10,
                "totalTrades": 20,
                "tradesPerDay": 1.25,
                "winRate": 55,
                "profitFactor": 1.4,
                "maxDrawdown": 8,
                "tradingVolume": 5000,
            }
        }
        result_b = {
            "summary": {
                "startingBalance": 1000,
                "finalBalance": 1200,
                "totalProfit": 200,
                "totalProfitPct": 20,
                "totalTrades": 24,
                "tradesPerDay": 1.5,
                "winRate": 60,
                "profitFactor": 1.8,
                "maxDrawdown": 6,
                "tradingVolume": 6500,
            }
        }

        snapshot = build_metric_snapshot(result_a, CORE_RESULT_METRICS)
        diff = compare_results(result_a, result_b)

        self.assertEqual(tuple(snapshot.keys()), CORE_RESULT_METRICS)
        self.assertEqual(tuple(diff.keys()), CORE_RESULT_METRICS)
        extended_snapshot = build_metric_snapshot(result_a, ("trades_per_day",))
        self.assertEqual(extended_snapshot["trades_per_day"], 1.25)

    def test_canonical_paths_are_consumed_by_runtime_modules(self) -> None:
        self.assertEqual(loop_service.AI_LOOP_STATE_DIR, config.AI_LOOP_STATE_DIR)
        self.assertEqual(loop_service.AI_LOOP_STATE_FILE, config.AI_LOOP_STATE_FILE)
        self.assertEqual(model_metrics_store._METRICS_FILE, config.AI_MODEL_METRICS_FILE)
