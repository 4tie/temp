from app.services.results.comparison_metrics import compare_overviews, compare_results
from app.services.results.empty_result_factory import empty_backtest_result, empty_normalized_result
from app.services.results.metric_registry import (
    AI_CONTEXT_METRICS,
    AI_LOOP_REPORT_METRICS,
    CORE_RESULT_METRICS,
    RESULTS_TABLE_METRICS,
    build_metric_delta_rows,
    build_metric_snapshot,
    extract_metric_value,
    get_metric_def,
    iter_metric_defs,
    metric_registry_payload,
)
from app.services.results.raw_loader import find_run_local_result_artifact, load_backtest_result_payload
from app.services.results.result_service import (
    build_compact_backtest_result,
    load_saved_backtest_result,
    load_stored_backtest_results,
    normalize_backtest_result,
    parse_backtest_results,
    should_rehydrate_backtest_result,
)

__all__ = [
    "AI_CONTEXT_METRICS",
    "AI_LOOP_REPORT_METRICS",
    "CORE_RESULT_METRICS",
    "RESULTS_TABLE_METRICS",
    "build_metric_delta_rows",
    "build_metric_snapshot",
    "compare_overviews",
    "compare_results",
    "empty_backtest_result",
    "empty_normalized_result",
    "extract_metric_value",
    "find_run_local_result_artifact",
    "get_metric_def",
    "iter_metric_defs",
    "build_compact_backtest_result",
    "load_saved_backtest_result",
    "load_stored_backtest_results",
    "load_backtest_result_payload",
    "metric_registry_payload",
    "normalize_backtest_result",
    "parse_backtest_results",
    "should_rehydrate_backtest_result",
]
