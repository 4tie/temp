from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.strategies import get_strategy_editable_context


_SOURCE = """from freqtrade.strategy import BooleanParameter, IntParameter, IStrategy


class MultiMa(IStrategy):
    buy_length = IntParameter(1, 10, default=5, space="buy")
    sell_enabled = BooleanParameter(default=True, space="sell")
"""


class StrategySnapshotServiceTests(unittest.TestCase):
    def test_get_strategy_editable_context_merges_source_sidecar_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "MultiMa.py").write_text(_SOURCE, encoding="utf-8")
            (root / "MultiMa.json").write_text(
                json.dumps(
                    {
                        "strategy_name": "MultiMa",
                        "params": {
                            "buy": {"buy_length": 7},
                            "sell": {"sell_enabled": False},
                            "custom": {"orphan_value": 99},
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            context = get_strategy_editable_context("MultiMa", strategies_dir=root)

        self.assertEqual(Path(context["source_path"]).name, "MultiMa.py")
        self.assertEqual(Path(context["sidecar_path"]).name, "MultiMa.json")
        self.assertEqual(context["current_values"]["buy_length"], 7)
        self.assertEqual(context["current_values"]["sell_enabled"], False)
        self.assertEqual(context["validation"]["source_syntax_ok"], True)
        self.assertEqual(context["validation"]["sidecar_valid_json"], True)
        self.assertIn("orphan_value", context["validation"]["unknown_sidecar_keys"])

        params = {item["name"]: item for item in context["parameters"]}
        self.assertEqual(params["buy_length"]["default"], 5)
        self.assertEqual(params["buy_length"]["value"], 7)
        self.assertEqual(params["sell_enabled"]["value"], False)


if __name__ == "__main__":
    unittest.main()
