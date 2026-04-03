import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query

from app.schemas.backtest import BacktestRequest, DownloadDataRequest, DataCoverageRequest
from app.services.runner import start_backtest, start_download
from app.services.storage import (
    load_run_meta, load_run_results, list_runs, delete_run,
    save_last_config, load_last_config, save_run_logs,
)
from app.services.data_coverage import check_data_coverage
from app.services.ohlcv_loader import load_ohlcv
from app.services.indicator_calculator import calculate_indicators
from app.core.processes import get_status, get_logs

router = APIRouter(tags=["backtest"])

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _checked_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise HTTPException(status_code=400, detail="Invalid run/job ID")
    return value


@router.post("/run")
async def run_backtest(req: BacktestRequest):
    save_last_config(req.model_dump())

    run_id = start_backtest(
        strategy=req.strategy,
        pairs=req.pairs,
        timeframe=req.timeframe,
        timerange=req.timerange,
        dry_run_wallet=req.dry_run_wallet,
        max_open_trades=req.max_open_trades,
        stake_amount=req.stake_amount,
        exchange=req.exchange,
        strategy_params=req.strategy_params,
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
        exchange=req.exchange,
        days=req.days,
        timerange=req.timerange,
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
    coverage = check_data_coverage(
        pairs=req.pairs,
        timeframe=req.timeframe,
        exchange=req.exchange,
    )
    return {"coverage": coverage}


@router.get("/last-config")
async def get_last_config():
    config = load_last_config()
    return {"config": config}


@router.get("/pairs")
async def get_pairs(
    exchange: str = Query("binance"),
    timeframe: str = Query(None),
):
    from app.core.config import DATA_DIR
    import os
    pairs = set()
    search_dirs = [DATA_DIR / exchange, DATA_DIR]
    for search_dir in search_dirs:
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
    return {"pairs": sorted(pairs)}


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
