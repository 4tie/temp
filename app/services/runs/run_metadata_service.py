from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import FREQTRADE_CONFIG_FILE, STRATEGIES_DIR
from app.core.processes import append_log

_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


def utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


def read_runtime_config() -> dict[str, Any]:
    if not FREQTRADE_CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(FREQTRADE_CONFIG_FILE.read_text())
    except Exception:
        return {}


def exchange_name_from_config(cfg: dict[str, Any]) -> str | None:
    exchange = cfg.get("exchange")
    if isinstance(exchange, dict):
        return exchange.get("name")
    if isinstance(exchange, str):
        return exchange
    return None


def ensure_valid_strategy_json(strategy: str, run_id: str, strategy_dir: Path | None = None) -> None:
    json_path = (strategy_dir or STRATEGIES_DIR) / f"{strategy}.json"
    if not json_path.exists():
        return
    try:
        raw = json_path.read_bytes()
        if not raw.strip():
            raise ValueError("empty file")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("not a dict")

        if "params" not in data:
            nested: dict = {"buy": {}, "sell": {}}
            for k, v in data.items():
                if not isinstance(v, _JSON_SCALAR_TYPES):
                    raise ValueError(f"non-scalar value: {type(v).__name__}")
                space = "sell" if k.startswith("sell_") else "buy"
                nested[space][k] = v
            data = {"strategy_name": strategy, "params": nested}
            json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            append_log(run_id, f"INFO: {strategy}.json migrated to nested params format.")
            return

        if "strategy_name" not in data:
            data["strategy_name"] = strategy
            json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        params = data["params"]
        if not isinstance(params, dict):
            raise ValueError("params is not a dict")
        for space_vals in params.values():
            if not isinstance(space_vals, dict):
                raise ValueError("space values must be a dict")
            for v in space_vals.values():
                if not isinstance(v, _JSON_SCALAR_TYPES):
                    raise ValueError(f"non-scalar value: {type(v).__name__}")
    except Exception as exc:
        json_path.write_text(json.dumps({"strategy_name": strategy, "params": {}}, indent=2), encoding="utf-8")
        append_log(
            run_id,
            f"WARNING: {strategy}.json was invalid ({exc}); reset so FreqTrade uses class defaults.",
        )


def finalize_meta(meta: dict[str, Any], status: str, error: str | None = None) -> dict[str, Any]:
    updated = dict(meta)
    updated["status"] = status
    updated["completed_at"] = utcnow_iso()
    if error:
        updated["error"] = error
    return updated
