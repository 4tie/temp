import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import DATA_DIR, VALID_TIMEFRAMES

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_SAFE_PAIR_RE = re.compile(r"^[A-Z0-9]+/[A-Z0-9]+$")
_TIMERANGE_RE = re.compile(r"^(\d{8})?-(\d{8})?$")


def _validate_exchange(exchange: str) -> bool:
    return bool(_SAFE_NAME_RE.match(exchange))


def _validate_pair(pair: str) -> bool:
    return bool(_SAFE_PAIR_RE.match(pair.upper()))


def _validate_timeframe(timeframe: str) -> bool:
    return timeframe in VALID_TIMEFRAMES


def _parse_timerange(timerange: str) -> tuple[Optional[datetime], Optional[datetime]]:
    if not timerange:
        return None, None

    m = _TIMERANGE_RE.match(timerange.strip())
    if not m:
        return None, None

    start_str, end_str = m.group(1), m.group(2)

    start_dt = None
    end_dt = None

    try:
        if start_str:
            start_dt = datetime.strptime(start_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        if end_str:
            end_dt = datetime.strptime(end_str, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None, None

    return start_dt, end_dt


def _find_data_file(exchange: str, pair: str, timeframe: str) -> Optional[Path]:
    if not _validate_exchange(exchange) or not _validate_pair(pair) or not _validate_timeframe(timeframe):
        return None

    pair_file = pair.replace("/", "_")

    search_dirs = [DATA_DIR / exchange, DATA_DIR]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ext in [".feather", ".json", ".json.gz"]:
            candidate = search_dir / f"{pair_file}-{timeframe}{ext}"
            resolved = candidate.resolve()
            if not resolved.is_relative_to(DATA_DIR.resolve()):
                continue
            if resolved.exists():
                return resolved

    return None


def _load_raw_data(file_path: Path) -> list:
    suffix = "".join(file_path.suffixes)

    if suffix == ".json.gz":
        with gzip.open(file_path, "rt", encoding="utf-8") as f:
            return json.load(f)
    elif suffix == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    elif suffix == ".feather":
        import pandas as pd
        df = pd.read_feather(file_path)
        cols = list(df.columns)
        rows = []
        for _, row in df.iterrows():
            if len(cols) >= 6:
                ts_val = row[cols[0]]
                if hasattr(ts_val, "timestamp"):
                    ts_ms = int(ts_val.timestamp() * 1000)
                elif isinstance(ts_val, (int, float)):
                    ts_ms = int(ts_val)
                else:
                    try:
                        ts_ms = int(pd.Timestamp(ts_val).timestamp() * 1000)
                    except Exception:
                        continue
                rows.append([
                    ts_ms,
                    float(row[cols[1]]),
                    float(row[cols[2]]),
                    float(row[cols[3]]),
                    float(row[cols[4]]),
                    float(row[cols[5]]),
                ])
        return rows

    return []


def load_ohlcv(
    pair: str,
    timeframe: str,
    exchange: str,
    timerange: Optional[str] = None,
) -> list[dict]:
    file_path = _find_data_file(exchange, pair, timeframe)
    if not file_path:
        return []

    raw = _load_raw_data(file_path)
    if not raw:
        return []

    start_dt, end_dt = _parse_timerange(timerange) if timerange else (None, None)
    start_ts = int(start_dt.timestamp() * 1000) if start_dt else None
    end_ts = int(end_dt.timestamp() * 1000) if end_dt else None

    result = []
    for candle in raw:
        if not isinstance(candle, (list, tuple)) or len(candle) < 6:
            continue

        ts = int(candle[0])

        if start_ts and ts < start_ts:
            continue
        if end_ts and ts >= end_ts:
            continue

        result.append({
            "date": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
        })

    return result
