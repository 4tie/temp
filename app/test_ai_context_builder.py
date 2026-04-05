from __future__ import annotations

import unittest
from unittest.mock import patch

from app.ai import context_builder


class ContextBuilderTests(unittest.TestCase):
    def test_build_context_snapshot_injects_goal_and_redacts_secret_fields(self) -> None:
        backtest = {
            "run_id": "run-1",
            "strategy": "MultiMa",
            "timeframe": "5m",
            "overview": {
                "profit_percent": 12.5,
                "profit_factor": 1.7,
                "win_rate": 0.53,
                "max_drawdown": 8.2,
                "total_trades": 101,
            },
            "per_pair": [{"pair": "ETH/USDT", "profit_percent": 11.1}],
            "warnings": ["sample warning"],
        }

        with (
            patch.object(context_builder, "latest_completed_run_id", return_value="run-1"),
            patch.object(context_builder, "_build_backtest_snapshot", return_value=backtest),
            patch.object(context_builder, "_load_strategy_sidecar", return_value={"api_key": "secret", "window": 20}),
            patch.object(context_builder, "_load_relevant_settings", return_value={"active_config": {"strategy": "MultiMa"}}),
        ):
            snapshot = context_builder.build_context_snapshot("maximize_profit")
            bundle = context_builder.build_context_bundle("maximize_profit")

        self.assertEqual(snapshot.get("goal_id"), "maximize_profit")
        self.assertEqual(snapshot.get("goal_label"), "Maximize Profit")
        self.assertEqual(snapshot.get("context_run_id"), "run-1")
        self.assertEqual(snapshot.get("strategy_config", {}).get("api_key"), "***REDACTED***")

        text = bundle.context_text
        self.assertIn("User goal: Maximize Profit", text)
        self.assertIn("Backtest context:", text)
        self.assertIn("Key metrics:", text)
        self.assertIn("Strategy config JSON:", text)
        self.assertIn("Relevant settings JSON:", text)


if __name__ == "__main__":
    unittest.main()
