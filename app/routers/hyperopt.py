import re
from fastapi import APIRouter, HTTPException

from app.schemas.backtest import HyperoptRequest, ApplyParamsRequest
from app.services.runner import start_hyperopt
from app.services.execution_context_service import (
    build_timerange_context,
    normalize_pair_selection,
    resolve_exchange_name,
    validate_selected_pair_data,
)
from app.services.hyperopt_storage import (
    load_hyperopt_meta, load_hyperopt_results, list_hyperopt_runs, delete_hyperopt_run, get_hyperopt_run_dir,
)
from app.services.runs.base_run_service import run_logs_path
from app.services.hyperopt_parser import save_params_file
from app.core.processes import get_status, get_logs
from app.services.storage import append_app_event

router = APIRouter(prefix="/hyperopt", tags=["hyperopt"])

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

LOSS_FUNCTIONS = [
    {"name": "SharpeHyperOptLossDaily", "label": "Sharpe (Daily)"},
    {"name": "SortinoHyperOptLossDaily", "label": "Sortino (Daily)"},
    {"name": "SharpeHyperOptLoss", "label": "Sharpe"},
    {"name": "OnlyProfitHyperOptLoss", "label": "Only Profit"},
    {"name": "CalmarHyperOptLoss", "label": "Calmar"},
    {"name": "MaxDrawDownHyperOptLoss", "label": "Max Drawdown"},
    {"name": "MaxDrawDownRelativeHyperOptLoss", "label": "Max Drawdown Relative"},
    {"name": "ProfitDrawDownHyperOptLoss", "label": "Profit / Drawdown"},
    {"name": "ShortTradeDurHyperOptLoss", "label": "Short Trade Duration"},
    {"name": "MultiMetricHyperOptLoss", "label": "Multi Metric"},
]

HYPEROPT_SPACES = [
    {"value": "all", "label": "All"},
    {"value": "default", "label": "Default (buy/sell/roi/stoploss)"},
    {"value": "buy", "label": "Buy"},
    {"value": "sell", "label": "Sell"},
    {"value": "roi", "label": "ROI"},
    {"value": "stoploss", "label": "Stoploss"},
    {"value": "trailing", "label": "Trailing Stop"},
    {"value": "protection", "label": "Protection"},
    {"value": "trades", "label": "Trades"},
]


def _checked_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise HTTPException(status_code=400, detail="Invalid run ID")
    return value


@router.post("/run")
async def run_hyperopt(req: HyperoptRequest):
    exchange_name = resolve_exchange_name()
    normalized_pairs = normalize_pair_selection(req.pairs)
    timerange_context = build_timerange_context(req.timerange)

    _, missing_pairs, issue_details = validate_selected_pair_data(
        pairs=normalized_pairs,
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
                "Download data for those pairs before hyperopt. "
                f"Details: {detail_suffix}. "
                f"Timerange context: {timerange_context}"
            ),
        )
    
    run_id = start_hyperopt(
        strategy=req.strategy,
        pairs=normalized_pairs,
        timeframe=req.timeframe,
        timerange=req.timerange,
        epochs=req.epochs,
        spaces=req.spaces,
        loss_function=req.loss_function,
        jobs=req.jobs,
        min_trades=req.min_trades,
        early_stop=req.early_stop,
        dry_run_wallet=req.dry_run_wallet,
        max_open_trades=req.max_open_trades,
        stake_amount=req.stake_amount,
        exchange=exchange_name,
        random_state=req.random_state,
        command_override=req.command_override,
    )
    return {"run_id": run_id, "status": "running"}


@router.get("/runs")
async def get_runs():
    runs = list_hyperopt_runs()
    return {"runs": runs}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    _checked_id(run_id)
    status = get_status(run_id)

    meta = load_hyperopt_meta(run_id)
    if not meta and status == "unknown":
        raise HTTPException(status_code=404, detail="Run not found")

    logs = get_logs(run_id)
    results = None
    progress = None

    if status in ("completed", "failed") or (meta and meta.get("status") in ("completed", "failed")):
        results = load_hyperopt_results(run_id)
        if not logs and meta:
            log_path = run_logs_path(get_hyperopt_run_dir(run_id))
            if log_path.exists():
                logs = log_path.read_text().split("\n")
    elif status == "running":
        progress = _extract_progress(logs, meta)

    effective_status = status if status != "unknown" else (meta.get("status", "unknown") if meta else "unknown")

    return {
        "run_id": run_id,
        "status": effective_status,
        "meta": meta,
        "logs": logs[-500:],
        "results": results,
        "progress": progress,
    }


def _extract_progress(logs: list[str], meta: dict | None) -> dict:
    total_epochs = meta.get("epochs", 0) if meta else 0
    current_epoch = 0
    best_profit = None
    best_loss = None
    best_trades = 0

    for line in reversed(logs or []):
        if not current_epoch:
            m = re.search(r"(\d+)/(\d+)\s*\[", line)
            if m:
                current_epoch = int(m.group(1))
                if not total_epochs:
                    total_epochs = int(m.group(2))

            m2 = re.search(r"Epoch\s+(\d+)", line, re.IGNORECASE)
            if m2 and not current_epoch:
                current_epoch = int(m2.group(1))

        if best_profit is None:
            m = re.search(r"Best profit:\s*([-\d.]+)%", line, re.IGNORECASE)
            if m:
                best_profit = float(m.group(1))

            m2 = re.search(r"best loss:\s*([-\d.]+)", line, re.IGNORECASE)
            if m2:
                best_loss = float(m2.group(1))

        if not best_trades:
            m3 = re.search(r"(\d+)\s+trades", line)
            if m3:
                best_trades = int(m3.group(1))

        if current_epoch and best_profit is not None and best_trades:
            break

    return {
        "current_epoch": current_epoch,
        "total_epochs": total_epochs,
        "best_profit_pct": best_profit,
        "best_loss": best_loss,
        "best_trades": best_trades,
    }


@router.delete("/runs/{run_id}")
async def remove_run(run_id: str):
    _checked_id(run_id)
    deleted = delete_hyperopt_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"deleted": True}


@router.get("/loss-functions")
async def get_loss_functions():
    return {"loss_functions": LOSS_FUNCTIONS}


@router.get("/spaces")
async def get_spaces():
    return {"spaces": HYPEROPT_SPACES}


@router.post("/apply-params")
async def apply_params(req: ApplyParamsRequest):
    if not req.strategy or not req.params:
        raise HTTPException(status_code=400, detail="Strategy and params required")
    try:
        save_params_file(req.strategy, req.params, req.spaces)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write params file: {e}")
    append_app_event(
        category="event",
        source="hyperopt",
        action="apply_params",
        status="ok",
        message=f"Applied hyperopt params for {req.strategy}.",
        strategy=req.strategy,
        spaces=req.spaces,
        param_count=len(req.params or {}),
    )
    return {"applied": True, "strategy": req.strategy, "spaces": req.spaces}
