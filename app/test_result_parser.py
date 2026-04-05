from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from app.services.result_normalizer import normalize_backtest_result
from app.services.result_parser import parse_backtest_results


FIXTURE_ZIP = Path(__file__).resolve().parents[1] / "user_data" / "backtest_results" / "backtest-result-2026-04-04_00-30-17.zip"


class ResultParserTests(unittest.TestCase):
    def test_parse_backtest_results_extracts_rich_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            shutil.copy2(FIXTURE_ZIP, run_dir / FIXTURE_ZIP.name)

            parsed = parse_backtest_results(run_dir)
            normalized = normalize_backtest_result(parsed)

        self.assertEqual(parsed["strategy_name"], "MultiMaScalp2026Base")
        self.assertIn("cagr", parsed["summary_metrics"])
        self.assertIn("max_relative_drawdown", parsed["risk_metrics"])
        self.assertIn("stoploss", parsed["config_snapshot"])
        self.assertIn("day", parsed["periodic_breakdown"])
        self.assertTrue(parsed["raw_artifact"]["available"])
        self.assertGreater(len(parsed["trades"]), 50)
        self.assertGreater(len(parsed["results_per_enter_tag"]), 0)
        self.assertGreater(len(parsed["mix_tag_stats"]), 0)
        self.assertGreater(len(parsed["exit_reason_summary"]), 0)

        self.assertAlmostEqual(normalized["summary"]["cagr"], 20.6, places=1)
        self.assertAlmostEqual(normalized["summary"]["winRate"], 52.53, places=2)
        self.assertAlmostEqual(normalized["risk_metrics"]["max_relative_drawdown"], 4.18, places=1)
        self.assertAlmostEqual(normalized["results_per_enter_tag"][0]["winrate"], 52.53, places=2)
        self.assertIn("cumulative_profit", normalized["periodic_breakdown"]["day"][0])


if __name__ == "__main__":
    unittest.main()
