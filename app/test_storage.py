from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shutil
from concurrent.futures import ThreadPoolExecutor

from app.services import storage

FIXTURE_ZIP = Path(__file__).resolve().parents[1] / "user_data" / "backtest_results" / "backtest-result-2026-04-04_00-30-17.zip"
if not FIXTURE_ZIP.exists():
    FIXTURE_ZIP = next(
        iter(sorted((Path(__file__).resolve().parents[1] / "user_data" / "backtest_results").rglob("backtest-result-*.zip"))),
        None,
    )


class StorageTests(unittest.TestCase):
    def test_allocate_strategy_version_dir_increments_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            with patch.object(storage, "BACKTEST_RESULTS_DIR", base_dir):
                v1, p1 = storage.allocate_strategy_version_dir("MultiMa")
                v2, p2 = storage.allocate_strategy_version_dir("MultiMa")

        self.assertEqual(v1, "v1")
        self.assertEqual(v2, "v2")
        self.assertEqual(p1.name, "v1")
        self.assertEqual(p2.name, "v2")

    def test_allocate_strategy_version_dir_is_unique_across_threads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            with patch.object(storage, "BACKTEST_RESULTS_DIR", base_dir):
                def _alloc() -> str:
                    v, _ = storage.allocate_strategy_version_dir("MultiMa")
                    return v

                with ThreadPoolExecutor(max_workers=5) as pool:
                    labels = sorted(pool.map(lambda _: _alloc(), range(5)))

        self.assertEqual(labels, ["v1", "v2", "v3", "v4", "v5"])

    def test_list_runs_filters_artifacts_and_returns_compact_overview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            run_id = "20260404_010203_abcd1234"

            with patch.object(storage, "BACKTEST_RESULTS_DIR", base_dir):
                storage.save_run_meta(
                    run_id,
                    {
                        "run_id": run_id,
                        "strategy": "Diamond",
                        "status": "completed",
                        "started_at": "2026-04-04T01:02:03",
                    },
                )
                storage.save_run_results(
                    run_id,
                    {
                        "overview": {
                            "total_trades": 11,
                            "profit_total_abs": 5.0,
                            "profit_percent": 12.5,
                            "profit_factor": 1.7,
                            "win_rate": 54.55,
                            "max_drawdown": 0.08,
                            "max_drawdown_abs": 3.25,
                            "starting_balance": 40.0,
                            "final_balance": 45.0,
                        },
                        "trades": [],
                        "per_pair": [],
                        "warnings": [],
                    },
                )

                (base_dir / "MultiMa").mkdir()

                runs = storage.list_runs()

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["run_id"], run_id)
        self.assertTrue(runs[0]["has_results"])
        self.assertAlmostEqual(runs[0]["overview"]["profit_percent"], 12.5, places=4)
        self.assertAlmostEqual(runs[0]["overview"]["max_drawdown"], 0.08, places=6)

    def test_load_run_results_rehydrates_from_local_artifact(self) -> None:
        if not FIXTURE_ZIP:
            self.skipTest("No backtest zip fixture found in user_data/backtest_results.")
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            run_id = "20260404_111111_deadbeef"
            run_dir = base_dir / run_id
            run_dir.mkdir(parents=True)
            shutil.copy2(FIXTURE_ZIP, run_dir / FIXTURE_ZIP.name)

            with patch.object(storage, "BACKTEST_RESULTS_DIR", base_dir):
                results = storage.load_run_results(run_id)

                self.assertIsNotNone(results)
                self.assertIn("periodic_breakdown", results)
                self.assertTrue((run_dir / "parsed_results.json").exists())
                self.assertTrue(results["raw_artifact"]["available"])
                self.assertGreater(len(results["trades"]), 0)

    def test_load_run_raw_payload_falls_back_to_parsed_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            run_id = "20260404_222222_deadbeef"

            with patch.object(storage, "BACKTEST_RESULTS_DIR", base_dir):
                storage.save_run_results(
                    run_id,
                    {
                        "overview": {
                            "total_trades": 2,
                            "profit_total": 0.1,
                            "profit_total_abs": 5.0,
                            "profit_percent": 10.0,
                            "starting_balance": 50.0,
                            "final_balance": 55.0,
                        },
                        "trades": [],
                        "per_pair": [],
                        "warnings": [],
                    },
                )

                payload = storage.load_run_raw_payload(run_id)

        self.assertIsNotNone(payload)
        self.assertTrue(payload["raw_artifact_missing"])
        self.assertEqual(payload["data_source"], "parsed_results")
        self.assertIn("overview", payload["payload"])

    def test_load_run_results_normalizes_legacy_stringified_pair_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            run_id = "20260404_333333_deadbeef"

            with patch.object(storage, "BACKTEST_RESULTS_DIR", base_dir):
                storage.save_run_meta(
                    run_id,
                    {
                        "run_id": run_id,
                        "strategy": "MultiMa",
                        "status": "completed",
                        "started_at": "2026-04-04T03:33:33",
                    },
                )
                run_dir = base_dir / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "parsed_results.json").write_text(
                    """
                    {
                      "overview": {
                        "best_pair": "{'key': 'ETH/USDT', 'profit_total_pct': 15.42}",
                        "worst_pair": "{'pair': 'BTC/USDT', 'profit_total_pct': -3.1}"
                      },
                      "summary": {
                        "bestPair": "{'key': 'ETH/USDT', 'profit_total_pct': 15.42}",
                        "worstPair": "{'pair': 'BTC/USDT', 'profit_total_pct': -3.1}"
                      },
                      "summary_metrics": {},
                      "risk_metrics": {},
                      "periodic_breakdown": {},
                      "raw_artifact": {"available": false},
                      "diagnostics": {}
                    }
                    """.strip()
                )

                results = storage.load_run_results(run_id)

        self.assertIsNotNone(results)
        self.assertEqual(results["summary"]["bestPair"], "ETH/USDT")
        self.assertEqual(results["summary"]["worstPair"], "BTC/USDT")
        self.assertEqual(results["overview"]["best_pair"], "ETH/USDT")
        self.assertEqual(results["overview"]["worst_pair"], "BTC/USDT")


if __name__ == "__main__":
    unittest.main()
