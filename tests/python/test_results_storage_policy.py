from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.results.result_service import load_stored_backtest_results
from app.services.runs.base_run_service import run_results_path


class StoredBacktestResultPolicyTest(unittest.TestCase):
    def test_load_stored_results_returns_saved_result_when_no_local_artifact_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            run_results_path(run_dir).write_text(
                json.dumps(
                    {
                        "summary": {
                            "startingBalance": 1000,
                            "finalBalance": 1100,
                            "totalProfit": 100,
                            "totalProfitPct": 10,
                            "totalTrades": 12,
                            "winRate": 58,
                            "profitFactor": 1.4,
                            "maxDrawdown": 6,
                            "tradingVolume": 4200,
                        }
                    }
                )
            )

            result = load_stored_backtest_results(run_dir)

        self.assertIsNotNone(result)
        self.assertEqual(result["summary"]["finalBalance"], 1100.0)
        self.assertEqual(result["overview"]["total_trades"], 12)
        self.assertIn("result_metrics", result)

    def test_load_stored_results_rehydrates_incomplete_saved_result_from_local_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            run_results_path(run_dir).write_text(
                json.dumps(
                    {
                        "summary": {},
                        "raw_artifact": {"available": True},
                    }
                )
            )
            (run_dir / "result.json").write_text("{}")

            reparsed = {
                "summary": {
                    "startingBalance": 1000,
                    "finalBalance": 1175,
                    "totalProfit": 175,
                    "totalProfitPct": 17.5,
                    "totalTrades": 16,
                    "winRate": 62,
                    "profitFactor": 1.7,
                    "maxDrawdown": 4,
                    "tradingVolume": 5200,
                },
                "raw_artifact": {"available": True, "run_local": True},
            }
            persisted: list[dict[str, object]] = []

            with patch("app.services.results.result_service.parse_backtest_results", return_value=reparsed):
                result = load_stored_backtest_results(
                    run_dir,
                    persist_normalized=persisted.append,
                )

        self.assertIsNotNone(result)
        self.assertEqual(len(persisted), 1)
        self.assertEqual(result["summary"]["finalBalance"], 1175.0)
        self.assertEqual(persisted[0]["summary"]["finalBalance"], 1175.0)
        self.assertEqual(result["result_metrics"]["final_balance"], 1175.0)
