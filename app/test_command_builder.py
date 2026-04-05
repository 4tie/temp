from __future__ import annotations

import unittest

from app.services.command_builder import build_backtest_command, build_download_data_command


class CommandBuilderTests(unittest.TestCase):
    def test_build_backtest_command_uses_backtest_directory(self) -> None:
        cmd = build_backtest_command(
            strategy="Diamond",
            pairs=["ETH/USDT"],
            timeframe="5m",
            timerange="20251001-20260321",
            strategy_params={},
            backtest_directory="user_data/backtest_results/test_run",
        )

        self.assertIn("--backtest-directory", cmd)
        self.assertIn("user_data/backtest_results/test_run", cmd)
        self.assertNotIn("--export-filename", cmd)

    def test_build_download_data_command_uses_timeframes_without_prepend(self) -> None:
        cmd = build_download_data_command(
            pairs=["ETH/USDT"],
            timeframe="5m",
            timerange="20251001-20260321",
        )

        self.assertIn("--timeframes", cmd)
        self.assertIn("5m", cmd)
        self.assertNotIn("--prepend", cmd)
        self.assertNotIn("--timeframe", cmd)
        self.assertIn("--timerange", cmd)
        tr_idx = cmd.index("--timerange") + 1
        self.assertEqual(cmd[tr_idx], "20251001-20260321")


if __name__ == "__main__":
    unittest.main()
