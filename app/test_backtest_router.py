from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class BacktestRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_run_backtest_rejects_missing_selected_pair_data(self) -> None:
        coverage = [
            {
                "pair": "ETH/USDT",
                "timeframe": "5m",
                "exchange": "binance",
                "available": True,
                "file_size": 123,
                "file_path": "/tmp/ETH_USDT-5m.json",
            },
            {
                "pair": "BTC/USDT",
                "timeframe": "5m",
                "exchange": "binance",
                "available": False,
                "file_size": 0,
                "file_path": "",
            },
        ]

        with patch("app.routers.backtest.check_data_coverage", return_value=coverage), patch(
            "app.routers.backtest.start_backtest"
        ) as mock_start, patch("app.routers.backtest.save_last_config") as mock_save:
            response = self.client.post(
                "/run",
                json={
                    "strategy": "Diamond",
                    "pairs": ["ETH/USDT", "BTC/USDT"],
                    "timeframe": "5m",
                    "exchange": "binance",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("BTC/USDT", response.json()["detail"])
        mock_start.assert_not_called()
        mock_save.assert_not_called()

    def test_run_backtest_starts_when_selected_pairs_have_data(self) -> None:
        coverage = [
            {
                "pair": "ETH/USDT",
                "timeframe": "5m",
                "exchange": "kraken",
                "available": True,
                "file_size": 123,
                "file_path": "/tmp/ETH_USDT-5m.json",
            },
        ]

        with patch("app.routers.backtest.check_data_coverage", return_value=coverage), patch(
            "app.routers.backtest.start_backtest", return_value="run_123"
        ) as mock_start, patch("app.routers.backtest.save_last_config") as mock_save:
            response = self.client.post(
                "/run",
                json={
                    "strategy": "Diamond",
                    "pairs": ["ETH/USDT"],
                    "timeframe": "5m",
                    "exchange": "kraken",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"run_id": "run_123", "status": "running"})
        mock_save.assert_called_once()
        mock_start.assert_called_once_with(
            strategy="Diamond",
            pairs=["ETH/USDT"],
            timeframe="5m",
            timerange=None,
            strategy_params={},
            exchange="kraken",
            strategy_path=None,
            strategy_label=None,
            command_override=None,
        )

    def test_run_backtest_forwards_optional_strategy_source_fields(self) -> None:
        coverage = [
            {
                "pair": "ETH/USDT",
                "timeframe": "5m",
                "exchange": "binance",
                "available": True,
                "file_size": 123,
                "file_path": "/tmp/ETH_USDT-5m.json",
            },
        ]

        with patch("app.routers.backtest.check_data_coverage", return_value=coverage), patch(
            "app.routers.backtest.start_backtest", return_value="run_456"
        ) as mock_start, patch("app.routers.backtest.save_last_config"):
            response = self.client.post(
                "/run",
                json={
                    "strategy": "MultiMa",
                    "pairs": ["ETH/USDT"],
                    "timeframe": "5m",
                    "exchange": "binance",
                    "strategy_path": "/tmp/evolved",
                    "strategy_label": "MultiMa_v2",
                    "strategy_params": {"buy_fast": 12},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"run_id": "run_456", "status": "running"})
        mock_start.assert_called_once_with(
            strategy="MultiMa",
            pairs=["ETH/USDT"],
            timeframe="5m",
            timerange=None,
            strategy_params={"buy_fast": 12},
            exchange="binance",
            strategy_path="/tmp/evolved",
            strategy_label="MultiMa_v2",
            command_override=None,
        )

    def test_get_run_returns_rich_results(self) -> None:
        with patch("app.routers.backtest.get_status", return_value="completed"), patch(
            "app.routers.backtest.load_run_meta",
            return_value={"run_id": "run_123", "strategy": "Diamond", "status": "completed"},
        ), patch(
            "app.routers.backtest.load_run_results",
            return_value={
                "overview": {"profit_percent": 10.0},
                "periodic_breakdown": {"day": [{"date": "2026-04-01"}]},
                "raw_artifact": {"available": True},
            },
        ), patch("app.routers.backtest.get_logs", return_value=["ok"]):
            response = self.client.get("/runs/run_123")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("periodic_breakdown", body["results"])
        self.assertTrue(body["results"]["raw_artifact"]["available"])

    def test_get_run_raw_returns_artifact_payload(self) -> None:
        with patch("app.routers.backtest.get_status", return_value="completed"), patch(
            "app.routers.backtest.load_run_meta",
            return_value={"run_id": "run_123", "strategy": "Diamond", "status": "completed"},
        ), patch(
            "app.routers.backtest.load_run_raw_payload",
            return_value={
                "run_id": "run_123",
                "raw_artifact_missing": False,
                "artifact": {"available": True, "file_name": "sample.zip"},
                "payload": {"strategy": {"Diamond": {}}},
                "data_source": "raw_artifact",
                "strategy_name": "Diamond",
            },
        ):
            response = self.client.get("/runs/run_123/raw")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["raw_artifact_missing"])
        self.assertEqual(body["artifact"]["file_name"], "sample.zip")

    def test_get_run_raw_returns_parsed_fallback(self) -> None:
        with patch("app.routers.backtest.get_status", return_value="completed"), patch(
            "app.routers.backtest.load_run_meta",
            return_value={"run_id": "run_123", "strategy": "Diamond", "status": "completed"},
        ), patch(
            "app.routers.backtest.load_run_raw_payload",
            return_value={
                "run_id": "run_123",
                "raw_artifact_missing": True,
                "artifact": {"available": False},
                "payload": {"overview": {"profit_percent": 10.0}},
                "data_source": "parsed_results",
                "strategy_name": "Diamond",
            },
        ):
            response = self.client.get("/runs/run_123/raw")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["raw_artifact_missing"])
        self.assertEqual(body["data_source"], "parsed_results")
        self.assertIn("overview", body["payload"])

    def test_apply_run_config_updates_core_fields_and_last_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.json"
            cfg_path.write_text(json.dumps({"strategy": "Old", "timeframe": "1h"}), encoding="utf-8")
            with (
                patch("app.routers.backtest._CONFIG_FILE", cfg_path),
                patch(
                    "app.routers.backtest.load_run_meta",
                    return_value={
                        "run_id": "run_123",
                        "strategy": "MultiMa",
                        "strategy_class": "MultiMa",
                        "pairs": ["ETH/USDT"],
                        "timeframe": "5m",
                        "timerange": "20250101-20250131",
                        "exchange": "binance",
                        "dry_run_wallet": 50,
                        "max_open_trades": 1,
                        "stake_amount": "unlimited",
                        "strategy_params": {"buy_fast": 12},
                    },
                ),
                patch("app.routers.backtest.STRATEGIES_DIR", Path(tmpdir)),
                patch("app.routers.backtest.save_last_config") as save_last_config_mock,
            ):
                response = self.client.post("/runs/run_123/apply-config")

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("strategy", body["applied"])
            self.assertIn("last_config", body["applied"])
            self.assertEqual(body["warnings"], [])
            saved_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_cfg["strategy"], "MultiMa")
            self.assertEqual(saved_cfg["timeframe"], "5m")
            save_last_config_mock.assert_called_once()
            sidecar = json.loads((Path(tmpdir) / "MultiMa.json").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["params"]["buy"]["buy_fast"], 12)

    def test_apply_run_config_warns_for_external_strategy_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.json"
            cfg_path.write_text("{}", encoding="utf-8")
            with (
                patch("app.routers.backtest._CONFIG_FILE", cfg_path),
                patch(
                    "app.routers.backtest.load_run_meta",
                    return_value={
                        "run_id": "run_123",
                        "strategy": "MultiMa_v2",
                        "strategy_class": "MultiMa",
                        "strategy_path": "/tmp/external",
                        "strategy_params": {"buy_fast": 12},
                    },
                ),
                patch("app.routers.backtest.save_last_config"),
            ):
                response = self.client.post("/runs/run_123/apply-config")

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("strategy_params", body["skipped"])
            self.assertTrue(any("external strategy_path" in warning for warning in body["warnings"]))


if __name__ == "__main__":
    unittest.main()
