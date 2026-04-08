import json
import re
import tempfile
import os
from contextlib import suppress
from typing import Optional
from pathlib import Path as SysPath

from fastapi import APIRouter, HTTPException, Path, Query

from app.schemas.backtest import BacktestRequest, DownloadDataRequest, DataCoverageRequest, ConfigPatchRequest, ApplyStrategySuggestionRequest
from app.services.runner import start_backtest, start_download
from app.services.execution_context_service import (
    build_timerange_context,
    normalize_pair_selection,
    read_config_json,
    resolve_exchange_name,
    validate_selected_pair_data,
)
from app.services.results.metric_registry import metric_registry_payload
from app.services.results.strategy_intelligence_service import (
    attach_strategy_intelligence,
    build_strategy_intelligence,
    has_strategy_intelligence,
)
from app.services.storage import (
    load_run_meta, load_run_results, list_runs, delete_run,
    save_last_config, load_last_config, save_run_logs, load_run_raw_payload, get_run_dir, save_run_results,
    load_app_events, append_app_event,
)
from app.services.strategies import save_strategy_current_values
from app.services.runs.base_run_service import run_logs_path
from app.services.ohlcv_loader import load_ohlcv
from app.services.indicator_calculator import calculate_indicators
from app.core.processes import get_status, get_logs
from app.core.config import FREQTRADE_CONFIG_FILE, STRATEGIES_DIR

router = APIRouter(tags=["backtest"])


def _write_config_json(cfg: dict) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=FREQTRADE_CONFIG_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp_path, FREQTRADE_CONFIG_FILE)
    except Exception:
        with suppress(OSError):
            os.unlink(tmp_path)
        raise

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _checked_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise HTTPException(status_code=400, detail="Invalid run/job ID")
    return value


def _is_default_strategy_path(strategy_path: Optional[str]) -> bool:
    if not strategy_path:
        return True
    try:
        return SysPath(strategy_path).resolve() == STRATEGIES_DIR.resolve()
    except Exception:
        return False

@router.get("/config")
async def get_config():
    cfg = read_config_json()
    return {
        "strategy": cfg.get("strategy"),
        "max_open_trades": cfg.get("max_open_trades"),
        "dry_run_wallet": cfg.get("dry_run_wallet"),
        "stake_amount": cfg.get("stake_amount"),
        "timeframe": cfg.get("timeframe"),
    }


@router.patch("/config")
async def patch_config(req: ConfigPatchRequest):
    cfg = read_config_json()
    updates = req.model_dump(exclude_none=True)
    for field, value in updates.items():
        cfg[field] = value
    _write_config_json(cfg)
    append_app_event(
        category="event",
        source="config",
        action="updated",
        status="ok",
        message="Backtest config updated.",
        fields=sorted(updates.keys()),
    )
    return {
        "strategy": cfg.get("strategy"),
        "max_open_trades": cfg.get("max_open_trades"),
        "dry_run_wallet": cfg.get("dry_run_wallet"),
        "stake_amount": cfg.get("stake_amount"),
        "timeframe": cfg.get("timeframe"),
    }


@router.post("/run")
async def run_backtest(req: BacktestRequest):
    exchange_name = resolve_exchange_name(req.exchange)
    normalized_pairs = normalize_pair_selection(req.pairs)
    timerange_context = build_timerange_context(req.timerange)
    _, missing_pairs, issue_details = validate_selected_pair_data(
        pairs=normalized_pairs,
        timeframe=req.timeframe,
        exchange=exchange_name,
        timerange=req.timerange,
    )
    if missing_pairs:
        # Auto-download missing data
        download_job_id = start_download(
            pairs=missing_pairs,
            timeframe=req.timeframe,
            timerange=req.timerange,
            command_override=None,
        )
        append_app_event(
            category="event",
            source="backtest",
            action="missing_data",
            status="warning",
            message=f"Backtest blocked by missing data. Auto-started download job {download_job_id}.",
            job_id=download_job_id,
            strategy=req.strategy,
            timeframe=req.timeframe,
            missing_pairs=missing_pairs,
        )
        detail_suffix = " | ".join(issue_details[:5])
        raise HTTPException(
            status_code=202,
            detail=(
                f"Downloading missing data for pairs: {', '.join(missing_pairs)}. "
                f"Download job ID: {download_job_id}. "
                f"Details: {detail_suffix}. "
                "Please wait for download to complete and retry the backtest."
            ),
        )

    save_last_config(req.model_dump())

    run_id = start_backtest(
        strategy=req.strategy,
        pairs=normalized_pairs,
        timeframe=req.timeframe,
        timerange=req.timerange,
        strategy_params=req.strategy_params,
        exchange=exchange_name,
        strategy_path=req.strategy_path,
        strategy_label=req.strategy_label,
        command_override=req.command_override,
        extra_meta={
            "parent_run_id": req.parent_run_id,
            "improvement_source": req.improvement_source,
            "improvement_items": req.improvement_items,
            "improvement_applied": req.improvement_applied,
            "improvement_skipped": req.improvement_skipped,
            "improvement_brief": req.improvement_brief,
        },
    )
    return {"run_id": run_id, "status": "running"}


@router.get("/runs")
async def get_runs():
    runs = list_runs()
    return {"runs": runs}


@router.get("/activity")
async def get_activity(limit: int = Query(100, ge=1, le=500)):
    return {"events": load_app_events(limit=limit)}


@router.get("/result-metrics")
async def get_result_metrics():
    return metric_registry_payload()


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    _checked_id(run_id)
    status = get_status(run_id)

    meta = load_run_meta(run_id)
    if not meta and status == "unknown":
        raise HTTPException(status_code=404, detail="Run not found")

    logs = get_logs(run_id)
    results = None

    if status in ("completed", "failed") or (meta and meta.get("status") in ("completed", "failed")):
        results = load_run_results(run_id)
        if results and meta and not has_strategy_intelligence(results):
            parent_run_id = meta.get("parent_run_id")
            parent_results = load_run_results(parent_run_id) if parent_run_id else None
            parent_meta = load_run_meta(parent_run_id) if parent_run_id else None
            intelligence = build_strategy_intelligence(
                run_id=run_id,
                result=results,
                meta=meta,
                parent_result=parent_results,
                parent_meta=parent_meta,
            )
            results = attach_strategy_intelligence(results, intelligence)
            save_run_results(run_id, results)
        if not logs and meta:
            log_path = run_logs_path(get_run_dir(run_id))
            if log_path.exists():
                logs = log_path.read_text().split("\n")

    effective_status = status if status != "unknown" else (meta.get("status", "unknown") if meta else "unknown")

    return {
        "run_id": run_id,
        "status": effective_status,
        "meta": meta,
        "logs": logs[-200:],
        "results": results,
    }


@router.get("/runs/{run_id}/raw")
async def get_run_raw(run_id: str):
    _checked_id(run_id)
    status = get_status(run_id)
    meta = load_run_meta(run_id)
    if not meta and status == "unknown":
        raise HTTPException(status_code=404, detail="Run not found")

    payload = load_run_raw_payload(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Raw payload not available")

    effective_status = status if status != "unknown" else (meta.get("status", "unknown") if meta else "unknown")
    return {
        "run_id": run_id,
        "status": effective_status,
        "meta": meta,
        **payload,
    }



@router.post("/runs/{run_id}/apply-suggestion")
async def apply_strategy_suggestion(run_id: str, req: ApplyStrategySuggestionRequest):
    _checked_id(run_id)
    return await apply_strategy_intelligence_suggestion(
        run_id=run_id,
        suggestion_id=req.suggestion_id,
        provider=req.provider,
    )
@router.post("/runs/{run_id}/apply-config")
async def apply_run_config(run_id: str):
    _checked_id(run_id)
    meta = load_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Run not found")

    cfg = read_config_json()
    applied: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []

    strategy = meta.get("strategy_class") or meta.get("base_strategy") or meta.get("strategy")
    if strategy:
        cfg["strategy"] = strategy
        applied.append("strategy")
    else:
        skipped.append("strategy")
        warnings.append("Strategy is missing in run metadata.")

    for field in ("timeframe", "dry_run_wallet", "max_open_trades", "stake_amount"):
        value = meta.get(field)
        if value is None:
            skipped.append(field)
            continue
        cfg[field] = value
        applied.append(field)

    _write_config_json(cfg)

    last_config_payload = {
        "strategy": strategy,
        "strategy_label": meta.get("strategy"),
        "strategy_base": meta.get("strategy_base") or meta.get("base_strategy") or strategy,
        "version_id": meta.get("version_id") or meta.get("strategy_version"),
        "strategy_version": meta.get("version_id") or meta.get("strategy_version"),
        "strategy_version_path": meta.get("strategy_version_path"),
        "strategy_path": meta.get("strategy_path"),
        "pairs": meta.get("pairs") or [],
        "timeframe": meta.get("timeframe"),
        "timerange": meta.get("timerange"),
        "exchange": meta.get("exchange"),
        "dry_run_wallet": meta.get("dry_run_wallet"),
        "max_open_trades": meta.get("max_open_trades"),
        "stake_amount": meta.get("stake_amount"),
        "strategy_params": meta.get("strategy_params") or {},
    }
    save_last_config(last_config_payload)
    applied.append("last_config")

    strategy_params = meta.get("strategy_params") or {}
    if isinstance(strategy_params, dict) and strategy_params:
        if strategy and _is_default_strategy_path(meta.get("strategy_path")):
            try:
                save_strategy_current_values(
                    strategy,
                    strategy_params,
                    strategies_dir=STRATEGIES_DIR,
                )
                applied.append("strategy_params")
            except Exception as exc:
                warnings.append(f"Failed to write {strategy}.json sidecar: {exc}")
        elif meta.get("strategy_path"):
            skipped.append("strategy_params")
            warnings.append("Skipped strategy params write because run used external strategy_path.")
        else:
            skipped.append("strategy_params")
            warnings.append("Skipped strategy params write because strategy class is missing.")
    else:
        skipped.append("strategy_params")

    append_app_event(
        category="event",
        source="backtest",
        action="apply_config",
        status="ok",
        message=f"Applied run config from {run_id}.",
        run_id=run_id,
        applied=sorted(set(applied)),
        skipped=sorted(set(skipped)),
        warnings=warnings,
    )

    return {
        "run_id": run_id,
        "applied": sorted(set(applied)),
        "skipped": sorted(set(skipped)),
        "warnings": warnings,
    }


@router.delete("/runs/{run_id}")
async def remove_run(run_id: str):
    _checked_id(run_id)
    deleted = delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"deleted": True}


@router.post("/download-data")
async def download_data(req: DownloadDataRequest):
    save_last_config({"download": req.model_dump()})

    job_id = start_download(
        pairs=req.pairs,
        timeframe=req.timeframe,
        timerange=req.timerange,
        command_override=req.command_override,
    )
    return {"job_id": job_id, "status": "running"}


@router.get("/download-data/{job_id}")
async def get_download_status(job_id: str):
    _checked_id(job_id)
    status = get_status(job_id)
    logs = get_logs(job_id)
    return {
        "job_id": job_id,
        "status": status,
        "logs": logs[-200:],
    }


@router.post("/data-coverage")
async def data_coverage(req: DataCoverageRequest):
    exchange_name = resolve_exchange_name(req.exchange)
    coverage, missing_pairs, issue_details = validate_selected_pair_data(
        pairs=normalize_pair_selection(req.pairs),
        timeframe=req.timeframe,
        exchange=exchange_name,
        timerange=req.timerange,
    )
    return {"coverage": coverage, "missing_pairs": missing_pairs, "issue_details": issue_details}


@router.get("/last-config")
async def get_last_config():
    config = load_last_config()
    return {"config": config}


def _scan_local_pairs(exchange: str, timeframe: str | None) -> list[str]:
    from app.core.config import DATA_DIR
    import os
    pairs: set[str] = set()
    for search_dir in [DATA_DIR / exchange, DATA_DIR]:
        if not search_dir.is_dir():
            continue
        for f in os.listdir(search_dir):
            if not f.endswith((".json", ".json.gz", ".feather")):
                continue
            name = f.replace(".json.gz", "").replace(".json", "").replace(".feather", "")
            parts = name.rsplit("-", 1)
            if len(parts) == 2:
                pair_name = parts[0].replace("_", "/")
                tf = parts[1]
                if timeframe and tf != timeframe:
                    continue
                pairs.add(pair_name)
    return sorted(pairs)


def _read_config_pairs() -> list[str]:
    """Read pair_whitelist from configured Freqtrade config."""
    pairs: set[str] = set()
    cfg = read_config_json()
    for source in [
        cfg.get("exchange", {}).get("pair_whitelist", []),
        *[pl.get("pair_whitelist", []) for pl in cfg.get("pairlists", [])],
    ]:
        pairs.update(p for p in source if isinstance(p, str) and "/" in p)
    return sorted(pairs)


_POPULAR_PAIRS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT",
    "MATIC/USDT", "LTC/USDT", "UNI/USDT", "ATOM/USDT", "ETC/USDT",
    "XLM/USDT", "BCH/USDT", "NEAR/USDT", "APT/USDT", "ARB/USDT",
    "OP/USDT", "INJ/USDT", "FTM/USDT", "HBAR/USDT", "VET/USDT",
    "ALGO/USDT", "AAVE/USDT", "ICP/USDT", "GRT/USDT", "FIL/USDT",
    "SAND/USDT", "MANA/USDT", "RUNE/USDT", "EGLD/USDT", "TRX/USDT",
    "WIF/USDT", "PEPE/USDT", "PEOPLE/USDT", "GALA/USDT", "CRV/USDT",
    "1INCH/USDT", "COMP/USDT", "MKR/USDT", "SNX/USDT", "YFI/USDT",
    "ZEC/USDT", "DASH/USDT", "EOS/USDT", "XTZ/USDT", "IOTA/USDT",
]


@router.get("/pairs")
async def get_pairs(
    exchange: str = Query("binance"),
    timeframe: str = Query(None),
):
    local_pairs  = _scan_local_pairs(exchange, timeframe)
    config_pairs = _read_config_pairs()

    # Categorise: local takes priority; config pairs not in local are "config";
    # remaining popular pairs are "suggested"
    local_set   = set(local_pairs)
    config_set  = set(config_pairs) - local_set
    popular_set = set(_POPULAR_PAIRS) - local_set - config_set

    return {
        "pairs": sorted(local_set | config_set | popular_set),
        "local_pairs":  sorted(local_set),
        "config_pairs": sorted(config_set),
        "popular_pairs": sorted(popular_set),
        "has_local_data": bool(local_set),
    }


@router.get("/ohlcv")
async def get_ohlcv(
    pair: str = Query(..., description="Trading pair e.g. BTC/USDT"),
    timeframe: str = Query("5m"),
    exchange: str = Query("binance"),
    timerange: Optional[str] = Query(None),
):
    from app.core.config import VALID_TIMEFRAMES
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    data = load_ohlcv(pair, timeframe, exchange, timerange)
    return {"pair": pair, "timeframe": timeframe, "data": data}


@router.get("/indicators")
async def get_indicators(
    pair: str = Query(..., description="Trading pair e.g. BTC/USDT"),
    timeframe: str = Query("5m"),
    exchange: str = Query("binance"),
    indicators: str = Query("sma_20", description="Comma-separated indicator specs"),
    timerange: Optional[str] = Query(None),
):
    from app.core.config import VALID_TIMEFRAMES
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    indicator_list = [i.strip() for i in indicators.split(",") if i.strip()]
    if not indicator_list:
        raise HTTPException(status_code=400, detail="No indicators specified")
    if len(indicator_list) > 20:
        raise HTTPException(status_code=400, detail="Too many indicators")
    result = calculate_indicators(pair, timeframe, exchange, indicator_list, timerange)
    return result

