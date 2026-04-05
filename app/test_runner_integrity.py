from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import shutil

from app.services import runner

FIXTURE_ZIP = Path(__file__).resolve().parents[1] / "user_data" / "backtest_results" / "backtest-result-2026-04-04_00-30-17.zip"


class RunnerIntegrityTests(unittest.TestCase):
    def test_backtest_worker_fails_when_no_run_local_artifact_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            run_id = "20260405_000000_deadbeef"
            meta = {"run_id": run_id}

            fake_proc = MagicMock()
            fake_proc.stdout = []
            fake_proc.returncode = 0

            with (
                patch.object(runner.subprocess, "Popen", return_value=fake_proc),
                patch.object(runner, "find_run_local_result_artifact", return_value={"available": False}),
                patch.object(runner, "parse_backtest_results") as parse_mock,
                patch.object(runner, "save_run_results") as save_results_mock,
                patch.object(runner, "set_process"),
                patch.object(runner, "remove_process"),
                patch.object(runner, "append_log") as append_log_mock,
                patch.object(runner, "set_status") as set_status_mock,
                patch.object(runner, "get_status", return_value="failed"),
                patch.object(runner, "save_run_meta"),
                patch.object(runner, "save_run_logs"),
                patch.object(runner, "get_logs", return_value=[]),
            ):
                runner._backtest_worker(run_id, ["python", "-m", "freqtrade", "backtesting"], run_dir, meta)

            parse_mock.assert_not_called()
            save_results_mock.assert_not_called()
            self.assertTrue(any(call.args[1] == "failed" for call in set_status_mock.call_args_list))
            self.assertTrue(
                any(
                    "no attributable result artifact" in str(call.args[1]).lower()
                    for call in append_log_mock.call_args_list
                )
            )

    def test_backtest_worker_imports_fresh_matching_global_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "backtest_results"
            base_dir.mkdir(parents=True)
            run_dir = Path(tmpdir) / "run_dir"
            run_dir.mkdir(parents=True)
            run_id = "20260405_010101_feedbeef"
            meta = {
                "run_id": run_id,
                "strategy_class": "MultiMaScalp2026Base",
                "timeframe": "5m",
                "started_at": "",
            }

            artifact_name = FIXTURE_ZIP.name
            artifact_path = base_dir / artifact_name
            shutil.copy2(FIXTURE_ZIP, artifact_path)
            meta_path = base_dir / artifact_name.replace(".zip", ".meta.json")
            meta_path.write_text('{"MultiMaScalp2026Base":{"timeframe":"5m"}}')
            (base_dir / ".last_result.json").write_text(f'{{"latest_backtest":"{artifact_name}"}}')

            fake_proc = MagicMock()
            fake_proc.stdout = []
            fake_proc.returncode = 0

            parsed_payload = {
                "summary": {},
                "overview": {},
                "summary_metrics": {},
                "balance_metrics": {},
                "risk_metrics": {},
                "run_metadata": {},
                "config_snapshot": {},
                "diagnostics": {},
                "trades": [],
                "per_pair": [],
                "periodic_breakdown": {},
                "raw_artifact": {"available": True, "run_local": True, "file_name": artifact_name},
            }

            with (
                patch.object(runner, "BACKTEST_RESULTS_DIR", base_dir),
                patch.object(runner.subprocess, "Popen", return_value=fake_proc),
                patch.object(runner, "parse_backtest_results", return_value=parsed_payload) as parse_mock,
                patch.object(runner, "save_run_results") as save_results_mock,
                patch.object(runner, "set_process"),
                patch.object(runner, "remove_process"),
                patch.object(runner, "append_log"),
                patch.object(runner, "set_status") as set_status_mock,
                patch.object(runner, "get_status", return_value="completed"),
                patch.object(runner, "save_run_meta"),
                patch.object(runner, "save_run_logs"),
                patch.object(runner, "get_logs", return_value=[]),
            ):
                runner._backtest_worker(run_id, ["python", "-m", "freqtrade", "backtesting"], run_dir, meta)

            self.assertTrue((run_dir / artifact_name).exists())
            self.assertTrue((run_dir / artifact_name.replace(".zip", ".meta.json")).exists())
            parse_mock.assert_called_once()
            save_results_mock.assert_called_once()
            self.assertTrue(any(call.args[1] == "completed" for call in set_status_mock.call_args_list))


if __name__ == "__main__":
    unittest.main()
