from fastapi import APIRouter, HTTPException

from app.schemas.backtest import CompareRequest
from app.services.results.comparison_metrics import compare_results
from app.services.results.metric_registry import build_metric_snapshot
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
    metrics_a = results_a.get("result_metrics") or build_metric_snapshot(results_a)
    metrics_b = results_b.get("result_metrics") or build_metric_snapshot(results_b)
    diff = compare_results(results_a, results_b)

    return {
        "run_a": {
            "run_id": req.run_id_a,
            "meta": meta_a,
            "overview": overview_a,
            "result_metrics": metrics_a,
            "trade_count": len(results_a.get("trades", [])),
            "per_pair": results_a.get("per_pair", []),
        },
        "run_b": {
            "run_id": req.run_id_b,
            "meta": meta_b,
            "overview": overview_b,
            "result_metrics": metrics_b,
            "trade_count": len(results_b.get("trades", [])),
            "per_pair": results_b.get("per_pair", []),
        },
        "diff": diff,
    }
