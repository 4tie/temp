from __future__ import annotations

import unittest

from app.services.strategy_scanner import get_strategy_params


class StrategyScannerTests(unittest.TestCase):
    def test_get_strategy_params_extracts_spaces_and_defaults_from_ast(self) -> None:
        params = {param["name"]: param for param in get_strategy_params("Diamond")}

        self.assertEqual(params["buy_fast_key"]["default"], "high")
        self.assertEqual(params["buy_slow_key"]["default"], "volume")
        self.assertEqual(params["sell_fast_key"]["default"], "high")
        self.assertEqual(params["sell_slow_key"]["default"], "low")
        self.assertEqual(params["sell_fast_key"]["space"], "sell")
        self.assertEqual(params["sell_vertical_push"]["space"], "sell")

    def test_get_strategy_params_handles_non_literal_int_bounds(self) -> None:
        # MultiMa uses variable bounds (e.g. count_max), which are not AST literals.
        params = get_strategy_params("MultiMa")
        self.assertTrue(len(params) > 0)


if __name__ == "__main__":
    unittest.main()
