from fastapi import APIRouter, HTTPException

from app.schemas.backtest import CompareRequest
from app.services.storage import load_run_results, load_run_meta

router = APIRouter(prefix="/compare", tags=["compare"])


@router.post("")
async def compare_runs(req: CompareRequest):
    results_a = load_run_results(req.run_id_a)
    results_b = load_run_results(req.run_id_b)

    if not results_a:
        raise HTTPException(status_code=404, detail=f"Results not found for run {req.run_id_a}")
    if not results_b:
        raise HTTPException(status_code=404, detail=f"Results not found for run {req.run_id_b}")

    meta_a = load_run_meta(req.run_id_a) or {}
    meta_b = load_run_meta(req.run_id_b) or {}

    overview_a = results_a.get("overview", {})
    overview_b = results_b.get("overview", {})

    diff = {}
    numeric_keys = [
        "total_trades", "profit_total", "profit_total_abs", "profit_percent",
        "profit_factor", "win_rate", "max_drawdown", "max_drawdown_abs",
        "avg_profit_pct", "starting_balance", "final_balance", "trading_volume",
    ]
    for key in numeric_keys:
        val_a = overview_a.get(key, 0) or 0
        val_b = overview_b.get(key, 0) or 0
        try:
            diff[key] = {
                "a": val_a,
                "b": val_b,
                "diff": round(float(val_b) - float(val_a), 4),
            }
        except (TypeError, ValueError):
            diff[key] = {"a": val_a, "b": val_b, "diff": None}

    return {
        "run_a": {
            "run_id": req.run_id_a,
            "meta": meta_a,
            "overview": overview_a,
            "trade_count": len(results_a.get("trades", [])),
            "per_pair": results_a.get("per_pair", []),
        },
        "run_b": {
            "run_id": req.run_id_b,
            "meta": meta_b,
            "overview": overview_b,
            "trade_count": len(results_b.get("trades", [])),
            "per_pair": results_b.get("per_pair", []),
        },
        "diff": diff,
    }
