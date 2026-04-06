from __future__ import annotations

import math
import statistics
from typing import Any

from app.services.results.summary_normalizer import coalesce, drawdown_to_pct, to_float, to_int


def compute_advanced_metrics(trades: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    profits = [float(trade["profit"]) for trade in trades if trade.get("profit") is not None]
    if len(profits) < 2:
        return {
            "sharpe_ratio": None,
            "sortino_ratio": None,
            "calmar_ratio": None,
            "expectancy": None,
            "recovery_factor": None,
            "profit_std_dev": None,
        }

    mean_profit = statistics.mean(profits)
    std_profit = statistics.stdev(profits)
    sharpe_ratio = round((mean_profit / std_profit) * math.sqrt(252), 4) if std_profit > 0 else None

    losses_only = [profit for profit in profits if profit < 0]
    if len(losses_only) >= 2:
        downside_dev = statistics.stdev(losses_only)
        sortino_ratio = round((mean_profit / downside_dev) * math.sqrt(252), 4) if downside_dev > 0 else None
    else:
        sortino_ratio = None

    total_profit_pct = to_float(summary.get("totalProfitPct"))
    max_drawdown_pct = to_float(summary.get("maxDrawdown"))
    if total_profit_pct is not None and max_drawdown_pct and max_drawdown_pct > 0:
        calmar_ratio = round(total_profit_pct / max_drawdown_pct, 4)
    else:
        calmar_ratio = None

    wins = [profit for profit in profits if profit > 0]
    losses = [profit for profit in profits if profit <= 0]
    if wins and losses:
        avg_win = statistics.mean(wins)
        avg_loss = abs(statistics.mean(losses))
        win_rate = len(wins) / len(profits)
        expectancy = round(avg_win * win_rate - avg_loss * (1 - win_rate), 4)
    elif wins:
        expectancy = round(statistics.mean(wins), 4)
    else:
        expectancy = None

    running = 0.0
    peak = 0.0
    max_drawdown_abs = 0.0
    for profit in profits:
        running += profit
        if running > peak:
            peak = running
        max_drawdown_abs = max(max_drawdown_abs, peak - running)

    net_profit = to_float(summary.get("totalProfit"))
    if net_profit is None:
        net_profit = sum(profits)
    recovery_factor = round(net_profit / max_drawdown_abs, 4) if max_drawdown_abs > 0 else None

    return {
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        "expectancy": expectancy,
        "recovery_factor": recovery_factor,
        "profit_std_dev": round(std_profit, 4) if std_profit > 0 else None,
    }


def normalize_risk_metrics(result: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("risk_metrics") or {})
    normalized = dict(section)
    normalized.update(
        {
            "max_drawdown": drawdown_to_pct(coalesce(section.get("max_drawdown"), summary.get("maxDrawdown"))),
            "max_drawdown_pct": drawdown_to_pct(coalesce(section.get("max_drawdown_account"), section.get("max_drawdown"), summary.get("maxDrawdown"))),
            "max_drawdown_abs": to_float(coalesce(section.get("max_drawdown_abs"), summary.get("maxDrawdownAbs"))),
            "max_drawdown_account": drawdown_to_pct(coalesce(section.get("max_drawdown_account"), summary.get("maxDrawdownAccount"))),
            "max_relative_drawdown": drawdown_to_pct(section.get("max_relative_drawdown")),
            "drawdown_start": section.get("drawdown_start"),
            "drawdown_start_ts": to_float(section.get("drawdown_start_ts")),
            "drawdown_end": section.get("drawdown_end"),
            "drawdown_end_ts": to_float(section.get("drawdown_end_ts")),
            "drawdown_duration": section.get("drawdown_duration"),
            "drawdown_duration_s": to_float(section.get("drawdown_duration_s")),
            "max_drawdown_high": to_float(section.get("max_drawdown_high")),
            "max_drawdown_low": to_float(section.get("max_drawdown_low")),
            "max_consecutive_wins": to_int(section.get("max_consecutive_wins")),
            "max_consecutive_losses": to_int(section.get("max_consecutive_losses")),
        }
    )
    return normalized


__all__ = ["compute_advanced_metrics", "normalize_risk_metrics"]
