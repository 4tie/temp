from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class StrategiesRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_save_source_valid_python_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_dir = Path(tmpdir)
            source_path = strategy_dir / "MultiMa.py"
            source_path.write_text("class MultiMa:\n    pass\n", encoding="utf-8")

            body = {"source": "class MultiMa:\n    def answer(self):\n        return 42\n"}
            with patch("app.routers.strategies.STRATEGIES_DIR", strategy_dir):
                response = self.client.post("/strategies/MultiMa/source", json=body)

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["strategy"], "MultiMa")
            self.assertEqual(payload["bytes_written"], len(body["source"].encode("utf-8")))
            self.assertEqual(source_path.read_text(encoding="utf-8"), body["source"])

    def test_save_source_invalid_python_returns_400_and_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_dir = Path(tmpdir)
            source_path = strategy_dir / "MultiMa.py"
            original = "class MultiMa:\n    pass\n"
            source_path.write_text(original, encoding="utf-8")

            with patch("app.routers.strategies.STRATEGIES_DIR", strategy_dir):
                response = self.client.post(
                    "/strategies/MultiMa/source",
                    json={"source": "class MultiMa(\n    pass\n"},
                )

            self.assertEqual(response.status_code, 400)
            self.assertIn("Python syntax error", response.json().get("detail", ""))
            self.assertEqual(source_path.read_text(encoding="utf-8"), original)

    def test_save_source_rejects_invalid_strategy_name(self) -> None:
        response = self.client.post(
            "/strategies/MultiMa./source",
            json={"source": "print('x')\n"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid strategy name", response.json().get("detail", ""))

    def test_save_source_missing_file_returns_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_dir = Path(tmpdir)
            with patch("app.routers.strategies.STRATEGIES_DIR", strategy_dir):
                response = self.client.post(
                    "/strategies/MultiMa/source",
                    json={"source": "class MultiMa:\n    pass\n"},
                )

            self.assertEqual(response.status_code, 404)
            self.assertIn("Strategy source not found", response.json().get("detail", ""))

    def test_get_params_uses_editable_context_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_dir = Path(tmpdir)
            (strategy_dir / "MultiMa.py").write_text(
                "from freqtrade.strategy import IntParameter, IStrategy\n"
                "class MultiMa(IStrategy):\n"
                "    buy_length = IntParameter(1, 10, default=5, space='buy')\n",
                encoding="utf-8",
            )
            (strategy_dir / "MultiMa.json").write_text(
                json.dumps({"strategy_name": "MultiMa", "params": {"buy": {"buy_length": 8}}}, indent=2),
                encoding="utf-8",
            )

            with patch("app.routers.strategies.STRATEGIES_DIR", strategy_dir):
                response = self.client.get("/strategies/MultiMa/params")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["strategy"], "MultiMa")
            self.assertEqual(payload["current_values"]["buy_length"], 8)
            self.assertTrue(payload["validation"]["source_syntax_ok"])
            params = {param["name"]: param for param in payload["parameters"]}
            self.assertEqual(params["buy_length"]["value"], 8)

    def test_save_params_writes_nested_sidecar_using_metadata_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_dir = Path(tmpdir)
            (strategy_dir / "MultiMa.py").write_text(
                "from freqtrade.strategy import BooleanParameter, IntParameter, IStrategy\n"
                "class MultiMa(IStrategy):\n"
                "    buy_length = IntParameter(1, 10, default=5, space='buy')\n"
                "    sell_enabled = BooleanParameter(default=True, space='sell')\n",
                encoding="utf-8",
            )

            with patch("app.routers.strategies.STRATEGIES_DIR", strategy_dir):
                response = self.client.post(
                    "/strategies/MultiMa/params",
                    json={"parameters": {"buy_length": 9, "sell_enabled": False}},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["ok"])
            sidecar = json.loads((strategy_dir / "MultiMa.json").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["params"]["buy"]["buy_length"], 9)
            self.assertEqual(sidecar["params"]["sell"]["sell_enabled"], False)


if __name__ == "__main__":
    unittest.main()
