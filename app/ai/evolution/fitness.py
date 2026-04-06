"""
Fitness scoring — converts a normalized backtest result into a single 0-100 scalar.

Weights
-------
  profit_factor  × 20   (capped at PF 2.0 → 20 pts)
  sharpe_ratio   × 15   (capped at SR 2.0 → 15 pts)
  drawdown       × 25   (0 % DD → 25 pts, 50 % DD → 0 pts, linear)
  win_rate       × 20   (win_rate% × 0.2, max 20 pts)
  trade_bonus    × 20   (log10(n) × 5, capped at 20 pts)

Returns 0 for fewer than 20 trades (insufficient data).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.services.results.result_service import normalize_backtest_result


@dataclass
class FitnessScore:
    value: float
    breakdown: dict[str, float | int | str]


def compute_fitness(backtest_result: dict[str, Any]) -> FitnessScore:
    normalized = normalize_backtest_result(backtest_result)
    summary: dict[str, Any] = normalized.get("summary") or {}
    advanced: dict[str, Any] = normalized.get("advanced_metrics") or {}
    trades: list[dict[str, Any]] = normalized.get("trades") or []

    n_trades = len(trades)
    if n_trades < 20:
        return FitnessScore(
            value=0.0,
            breakdown={"reason": "insufficient_trades", "n_trades": n_trades},
        )

    profit_factor = float(summary.get("profitFactor") or 0.0)
    profit_factor_score = min(profit_factor, 2.0) / 2.0 * 20.0

    sharpe_ratio = advanced.get("sharpe_ratio")
    if sharpe_ratio is None:
        sharpe_ratio = summary.get("sharpeRatio")
    sharpe_ratio = float(sharpe_ratio or 0.0)
    sharpe_score = min(max(sharpe_ratio, 0.0), 2.0) / 2.0 * 15.0

    max_drawdown = float(summary.get("maxDrawdown") or 0.0)
    drawdown_score = max(0.0, 25.0 - (max_drawdown / 2.0))

    win_rate = float(summary.get("winRate") or 0.0)
    win_rate_score = min(win_rate * 0.2, 20.0)

    trade_bonus_score = math.log10(max(n_trades, 1)) * 5.0

    total = profit_factor_score + sharpe_score + drawdown_score + win_rate_score + trade_bonus_score
    total = max(0.0, min(total, 100.0))

    return FitnessScore(
        value=round(total, 2),
        breakdown={
            "profit_factor_score": round(profit_factor_score, 2),
            "sharpe_score": round(sharpe_score, 2),
            "drawdown_score": round(drawdown_score, 2),
            "win_rate_score": round(win_rate_score, 2),
            "trade_bonus_score": round(trade_bonus_score, 2),
            "profit_factor": round(profit_factor, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "max_drawdown_pct": round(max_drawdown, 2),
            "win_rate_pct": round(win_rate, 2),
            "n_trades": n_trades,
        },
    )
