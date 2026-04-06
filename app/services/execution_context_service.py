from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from app.core.config import FREQTRADE_CONFIG_FILE
from app.services.data_coverage import check_data_coverage

_TIMERANGE_RE = re.compile(r"^(\d{8})-(\d{8})$")


def read_config_json() -> dict[str, Any]:
    if FREQTRADE_CONFIG_FILE.exists():
        try:
            import json

            return json.loads(FREQTRADE_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def resolve_exchange_name(explicit_exchange: Optional[str] = None) -> str:
    if explicit_exchange:
        return explicit_exchange

    cfg = read_config_json()
    exchange_name = cfg.get("exchange", {})
    if isinstance(exchange_name, dict):
        exchange_name = exchange_name.get("name")

    if isinstance(exchange_name, str) and exchange_name:
        return exchange_name

    return "binance"


def normalize_pair_selection(pairs: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for pair in pairs or []:
        value = str(pair or "").strip().upper()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def build_timerange_context(timerange: Optional[str]) -> dict[str, Any]:
    raw = str(timerange or "").strip()
    if not raw:
        return {
            "raw": None,
            "valid": False,
            "start": None,
            "end": None,
            "days": None,
        }

    match = _TIMERANGE_RE.match(raw)
    if not match:
        return {
            "raw": raw,
            "valid": False,
            "start": None,
            "end": None,
            "days": None,
        }

    start_s, end_s = match.groups()
    try:
        start_d = date(int(start_s[:4]), int(start_s[4:6]), int(start_s[6:8]))
        end_d = date(int(end_s[:4]), int(end_s[4:6]), int(end_s[6:8]))
        days = (end_d - start_d).days + 1
    except ValueError:
        return {
            "raw": raw,
            "valid": False,
            "start": None,
            "end": None,
            "days": None,
        }

    return {
        "raw": raw,
        "valid": True,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "days": days if days > 0 else None,
    }


def validate_selected_pair_data(
    pairs: list[str],
    timeframe: str,
    exchange: str,
    timerange: Optional[str] = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    normalized_pairs = normalize_pair_selection(pairs)
    coverage = check_data_coverage(
        pairs=normalized_pairs,
        timeframe=timeframe,
        exchange=exchange,
        timerange=timerange,
    )
    missing_pairs: list[str] = []
    issue_details: list[str] = []

    for item in coverage:
        pair = item.get("pair", "unknown")
        available = bool(item.get("available"))
        missing_days = list(item.get("missing_days") or [])
        incomplete_days = list(item.get("incomplete_days") or [])
        daily_applied = bool(item.get("daily_validation_applied"))

        has_issue = (not available) or (daily_applied and (missing_days or incomplete_days))
        if not has_issue:
            continue

        missing_pairs.append(pair)
        if not available:
            issue_details.append(f"{pair}: data file missing")
            continue

        details: list[str] = []
        if missing_days:
            preview = ", ".join(missing_days[:3])
            if len(missing_days) > 3:
                preview += f" (+{len(missing_days) - 3} more)"
            details.append(f"missing days [{preview}]")
        if incomplete_days:
            short = ", ".join(
                f"{d.get('date')} ({d.get('actual')}/{d.get('expected')})"
                for d in incomplete_days[:3]
            )
            if len(incomplete_days) > 3:
                short += f" (+{len(incomplete_days) - 3} more)"
            details.append(f"incomplete days [{short}]")
        issue_details.append(f"{pair}: " + "; ".join(details))

    return coverage, missing_pairs, issue_details
