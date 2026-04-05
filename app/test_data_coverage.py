from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.services.data_coverage import check_data_coverage


def _candles_for_day(day: datetime, timeframe_minutes: int, count: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for i in range(count):
        ts = int((day + timedelta(minutes=i * timeframe_minutes)).timestamp() * 1000)
        rows.append([ts, 1.0, 1.0, 1.0, 1.0, 100.0])
    return rows


class DataCoverageTests(unittest.TestCase):
    def test_exact_complete_daily_candles_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            ex_dir = data_dir / "binance"
            ex_dir.mkdir(parents=True)
            start = datetime(2026, 4, 1, tzinfo=timezone.utc)
            candles = _candles_for_day(start, 5, 288) + _candles_for_day(start + timedelta(days=1), 5, 288)
            (ex_dir / "ETH_USDT-5m.json").write_text(json.dumps(candles), encoding="utf-8")

            with patch("app.services.data_coverage.DATA_DIR", data_dir):
                coverage = check_data_coverage(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange="20260401-20260402",
                )

            item = coverage[0]
            self.assertTrue(item["available"])
            self.assertTrue(item["daily_validation_applied"])
            self.assertEqual(item["expected_candles_per_day"], 288)
            self.assertEqual(item["missing_days"], [])
            self.assertEqual(item["incomplete_days"], [])

    def test_missing_day_fails_daily_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            ex_dir = data_dir / "binance"
            ex_dir.mkdir(parents=True)
            start = datetime(2026, 4, 1, tzinfo=timezone.utc)
            candles = _candles_for_day(start, 5, 288)
            (ex_dir / "ETH_USDT-5m.json").write_text(json.dumps(candles), encoding="utf-8")

            with patch("app.services.data_coverage.DATA_DIR", data_dir):
                coverage = check_data_coverage(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange="20260401-20260402",
                )

            item = coverage[0]
            self.assertEqual(item["missing_days"], ["2026-04-02"])
            self.assertEqual(item["incomplete_days"], [])

    def test_partial_day_fails_daily_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            ex_dir = data_dir / "binance"
            ex_dir.mkdir(parents=True)
            start = datetime(2026, 4, 1, tzinfo=timezone.utc)
            candles = _candles_for_day(start, 5, 200)
            (ex_dir / "ETH_USDT-5m.json").write_text(json.dumps(candles), encoding="utf-8")

            with patch("app.services.data_coverage.DATA_DIR", data_dir):
                coverage = check_data_coverage(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange="20260401-20260401",
                )

            item = coverage[0]
            self.assertEqual(item["missing_days"], [])
            self.assertEqual(len(item["incomplete_days"]), 1)
            self.assertEqual(item["incomplete_days"][0]["date"], "2026-04-01")
            self.assertEqual(item["incomplete_days"][0]["actual"], 200)
            self.assertEqual(item["incomplete_days"][0]["expected"], 288)

    def test_invalid_timerange_skips_daily_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            ex_dir = data_dir / "binance"
            ex_dir.mkdir(parents=True)
            start = datetime(2026, 4, 1, tzinfo=timezone.utc)
            candles = _candles_for_day(start, 5, 10)
            (ex_dir / "ETH_USDT-5m.json").write_text(json.dumps(candles), encoding="utf-8")

            with patch("app.services.data_coverage.DATA_DIR", data_dir):
                coverage = check_data_coverage(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange="invalid",
                )

            item = coverage[0]
            self.assertFalse(item["daily_validation_applied"])
            self.assertEqual(item["missing_days"], [])
            self.assertEqual(item["incomplete_days"], [])

    def test_empty_timerange_skips_daily_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            ex_dir = data_dir / "binance"
            ex_dir.mkdir(parents=True)
            start = datetime(2026, 4, 1, tzinfo=timezone.utc)
            candles = _candles_for_day(start, 5, 10)
            (ex_dir / "ETH_USDT-5m.json").write_text(json.dumps(candles), encoding="utf-8")

            with patch("app.services.data_coverage.DATA_DIR", data_dir):
                coverage = check_data_coverage(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange=None,
                )

            item = coverage[0]
            self.assertFalse(item["daily_validation_applied"])
            self.assertEqual(item["missing_days"], [])
            self.assertEqual(item["incomplete_days"], [])

    def test_unsupported_timeframe_skips_daily_strict_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            ex_dir = data_dir / "binance"
            ex_dir.mkdir(parents=True)
            start = datetime(2026, 4, 1, tzinfo=timezone.utc)
            candles = _candles_for_day(start, 60, 24)
            (ex_dir / "ETH_USDT-3d.json").write_text(json.dumps(candles), encoding="utf-8")

            with patch("app.services.data_coverage.DATA_DIR", data_dir):
                coverage = check_data_coverage(
                    pairs=["ETH/USDT"],
                    timeframe="3d",
                    exchange="binance",
                    timerange="20260401-20260402",
                )

            item = coverage[0]
            self.assertFalse(item["daily_validation_applied"])
            self.assertIsNone(item["expected_candles_per_day"])
            self.assertTrue(isinstance(item.get("daily_validation_skip_reason"), str))

    def test_partial_current_day_is_allowed_when_end_day_is_today(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            ex_dir = data_dir / "binance"
            ex_dir.mkdir(parents=True)
            today = datetime.now(timezone.utc).date()
            day_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
            candles = _candles_for_day(day_start, 5, 226)
            (ex_dir / "ETH_USDT-5m.json").write_text(json.dumps(candles), encoding="utf-8")
            timerange = f"{today.strftime('%Y%m%d')}-{today.strftime('%Y%m%d')}"

            with patch("app.services.data_coverage.DATA_DIR", data_dir):
                coverage = check_data_coverage(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange=timerange,
                )

            item = coverage[0]
            self.assertEqual(item["missing_days"], [])
            self.assertEqual(item["incomplete_days"], [])
            self.assertTrue(item["partial_current_day_allowed"])

    def test_missing_current_day_remains_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            ex_dir = data_dir / "binance"
            ex_dir.mkdir(parents=True)
            (ex_dir / "ETH_USDT-5m.json").write_text(json.dumps([]), encoding="utf-8")
            today = datetime.now(timezone.utc).date()
            timerange = f"{today.strftime('%Y%m%d')}-{today.strftime('%Y%m%d')}"

            with patch("app.services.data_coverage.DATA_DIR", data_dir):
                coverage = check_data_coverage(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange=timerange,
                )

            item = coverage[0]
            self.assertEqual(item["missing_days"], [today.isoformat()])
            self.assertEqual(item["incomplete_days"], [])
            self.assertTrue(item["partial_current_day_allowed"])

    def test_partial_past_end_day_is_still_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            ex_dir = data_dir / "binance"
            ex_dir.mkdir(parents=True)
            yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
            day_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)
            candles = _candles_for_day(day_start, 5, 226)
            (ex_dir / "ETH_USDT-5m.json").write_text(json.dumps(candles), encoding="utf-8")
            timerange = f"{yesterday.strftime('%Y%m%d')}-{yesterday.strftime('%Y%m%d')}"

            with patch("app.services.data_coverage.DATA_DIR", data_dir):
                coverage = check_data_coverage(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange=timerange,
                )

            item = coverage[0]
            self.assertEqual(item["missing_days"], [])
            self.assertEqual(len(item["incomplete_days"]), 1)
            self.assertEqual(item["incomplete_days"][0]["actual"], 226)
            self.assertFalse(item["partial_current_day_allowed"])


if __name__ == "__main__":
    unittest.main()
