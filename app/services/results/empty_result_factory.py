from __future__ import annotations

from typing import Any


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


def empty_normalized_result() -> dict[str, Any]:
    return {
        "summary": {},
        "overview": {},
        "result_metrics": {},
        "advanced_metrics": {},
        "summary_metrics": {},
        "balance_metrics": {},
        "risk_metrics": {},
        "run_metadata": {},
        "config_snapshot": {},
        "diagnostics": {"raw_artifact": {"available": False}, "warnings": []},
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
    }


__all__ = ["empty_backtest_result", "empty_normalized_result"]
