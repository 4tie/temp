from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import BACKTEST_RESULTS_DIR, RAW_ARTIFACT_META_SUFFIX
from app.services.results.raw_loader import find_run_local_result_artifact
from app.services.results.result_service import parse_backtest_results
from app.services.runs.run_metadata_service import exchange_name_from_config, read_runtime_config, utcnow_iso


def build_backtest_meta(
    *,
    run_id: str,
    strategy: str,
    display_strategy: str,
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
    strategy_params: dict[str, Any],
    strategy_path: str | None,
    command: list[str],
    exchange: str | None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = read_runtime_config()
    meta: dict[str, Any] = {
        "run_id": run_id,
        "strategy": display_strategy,
        "display_strategy": display_strategy,
        "strategy_class": strategy,
        "base_strategy": strategy,
        "strategy_base": strategy,
        "pairs": pairs,
        "timeframe": timeframe,
        "timerange": timerange,
        "dry_run_wallet": cfg.get("dry_run_wallet"),
        "max_open_trades": cfg.get("max_open_trades"),
        "stake_amount": cfg.get("stake_amount"),
        "exchange": exchange or exchange_name_from_config(cfg),
        "strategy_params": strategy_params,
        "strategy_path": strategy_path,
        "command": command,
        "status": "running",
        "started_at": utcnow_iso(),
        "completed_at": None,
    }
    if extra_meta:
        meta.update(extra_meta)
    resolved_version_id = (
        meta.get("version_id")
        or meta.get("strategy_version")
        or meta.get("strategy_source_name")
    )
    if resolved_version_id:
        meta["version_id"] = resolved_version_id
        meta.setdefault("strategy_version", resolved_version_id)
        meta.setdefault("display_version", resolved_version_id)
    return meta


def try_import_fresh_global_result(run_dir: Path, meta: dict[str, Any]) -> bool:
    last_result_file = BACKTEST_RESULTS_DIR / ".last_result.json"
    if not last_result_file.exists():
        return False

    try:
        last_ref = json.loads(last_result_file.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    latest_name = str(last_ref.get("latest_backtest") or "").strip()
    if not latest_name:
        return False

    source_artifact = BACKTEST_RESULTS_DIR / latest_name
    if not source_artifact.exists() or not source_artifact.is_file():
        return False

    started_at = meta.get("started_at")
    start_ts = None
    if isinstance(started_at, str) and started_at:
        try:
            start_ts = datetime.fromisoformat(started_at).timestamp()
        except ValueError:
            start_ts = None

    source_mtime = source_artifact.stat().st_mtime
    if start_ts is not None and source_mtime + 1 < start_ts:
        return False

    strategy_expected = str(meta.get("strategy_class") or meta.get("base_strategy") or meta.get("strategy") or "")
    timeframe_expected = str(meta.get("timeframe") or "")
    if source_artifact.suffix.lower() == ".zip":
        source_meta = source_artifact.with_name(source_artifact.name.replace(".zip", RAW_ARTIFACT_META_SUFFIX))
        if not source_meta.exists():
            return False
        try:
            meta_payload = json.loads(source_meta.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        if not isinstance(meta_payload, dict) or not meta_payload:
            return False

        strategy_key = strategy_expected if strategy_expected in meta_payload else next(iter(meta_payload.keys()))
        strat_meta = meta_payload.get(strategy_key) if isinstance(meta_payload.get(strategy_key), dict) else None
        if strat_meta is None:
            return False

        if strategy_expected and strategy_expected not in meta_payload:
            return False
        if timeframe_expected and str(strat_meta.get("timeframe") or "") != timeframe_expected:
            return False

        shutil.copy2(source_meta, run_dir / source_meta.name)

    shutil.copy2(source_artifact, run_dir / source_artifact.name)
    return True


def collect_backtest_run_results(run_dir: Path, meta: dict[str, Any]) -> dict[str, Any]:
    artifact = find_run_local_result_artifact(run_dir)
    if not artifact.get("available") and try_import_fresh_global_result(run_dir, meta):
        artifact = find_run_local_result_artifact(run_dir)

    if not artifact.get("available"):
        return {
            "status": "failed",
            "results": None,
            "error": "missing run-local result artifact",
            "log_message": "ERROR: Backtest completed but no attributable result artifact was found for this run.",
            "raw_artifact": {"available": False, "run_local": False},
        }

    results = parse_backtest_results(run_dir)
    results["display_strategy"] = meta.get("display_strategy") or meta.get("strategy")
    raw_artifact = results.get("raw_artifact", {"available": False})

    if results.get("error"):
        error = f"result parse error: {results.get('error')}"
        return {
            "status": "failed",
            "results": results,
            "error": error,
            "log_message": f"ERROR: Failed to parse run-local result artifact: {results.get('error')}",
            "raw_artifact": raw_artifact,
        }

    return {
        "status": "completed",
        "results": results,
        "error": None,
        "log_message": None,
        "raw_artifact": raw_artifact,
    }
