import gzip
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.config import DATA_DIR

_TIMERANGE_RE = re.compile(r"^(\d{8})-(\d{8})$")
_INTRADAY_TIMEFRAME_RE = re.compile(r"^(\d+)(m|h)$")
_RECENT_END_DAY_GRACE_DAYS = 1


def _find_pair_file(pair: str, timeframe: str, exchange: str) -> tuple[Optional[Path], int]:
    search_dirs = [DATA_DIR / exchange, DATA_DIR]
    pair_file_name = pair.replace("/", "_")

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ext in [".feather", ".json", ".json.gz", ".hdf5"]:
            candidate = search_dir / f"{pair_file_name}-{timeframe}{ext}"
            if candidate.exists():
                return candidate, candidate.stat().st_size
    return None, 0


def _parse_timerange(timerange: Optional[str]) -> tuple[Optional[date], Optional[date]]:
    if not timerange:
        return None, None
    match = _TIMERANGE_RE.match(timerange.strip())
    if not match:
        return None, None
    try:
        start = datetime.strptime(match.group(1), "%Y%m%d").date()
        end = datetime.strptime(match.group(2), "%Y%m%d").date()
    except ValueError:
        return None, None
    if end < start:
        return None, None
    return start, end


def _expected_candles_per_day(timeframe: str) -> tuple[Optional[int], Optional[str]]:
    if timeframe == "1d":
        return 1, None
    if timeframe in {"3d", "1w", "1M"}:
        return None, f"timeframe '{timeframe}' does not support strict per-day candle counts"

    match = _INTRADAY_TIMEFRAME_RE.match(timeframe)
    if not match:
        return None, f"timeframe '{timeframe}' is not supported for daily strict validation"

    value = int(match.group(1))
    unit = match.group(2)
    step_minutes = value if unit == "m" else value * 60
    if step_minutes <= 0:
        return None, f"timeframe '{timeframe}' is invalid"
    if 1440 % step_minutes != 0:
        return None, f"timeframe '{timeframe}' does not divide evenly into one day"
    return 1440 // step_minutes, None


def _load_timestamps_ms(file_path: Path) -> list[int]:
    suffix = "".join(file_path.suffixes)

    if suffix == ".json.gz":
        with gzip.open(file_path, "rt", encoding="utf-8") as f:
            raw = json.load(f)
    elif suffix == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    elif suffix == ".feather":
        import pandas as pd

        df = pd.read_feather(file_path)
        if df.empty:
            return []
        first_col = df.columns[0]
        timestamps: list[int] = []
        for value in df[first_col]:
            if hasattr(value, "timestamp"):
                timestamps.append(int(value.timestamp() * 1000))
            elif isinstance(value, (int, float)):
                timestamps.append(int(value))
            else:
                try:
                    timestamps.append(int(pd.Timestamp(value).timestamp() * 1000))
                except Exception:
                    continue
        return timestamps
    elif suffix == ".hdf5":
        import pandas as pd

        df = pd.read_hdf(file_path)
        if df.empty:
            return []
        first_col = df.columns[0]
        timestamps: list[int] = []
        for value in df[first_col]:
            if hasattr(value, "timestamp"):
                timestamps.append(int(value.timestamp() * 1000))
            elif isinstance(value, (int, float)):
                timestamps.append(int(value))
            else:
                try:
                    timestamps.append(int(pd.Timestamp(value).timestamp() * 1000))
                except Exception:
                    continue
        return timestamps
    else:
        return []

    timestamps: list[int] = []
    for candle in raw:
        if isinstance(candle, (list, tuple)) and candle:
            try:
                timestamps.append(int(candle[0]))
            except (TypeError, ValueError):
                continue
    return timestamps


def _build_daily_counts(
    timestamps_ms: list[int],
    start_day: date,
    end_day: date,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ts in timestamps_ms:
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
        if day < start_day or day > end_day:
            continue
        key = day.isoformat()
        counts[key] = counts.get(key, 0) + 1
    return counts


def _iter_days(start_day: date, end_day: date) -> list[str]:
    days: list[str] = []
    current = start_day
    while current <= end_day:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _current_utc_day() -> date:
    return datetime.now(timezone.utc).date()


def check_data_coverage(
    pairs: list[str],
    timeframe: str,
    exchange: str,
    timerange: Optional[str] = None,
) -> list[dict[str, Any]]:
    coverage = []
    start_day, end_day = _parse_timerange(timerange)
    expected_per_day, skip_reason = _expected_candles_per_day(timeframe)
    requested_daily_validation = start_day is not None and end_day is not None
    today_utc = _current_utc_day()
    partial_current_day_allowed = bool(
        requested_daily_validation
        and expected_per_day is not None
        and end_day >= (today_utc - timedelta(days=_RECENT_END_DAY_GRACE_DAYS))
    )

    for pair in pairs:
        file_path, file_size = _find_pair_file(pair, timeframe, exchange)
        found = file_path is not None
        file_path_str = str(file_path) if file_path else ""
        daily_validation_applied = bool(
            requested_daily_validation and found and expected_per_day is not None
        )
        missing_days: list[str] = []
        incomplete_days: list[dict[str, Any]] = []
        daily_skip_reason = None

        if requested_daily_validation:
            if expected_per_day is None:
                daily_skip_reason = skip_reason or "daily validation not available for timeframe"
            elif not found:
                days = _iter_days(start_day, end_day)
                missing_days = days
                daily_validation_applied = True
            else:
                try:
                    timestamps_ms = _load_timestamps_ms(file_path)
                    day_counts = _build_daily_counts(timestamps_ms, start_day, end_day)
                    for day in _iter_days(start_day, end_day):
                        actual = day_counts.get(day, 0)
                        is_in_progress_end_day = (
                            partial_current_day_allowed
                            and day == end_day.isoformat()
                        )
                        if is_in_progress_end_day:
                            # The trailing requested day may still be settling due to
                            # exchange/API lag. Do not force an auto-download loop for it.
                            continue
                        if actual == 0:
                            missing_days.append(day)
                        elif actual != expected_per_day:
                            incomplete_days.append({
                                "date": day,
                                "actual": actual,
                                "expected": expected_per_day,
                            })
                except Exception:
                    daily_validation_applied = True
                    daily_skip_reason = "failed to parse data file for daily validation"
                    missing_days = _iter_days(start_day, end_day)

        coverage.append({
            "pair": pair,
            "timeframe": timeframe,
            "exchange": exchange,
            "available": found,
            "file_size": file_size,
            "file_path": file_path_str,
            "daily_validation_applied": daily_validation_applied,
            "expected_candles_per_day": expected_per_day if daily_validation_applied else None,
            "missing_days": missing_days,
            "incomplete_days": incomplete_days,
            "daily_validation_skip_reason": daily_skip_reason,
            "partial_current_day_allowed": partial_current_day_allowed,
        })

    return coverage
