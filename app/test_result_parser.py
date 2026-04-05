from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from app.services.result_normalizer import normalize_backtest_result
from app.services.result_parser import parse_backtest_results


FIXTURE_ZIP = Path(__file__).resolve().parents[1] / "user_data" / "backtest_results" / "backtest-result-2026-04-04_00-30-17.zip"
if not FIXTURE_ZIP.exists():
    FIXTURE_ZIP = next(
        iter(sorted((Path(__file__).resolve().parents[1] / "user_data" / "backtest_results").rglob("backtest-result-*.zip"))),
        None,
    )


class ResultParserTests(unittest.TestCase):
    def test_parse_backtest_results_extracts_rich_sections(self) -> None:
        if not FIXTURE_ZIP:
            self.skipTest("No backtest zip fixture found in user_data/backtest_results.")
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            shutil.copy2(FIXTURE_ZIP, run_dir / FIXTURE_ZIP.name)

            parsed = parse_backtest_results(run_dir)
            normalized = normalize_backtest_result(parsed)

        self.assertTrue(parsed["strategy_name"])
        self.assertIn("cagr", parsed["summary_metrics"])
        self.assertIn("max_relative_drawdown", parsed["risk_metrics"])
        self.assertIn("stoploss", parsed["config_snapshot"])
        self.assertIn("day", parsed["periodic_breakdown"])
        self.assertTrue(parsed["raw_artifact"]["available"])
        self.assertGreater(len(parsed["trades"]), 50)
        self.assertGreater(len(parsed["results_per_enter_tag"]), 0)
        self.assertGreater(len(parsed["mix_tag_stats"]), 0)
        self.assertGreater(len(parsed["exit_reason_summary"]), 0)

        self.assertIsInstance(normalized["summary"]["cagr"], float)
        self.assertIsInstance(normalized["summary"]["winRate"], float)
        self.assertIsInstance(normalized["risk_metrics"]["max_relative_drawdown"], float)
        self.assertIsInstance(normalized["results_per_enter_tag"][0]["winrate"], float)
        self.assertIn("cumulative_profit", normalized["periodic_breakdown"]["day"][0])


if __name__ == "__main__":
    unittest.main()
