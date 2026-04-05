"""
Fitness scoring — converts a parsed backtest result into a single 0-100 scalar.

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


@dataclass
class FitnessScore:
    value: float                  # 0–100
    breakdown: dict[str, float]   # component scores


def compute_fitness(backtest_result: dict) -> FitnessScore:
    """
    Compute fitness from a parsed backtest result dict.

    Expects the same structure produced by result_parser / services/storage:
      backtest_result["summary"]          → summary metrics
      backtest_result["advanced_metrics"] → sharpe_ratio etc.
      backtest_result["trades"]           → list of trade dicts
    """
    summary: dict = backtest_result.get("summary") or {}
    advanced: dict = backtest_result.get("advanced_metrics") or {}
    trades: list = backtest_result.get("trades") or []

    n_trades = len(trades)
    if n_trades < 20:
        return FitnessScore(value=0.0, breakdown={"reason": "insufficient_trades", "n_trades": n_trades})

    # ── Profit factor (0–20) ──────────────────────────────────────────────────
    pf = float(summary.get("profitFactor") or 0.0)
    pf_score = min(pf / 2.0, 1.0) * 20.0

    # ── Sharpe ratio (0–15) ───────────────────────────────────────────────────
    sharpe = advanced.get("sharpe_ratio")
    if sharpe is None:
        sharpe = float(summary.get("sharpeRatio") or 0.0)
    sharpe = float(sharpe)
    sharpe_score = min(max(sharpe, 0.0) / 2.0, 1.0) * 15.0

    # ── Drawdown (0–25) ───────────────────────────────────────────────────────
    dd = float(summary.get("maxDrawdown") or 0.0)          # already a percentage
    dd_score = max(0.0, 1.0 - dd / 50.0) * 25.0

    # ── Win rate (0–20) ───────────────────────────────────────────────────────
    wr = float(summary.get("winRate") or 0.0)              # already a percentage
    wr_score = min(wr * 0.2, 20.0)

    # ── Trade count bonus (0–20) ──────────────────────────────────────────────
    trade_score = min(math.log10(max(n_trades, 1)) * 5.0, 20.0)

    total = pf_score + sharpe_score + dd_score + wr_score + trade_score

    return FitnessScore(
        value=round(total, 2),
        breakdown={
            "profit_factor_score": round(pf_score, 2),
            "sharpe_score": round(sharpe_score, 2),
            "drawdown_score": round(dd_score, 2),
            "win_rate_score": round(wr_score, 2),
            "trade_bonus_score": round(trade_score, 2),
            "profit_factor": round(pf, 4),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown_pct": round(dd, 2),
            "win_rate_pct": round(wr, 2),
            "n_trades": n_trades,
        },
    )


from app.services.result_normalizer import normalize_backtest_result as _normalize_backtest_result


@dataclass
class FitnessScore:
    value: float
    breakdown: dict[str, float | int | str]


def compute_fitness(backtest_result: dict) -> FitnessScore:
    normalized = _normalize_backtest_result(backtest_result)
    summary: dict = normalized.get("summary") or {}
    advanced: dict = normalized.get("advanced_metrics") or {}
    trades: list = normalized.get("trades") or []

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
