from __future__ import annotations

import json
from typing import Any


def resolve_strategy_payload(raw: Any) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(raw, dict):
        return None, None

    wrapped = raw.get("latest_backtest")
    if isinstance(wrapped, str) and wrapped:
        try:
            decoded = json.loads(wrapped)
        except (json.JSONDecodeError, TypeError):
            decoded = None
        if isinstance(decoded, dict) and decoded:
            wrapped = decoded

    if isinstance(wrapped, dict) and wrapped:
        raw = wrapped

    strategy_block = raw.get("strategy")
    if isinstance(strategy_block, dict) and strategy_block:
        strategy_name = next(iter(strategy_block))
        strategy_data = strategy_block.get(strategy_name)
        if isinstance(strategy_data, dict):
            return strategy_name, strategy_data

    if isinstance(raw.get("trades"), list):
        strategy_name = raw.get("strategy_name")
        return strategy_name if isinstance(strategy_name, str) else None, raw

    strategy_comparison = raw.get("strategy_comparison")
    if isinstance(strategy_comparison, list) and strategy_comparison:
        first = strategy_comparison[0]
        if isinstance(first, dict):
            strategy_name = first.get("key")
            return strategy_name if isinstance(strategy_name, str) else None, first

    return None, None


__all__ = ["resolve_strategy_payload"]
