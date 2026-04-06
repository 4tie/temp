from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.results.empty_result_factory import empty_backtest_result, empty_normalized_result
from app.services.results.metric_registry import build_metric_snapshot
from app.services.results.overview_builder import build_overview, extract_overview
from app.services.results.raw_extractors import (
    extract_daily_profit,
    extract_equity_curve,
    extract_grouped_rows,
    extract_per_pair,
    extract_periodic_breakdown,
    extract_section,
    extract_trades,
)
from app.services.results.raw_loader import load_backtest_result_payload
from app.services.results.risk_normalizer import compute_advanced_metrics, normalize_risk_metrics
from app.services.results.schema_keys import (
    BALANCE_METRIC_KEYS,
    CONFIG_SNAPSHOT_KEYS,
    DIAGNOSTIC_KEYS,
    RISK_METRIC_KEYS,
    RUN_METADATA_KEYS,
    SUMMARY_METRIC_KEYS,
)
from app.services.results.summary_normalizer import (
    build_summary,
    coalesce,
    collect_integrity_warnings,
    has_value,
    merge_unique_warnings,
    normalize_balance_metrics,
    normalize_config_snapshot,
    normalize_diagnostics,
    normalize_run_metadata,
    normalize_summary_metrics,
    to_float,
)
from app.services.results.trade_normalizer import (
    derive_avg_profit_pct_from_trades,
    normalize_daily_profit,
    normalize_per_pair,
    normalize_periodic_breakdown,
    normalize_stat_rows,
    normalize_trade,
)


def parse_backtest_results(result_dir: Path) -> dict[str, Any]:
    bundle = load_backtest_result_payload(result_dir)
    if bundle is None:
        return empty_backtest_result("No result file found")

    raw_payload = bundle["raw_payload"]
    strategy_key = bundle["strategy_name"]
    strat_data = bundle["strategy_data"]
    if not isinstance(strat_data, dict):
        return empty_backtest_result(
            "Unrecognized result format",
            raw_keys=sorted(raw_payload.keys()) if isinstance(raw_payload, dict) else [],
        )

    warnings = list(strat_data.get("backtest_warnings") or [])

    return {
        "overview": extract_overview(strat_data),
        "summary_metrics": extract_section(strat_data, SUMMARY_METRIC_KEYS),
        "balance_metrics": extract_section(strat_data, BALANCE_METRIC_KEYS),
        "risk_metrics": extract_section(strat_data, RISK_METRIC_KEYS),
        "run_metadata": extract_section(strat_data, RUN_METADATA_KEYS),
        "config_snapshot": extract_section(strat_data, CONFIG_SNAPSHOT_KEYS),
        "diagnostics": {
            **extract_section(strat_data, DIAGNOSTIC_KEYS),
            "locks": strat_data.get("locks") or [],
            "warnings": warnings,
            "raw_artifact": bundle["artifact"],
        },
        "trades": extract_trades(strat_data),
        "per_pair": extract_per_pair(strat_data),
        "equity_curve": extract_equity_curve(strat_data),
        "daily_profit": extract_daily_profit(strat_data),
        "exit_reason_summary": extract_grouped_rows(strat_data.get("exit_reason_summary")),
        "results_per_enter_tag": extract_grouped_rows(strat_data.get("results_per_enter_tag")),
        "mix_tag_stats": extract_grouped_rows(strat_data.get("mix_tag_stats")),
        "left_open_trades": extract_grouped_rows(strat_data.get("left_open_trades")),
        "periodic_breakdown": extract_periodic_breakdown(strat_data),
        "warnings": warnings,
        "strategy_name": strategy_key or strat_data.get("strategy_name"),
        "raw_artifact": bundle["artifact"],
    }


def normalize_backtest_result(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return empty_normalized_result()

    normalized = dict(result)
    normalized_trades = [normalize_trade(trade) for trade in result.get("trades") or [] if isinstance(trade, dict)]
    summary = build_summary(result)
    overview = build_overview(summary)
    advanced_metrics = dict(result.get("advanced_metrics") or {})

    computed_advanced = compute_advanced_metrics(normalized_trades, summary)
    for key, value in computed_advanced.items():
        advanced_metrics.setdefault(key, value)

    if not has_value(
        coalesce(
            result.get("summary", {}).get("avgProfitPct"),
            result.get("overview", {}).get("avg_profit_pct"),
            result.get("summary_metrics", {}).get("profit_mean_pct"),
        )
    ):
        derived_avg_pct = derive_avg_profit_pct_from_trades(normalized_trades)
        if derived_avg_pct is not None:
            summary["avgProfitPct"] = derived_avg_pct
            summary["avg_profit_pct"] = derived_avg_pct
            overview["avg_profit_pct"] = derived_avg_pct

    sharpe = coalesce(summary.get("sharpe_ratio"), advanced_metrics.get("sharpe_ratio"))
    summary["sharpe_ratio"] = sharpe
    summary["sharpeRatio"] = sharpe
    overview["sharpe_ratio"] = sharpe

    starting_balance = to_float(summary.get("startingBalance"))
    normalized_per_pair = [
        normalize_per_pair(entry, starting_balance=starting_balance)
        for entry in result.get("per_pair") or []
        if isinstance(entry, dict)
    ]
    summary_metrics = normalize_summary_metrics(result, summary)
    balance_metrics = normalize_balance_metrics(result, summary)
    risk_metrics = normalize_risk_metrics(result, summary)
    run_metadata = normalize_run_metadata(result, summary)
    integrity_warnings, summary, balance_metrics = collect_integrity_warnings(
        result=result,
        summary=summary,
        balance_metrics=balance_metrics,
        run_metadata=run_metadata,
    )
    overview = build_overview(summary)
    config_snapshot = normalize_config_snapshot(result)
    diagnostics = normalize_diagnostics(result)
    diagnostics["warnings"] = merge_unique_warnings(diagnostics.get("warnings") or [], integrity_warnings)
    diagnostics["integrity_warnings"] = integrity_warnings
    daily_profit = normalize_daily_profit(result)
    periodic_breakdown = normalize_periodic_breakdown(result)
    raw_artifact = diagnostics["raw_artifact"]

    normalized.update(
        {
            "summary": summary,
            "overview": overview,
            "result_metrics": {},
            "advanced_metrics": advanced_metrics,
            "summary_metrics": summary_metrics,
            "balance_metrics": balance_metrics,
            "risk_metrics": risk_metrics,
            "run_metadata": run_metadata,
            "config_snapshot": config_snapshot,
            "diagnostics": diagnostics,
            "trades": normalized_trades,
            "per_pair": normalized_per_pair,
            "equity_curve": daily_profit,
            "daily_profit": daily_profit,
            "exit_reason_summary": normalize_stat_rows(result.get("exit_reason_summary") or [], starting_balance=starting_balance),
            "results_per_enter_tag": normalize_stat_rows(result.get("results_per_enter_tag") or [], starting_balance=starting_balance),
            "mix_tag_stats": normalize_stat_rows(result.get("mix_tag_stats") or [], starting_balance=starting_balance),
            "left_open_trades": normalize_stat_rows(result.get("left_open_trades") or [], starting_balance=starting_balance),
            "periodic_breakdown": periodic_breakdown,
            "warnings": merge_unique_warnings(result.get("warnings") or [], diagnostics.get("warnings") or []),
            "raw_artifact": raw_artifact,
        }
    )
    normalized["result_metrics"] = build_metric_snapshot(normalized)
    if "strategy" not in normalized and result.get("strategy_name"):
        normalized["strategy"] = result.get("strategy_name")
    return normalized


__all__ = ["normalize_backtest_result", "parse_backtest_results"]
