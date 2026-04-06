from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.services.execution_context_service import validate_selected_pair_data


def _day_candles(day: date, count: int, step_minutes: int = 5) -> list[list[int]]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    candles: list[list[int]] = []
    for index in range(count):
        ts_ms = int((start + timedelta(minutes=index * step_minutes)).timestamp() * 1000)
        candles.append([ts_ms, 0, 0, 0, 0, 0])
    return candles


class DataCoverageRecentEndDayTest(unittest.TestCase):
    def test_recent_trailing_day_incomplete_is_tolerated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_root = Path(tmpdir)
            exchange_dir = data_root / "binance"
            exchange_dir.mkdir(parents=True, exist_ok=True)
            payload = (
                _day_candles(date(2026, 4, 4), 288)
                + _day_candles(date(2026, 4, 5), 218)
            )
            (exchange_dir / "ETH_USDT-5m.json").write_text(json.dumps(payload), encoding="utf-8")

            with patch("app.services.data_coverage.DATA_DIR", data_root), patch(
                "app.services.data_coverage._current_utc_day",
                return_value=date(2026, 4, 6),
            ):
                coverage, missing_pairs, issue_details = validate_selected_pair_data(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange="20260404-20260405",
                )

        self.assertEqual(missing_pairs, [])
        self.assertEqual(issue_details, [])
        self.assertEqual(coverage[0]["incomplete_days"], [])
        self.assertTrue(coverage[0]["partial_current_day_allowed"])

    def test_older_incomplete_day_still_blocks_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_root = Path(tmpdir)
            exchange_dir = data_root / "binance"
            exchange_dir.mkdir(parents=True, exist_ok=True)
            payload = _day_candles(date(2026, 4, 4), 218)
            (exchange_dir / "ETH_USDT-5m.json").write_text(json.dumps(payload), encoding="utf-8")

            with patch("app.services.data_coverage.DATA_DIR", data_root), patch(
                "app.services.data_coverage._current_utc_day",
                return_value=date(2026, 4, 6),
            ):
                coverage, missing_pairs, issue_details = validate_selected_pair_data(
                    pairs=["ETH/USDT"],
                    timeframe="5m",
                    exchange="binance",
                    timerange="20260404-20260404",
                )

        self.assertEqual(missing_pairs, ["ETH/USDT"])
        self.assertIn("incomplete days [2026-04-04 (218/288)]", issue_details[0])
        self.assertEqual(coverage[0]["incomplete_days"][0]["date"], "2026-04-04")
