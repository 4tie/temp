from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ai.goals import goal_label, normalize_goal_id
from app.core.config import BASE_DIR, LAST_CONFIG_FILE, STRATEGIES_DIR
from app.services.storage import list_runs, load_run_meta, load_run_results

_SECRET_KEYS = {
    "key",
    "secret",
    "password",
    "token",
    "jwt_secret_key",
    "ws_token",
    "api_key",
    "openrouter_api_key",
}

_CONFIG_PATH = BASE_DIR / "config.json"


@dataclass
class ContextBundle:
    snapshot: dict[str, Any]
    context_text: str
    context_hint: str
    metadata: dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _redact_value(key: str, value: Any) -> Any:
    if any(secret in key.lower() for secret in _SECRET_KEYS):
        if isinstance(value, str) and value:
            return "***REDACTED***"
        return "***REDACTED***"
    return value


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: redact_secrets(_redact_value(k, v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_secrets(v) for v in value]
    return value


def normalize_backtest_overview(results: dict[str, Any]) -> dict[str, Any]:
    overview = deepcopy(results.get("overview") or results.get("summary") or {})
    if not overview:
        return {}

    def _pick(*keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in overview and overview[key] is not None:
                return overview[key]
        return default

    return {
        "total_trades": _pick("total_trades", "trade_count", default=0),
        "profit_percent": _pick("profit_percent", "profit_total_pct", "totalProfitPct", default=0),
        "profit_factor": _pick("profit_factor", "profitFactor", default=0),
        "win_rate": _pick("win_rate", "winRate", default=0),
        "max_drawdown": _pick("max_drawdown", "max_drawdown_pct", "maxDrawdown", default=0),
        "starting_balance": _pick("starting_balance", default=0),
        "final_balance": _pick("final_balance", default=0),
        "timeframe": _pick("timeframe", default=""),
        "stake_amount": _pick("stake_amount", default=""),
        "max_open_trades": _pick("max_open_trades", default=0),
    }


def latest_completed_run_id() -> str | None:
    for run in list_runs():
        if str(run.get("status", "")).lower() in {"completed", "done"}:
            return run.get("run_id")
    return None


def _load_strategy_sidecar(strategy_name: str | None) -> dict[str, Any]:
    if not strategy_name:
        return {}
    return _read_json(STRATEGIES_DIR / f"{strategy_name}.json")


def _load_relevant_settings() -> dict[str, Any]:
    active = _read_json(_CONFIG_PATH)
    last_config = _read_json(LAST_CONFIG_FILE)

    relevant_active = {
        "strategy": active.get("strategy"),
        "timeframe": active.get("timeframe"),
        "stake_currency": active.get("stake_currency"),
        "stake_amount": active.get("stake_amount"),
        "max_open_trades": active.get("max_open_trades"),
        "dry_run": active.get("dry_run"),
        "trading_mode": active.get("trading_mode"),
        "exchange": {
            "name": (active.get("exchange") or {}).get("name"),
            "pair_whitelist": ((active.get("exchange") or {}).get("pair_whitelist") or [])[:10],
        },
        "pairlists": (active.get("pairlists") or [])[:3],
        "freqai": {
            "enabled": ((active.get("freqai") or {}).get("enabled")),
            "identifier": ((active.get("freqai") or {}).get("identifier")),
        },
    }

    relevant_last = {
        "strategy": last_config.get("strategy"),
        "pairs": (last_config.get("pairs") or [])[:10],
        "timeframe": last_config.get("timeframe"),
        "timerange": last_config.get("timerange"),
        "strategy_params": last_config.get("strategy_params") or {},
    }

    return redact_secrets({
        "active_config": relevant_active,
        "last_backtest_request": relevant_last,
    })


def _build_backtest_snapshot(run_id: str | None) -> dict[str, Any]:
    if not run_id:
        return {}

    meta = load_run_meta(run_id) or {}
    results = load_run_results(run_id) or {}
    overview = normalize_backtest_overview(results)
    per_pair = deepcopy(results.get("per_pair") or results.get("pairs") or [])
    warnings = deepcopy(results.get("warnings") or [])

    return {
        "run_id": run_id,
        "strategy": meta.get("strategy"),
        "pairs": (meta.get("pairs") or [])[:10],
        "timeframe": meta.get("timeframe") or overview.get("timeframe"),
        "timerange": meta.get("timerange"),
        "overview": overview,
        "per_pair": per_pair[:5],
        "warnings": warnings[:5],
    }


def build_context_snapshot(goal_id: str | None, context_run_id: str | None = None) -> dict[str, Any]:
    normalized_goal = normalize_goal_id(goal_id)
    selected_run_id = context_run_id or latest_completed_run_id()
    backtest = _build_backtest_snapshot(selected_run_id)
    strategy_name = (
        backtest.get("strategy")
        or (_read_json(_CONFIG_PATH).get("strategy"))
        or (_read_json(LAST_CONFIG_FILE).get("strategy"))
    )

    snapshot = {
        "schema_version": 1,
        "captured_at": _utc_now(),
        "goal_id": normalized_goal,
        "goal_label": goal_label(normalized_goal),
        "context_run_id": selected_run_id,
        "context_source": "explicit" if context_run_id else ("latest_completed" if selected_run_id else "none"),
        "backtest": backtest,
        "strategy_config": _load_strategy_sidecar(strategy_name),
        "settings": _load_relevant_settings(),
    }
    return redact_secrets(snapshot)


def render_context_text(snapshot: dict[str, Any]) -> str:
    if not snapshot:
        return ""

    parts = [f"User goal: {snapshot.get('goal_label', goal_label(snapshot.get('goal_id')))}"]
    backtest = snapshot.get("backtest") or {}
    overview = backtest.get("overview") or {}
    if backtest.get("run_id"):
        parts.append(
            "Backtest context: "
            f"run_id={backtest.get('run_id')} strategy={backtest.get('strategy')} timeframe={backtest.get('timeframe')}"
        )
    if overview:
        parts.append(
            "Key metrics: "
            f"profit_percent={overview.get('profit_percent')} "
            f"profit_factor={overview.get('profit_factor')} "
            f"win_rate={overview.get('win_rate')} "
            f"max_drawdown={overview.get('max_drawdown')} "
            f"total_trades={overview.get('total_trades')}"
        )
    per_pair = backtest.get("per_pair") or []
    if per_pair:
        parts.append(f"Per-pair summary JSON: {json.dumps(per_pair[:3], ensure_ascii=True)}")
    strategy_config = snapshot.get("strategy_config") or {}
    if strategy_config:
        parts.append(f"Strategy config JSON: {json.dumps(strategy_config, ensure_ascii=True)}")
    settings = snapshot.get("settings") or {}
    if settings:
        parts.append(f"Relevant settings JSON: {json.dumps(settings, ensure_ascii=True)}")
    warnings = backtest.get("warnings") or []
    if warnings:
        parts.append(f"Warnings: {json.dumps(warnings, ensure_ascii=True)}")
    return "\n\n".join(parts)


def build_context_bundle(goal_id: str | None, context_run_id: str | None = None) -> ContextBundle:
    snapshot = build_context_snapshot(goal_id, context_run_id)
    backtest = snapshot.get("backtest") or {}
    hint_bits = [f"goal={snapshot.get('goal_id')}"]
    if backtest.get("strategy"):
        hint_bits.append(f"strategy={backtest.get('strategy')}")
    if backtest.get("run_id"):
        hint_bits.append(f"run_id={backtest.get('run_id')}")
    return ContextBundle(
        snapshot=snapshot,
        context_text=render_context_text(snapshot),
        context_hint=" ".join(hint_bits),
        metadata={
            "goal_id": snapshot.get("goal_id"),
            "context_run_id": snapshot.get("context_run_id"),
            "context_source": snapshot.get("context_source"),
            "strategy": backtest.get("strategy"),
            "timeframe": backtest.get("timeframe"),
        },
    )
