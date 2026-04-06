import json
import re
import tempfile
import os
from typing import Optional
from pathlib import Path as SysPath

from fastapi import APIRouter, HTTPException, Path, Query

from app.schemas.backtest import BacktestRequest, DownloadDataRequest, DataCoverageRequest, ConfigPatchRequest
from app.services.runner import start_backtest, start_download
from app.services.storage import (
    load_run_meta, load_run_results, list_runs, delete_run,
    save_last_config, load_last_config, save_run_logs, load_run_raw_payload,
)
from app.services.data_coverage import check_data_coverage
from app.services.ohlcv_loader import load_ohlcv
from app.services.indicator_calculator import calculate_indicators
from app.core.processes import get_status, get_logs
from app.core.config import FREQTRADE_CONFIG_FILE, STRATEGIES_DIR

router = APIRouter(tags=["backtest"])

_CONFIG_FILE = FREQTRADE_CONFIG_FILE


def _read_config_json() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def _write_config_json(cfg: dict) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=_CONFIG_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp_path, _CONFIG_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _checked_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise HTTPException(status_code=400, detail="Invalid run/job ID")
    return value


def _resolve_exchange_name(explicit_exchange: Optional[str] = None) -> str:
    if explicit_exchange:
        return explicit_exchange

    cfg = _read_config_json()
    exchange_name = cfg.get("exchange", {})
    if isinstance(exchange_name, dict):
        exchange_name = exchange_name.get("name")

    if isinstance(exchange_name, str) and exchange_name:
        return exchange_name

    return "binance"


def _is_default_strategy_path(strategy_path: Optional[str]) -> bool:
    if not strategy_path:
        return True
    try:
        return SysPath(strategy_path).resolve() == STRATEGIES_DIR.resolve()
    except Exception:
        return False


def _write_strategy_sidecar(strategy: str, params: dict) -> None:
    space_map: dict[str, dict] = {}
    for key, value in params.items():
        if not isinstance(key, str):
            continue
        space = "sell" if key.startswith("sell_") else "buy"
        space_map.setdefault(space, {})[key] = value
    target = STRATEGIES_DIR / f"{strategy}.json"
    target.write_text(json.dumps({"strategy_name": strategy, "params": space_map}, indent=2), encoding="utf-8")


def _validate_selected_pair_data(
    pairs: list[str],
    timeframe: str,
    exchange: str,
    timerange: Optional[str] = None,
) -> tuple[list[dict], list[str], list[str]]:
    coverage = check_data_coverage(
        pairs=pairs,
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


@router.get("/config")
async def get_config():
    cfg = _read_config_json()
    return {
        "strategy": cfg.get("strategy"),
        "max_open_trades": cfg.get("max_open_trades"),
        "dry_run_wallet": cfg.get("dry_run_wallet"),
        "stake_amount": cfg.get("stake_amount"),
        "timeframe": cfg.get("timeframe"),
    }


@router.patch("/config")
async def patch_config(req: ConfigPatchRequest):
    cfg = _read_config_json()
    updates = req.model_dump(exclude_none=True)
    for field, value in updates.items():
        cfg[field] = value
    _write_config_json(cfg)
    return {
        "strategy": cfg.get("strategy"),
        "max_open_trades": cfg.get("max_open_trades"),
        "dry_run_wallet": cfg.get("dry_run_wallet"),
        "stake_amount": cfg.get("stake_amount"),
        "timeframe": cfg.get("timeframe"),
    }


@router.post("/run")
async def run_backtest(req: BacktestRequest):
    exchange_name = _resolve_exchange_name(req.exchange)
    _, missing_pairs, issue_details = _validate_selected_pair_data(
        pairs=req.pairs,
        timeframe=req.timeframe,
        exchange=exchange_name,
        timerange=req.timerange,
    )
    if missing_pairs:
        detail_suffix = " | ".join(issue_details[:5])
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing local market data for selected pairs: "
                f"{', '.join(missing_pairs)}. "
                "Download data for those pairs before backtesting. "
                f"Details: {detail_suffix}"
            ),
        )

    save_last_config(req.model_dump())

    run_id = start_backtest(
        strategy=req.strategy,
        pairs=req.pairs,
        timeframe=req.timeframe,
        timerange=req.timerange,
        strategy_params=req.strategy_params,
        exchange=exchange_name,
        strategy_path=req.strategy_path,
        strategy_label=req.strategy_label,
        command_override=req.command_override,
    )
    return {"run_id": run_id, "status": "running"}


@router.get("/runs")
async def get_runs():
    runs = list_runs()
    return {"runs": runs}


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
        if not logs and meta:
            log_file = meta.get("run_id", "")
            from app.core.config import BACKTEST_RESULTS_DIR
            log_path = BACKTEST_RESULTS_DIR / run_id / "logs.txt"
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


@router.post("/runs/{run_id}/apply-config")
async def apply_run_config(run_id: str):
    _checked_id(run_id)
    meta = load_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Run not found")

    cfg = _read_config_json()
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
        "strategy_version": meta.get("strategy_version"),
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
                _write_strategy_sidecar(strategy, strategy_params)
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
    exchange_name = _resolve_exchange_name(req.exchange)
    coverage, missing_pairs, issue_details = _validate_selected_pair_data(
        pairs=req.pairs,
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
    import json as _json
    cfg_file = FREQTRADE_CONFIG_FILE
    pairs: set[str] = set()
    if cfg_file.exists():
        try:
            cfg = _json.loads(cfg_file.read_text())
            for source in [
                cfg.get("exchange", {}).get("pair_whitelist", []),
                *[pl.get("pair_whitelist", []) for pl in cfg.get("pairlists", [])],
            ]:
                pairs.update(p for p in source if isinstance(p, str) and "/" in p)
        except Exception:
            pass
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
