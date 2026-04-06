from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.result_artifact_loader import (
    find_run_local_result_artifact,
    load_backtest_result_payload,
)
from app.services.result_extractors import (
    extract_daily_profit,
    extract_equity_curve,
    extract_grouped_rows,
    extract_overview,
    extract_per_pair,
    extract_periodic_breakdown,
    extract_section,
    extract_trades,
)
from app.services.result_parser_schema import (
    BALANCE_METRIC_KEYS,
    CONFIG_SNAPSHOT_KEYS,
    DIAGNOSTIC_KEYS,
    RISK_METRIC_KEYS,
    RUN_METADATA_KEYS,
    SUMMARY_METRIC_KEYS,
)


def empty_backtest_result(error: str, raw_keys: list[str] | None = None) -> dict[str, Any]:
    return {
        "error": error,
        "overview": {},
        "summary_metrics": {},
        "balance_metrics": {},
        "risk_metrics": {},
        "run_metadata": {},
        "config_snapshot": {},
        "diagnostics": {},
        "trades": [],
        "per_pair": [],
        "equity_curve": [],
        "daily_profit": [],
        "exit_reason_summary": [],
        "results_per_enter_tag": [],
        "mix_tag_stats": [],
        "left_open_trades": [],
        "periodic_breakdown": {},
        "warnings": [],
        "raw_artifact": {"available": False},
        "raw_keys": raw_keys or [],
    }


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


__all__ = [
    "empty_backtest_result",
    "find_run_local_result_artifact",
    "load_backtest_result_payload",
    "parse_backtest_results",
]
