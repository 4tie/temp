"""
Deep Backtest Analysis Engine — evidence-based, strict output rules.
Never invents data. Returns "insufficient evidence" when data is absent.
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
import statistics
import threading
from collections import defaultdict
from math import sqrt
from typing import Any

from app.core.config import BACKTEST_RESULTS_DIR, STRATEGIES_DIR
from app.services.results.result_service import normalize_backtest_result

logger = logging.getLogger(__name__)

INSUFFICIENT = "insufficient evidence"
LOW_TRADE_THRESHOLD = 30

STRAT_DIR = STRATEGIES_DIR

# ─────────────────────────────────────────────────────────────────────────────
# AI Narrative Cache (module-level, FIFO eviction at 100 entries)
# ─────────────────────────────────────────────────────────────────────────────

_NARRATIVE_CACHE: dict[str, dict] = {}
_NARRATIVE_CACHE_ORDER: list[str] = []
_NARRATIVE_CACHE_MAX = 100
_NARRATIVE_CACHE_DIR = BACKTEST_RESULTS_DIR


def _narrative_cache_get(run_id: str) -> dict | None:
    return _NARRATIVE_CACHE.get(run_id)


def _narrative_cache_set(run_id: str, narrative: dict) -> None:
    if run_id in _NARRATIVE_CACHE:
        _NARRATIVE_CACHE_ORDER.remove(run_id)
    elif len(_NARRATIVE_CACHE) >= _NARRATIVE_CACHE_MAX:
        oldest = _NARRATIVE_CACHE_ORDER.pop(0)
        _NARRATIVE_CACHE.pop(oldest, None)
    _NARRATIVE_CACHE[run_id] = narrative
    _NARRATIVE_CACHE_ORDER.append(run_id)
    try:
        _NARRATIVE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = _NARRATIVE_CACHE_DIR / f"{run_id}_narrative_cache.json"
        cache_file.write_text(json.dumps(narrative), encoding="utf-8")
    except Exception:
        pass


def _narrative_cache_load_from_disk(run_id: str) -> dict | None:
    try:
        cache_file = _NARRATIVE_CACHE_DIR / f"{run_id}_narrative_cache.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            _narrative_cache_set(run_id, data)
            return data
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def analyze(run: dict, run_id: str = "", include_ai_narrative: bool = False) -> dict:
    run = normalize_backtest_result(run)
    trades: list[dict] = run.get("trades") or []
    summary: dict = run.get("summary") or {}
    strategy_name: str = run.get("strategy", "")

    data_warnings: list[dict] = []

    # Read strategy source
    strategy_source = _read_strategy_source(strategy_name)

    # Data warnings
    if len(trades) < LOW_TRADE_THRESHOLD:
        data_warnings.append({
            "issue": f"Only {len(trades)} trade(s) available (fewer than {LOW_TRADE_THRESHOLD})",
            "impact": "All confidence levels are reduced; statistical conclusions may not be reliable.",
        })

    has_mae_mfe = any(t.get("maePct") is not None and t.get("mfePct") is not None for t in trades)
    if not has_mae_mfe:
        data_warnings.append({
            "issue": "MAE/MFE (Maximum Adverse/Favorable Excursion) data not provided",
            "impact": "Trade quality scoring and MAE vs MFE chart are unavailable.",
        })

    low_data = len(trades) < LOW_TRADE_THRESHOLD

    # Compute all sections
    # code_audit runs first so stoploss evidence can inform health scoring
    code_audit = _audit_code(strategy_source, strategy_name)
    advanced_metrics = _compute_advanced_metrics(trades, summary)
    health = _compute_health_score(trades, summary, has_mae_mfe, low_data, code_audit, advanced_metrics)
    strengths, weaknesses = _compute_findings(trades, summary, low_data)
    per_pair = _compute_per_pair_stats(trades, low_data, strengths, weaknesses)
    strengths = per_pair.pop("_strengths", strengths)
    weaknesses = per_pair.pop("_weaknesses", weaknesses)
    signal_issues = _detect_signal_issues(trades)
    param_recs = _compute_param_recommendations(trades, summary, strategy_source, low_data)
    # Merge signal issues into code_audit
    code_audit = list(code_audit) + signal_issues
    analysis = _compute_analysis(trades, summary, has_mae_mfe, low_data)

    best_worst_trades = _compute_best_worst_trades(trades)
    concentration_risk = _compute_concentration_risk(trades, per_pair)
    regime_analysis = _compute_regime_analysis(trades)
    drawdown_recovery = _compute_drawdown_recovery(trades)
    trade_clustering = _compute_trade_clustering(trades)

    run_config = run.get("config") or {} if isinstance(run, dict) else {}

    overfitting = _detect_overfitting(trades)
    loss_patterns = _analyze_loss_patterns(trades)
    signal_frequency = _analyze_signal_frequency(trades, summary, run_config, strategy_source)
    exit_quality = _analyze_exit_quality(trades, summary)
    root_cause_diagnosis = _diagnose_root_causes(
        trades, summary, analysis, advanced_metrics or {}, code_audit, strategy_source, run_config, overfitting
    )

    narrative = _compute_narrative(
        trades, summary, health, strengths, weaknesses, analysis,
        strategy_name, low_data, advanced_metrics,
        root_cause_diagnosis, loss_patterns, signal_frequency, exit_quality, overfitting
    )

    # Try AI narrative (with caching); fall back to deterministic on any error
    if include_ai_narrative:
        ai_narrative = _try_ai_narrative(
            run_id=run_id,
            run=run,
            summary=summary,
            strategy_name=strategy_name,
            trades=trades,
            advanced_metrics=advanced_metrics,
            root_cause_diagnosis=root_cause_diagnosis,
            loss_patterns=loss_patterns,
            signal_frequency=signal_frequency,
            exit_quality=exit_quality,
            overfitting=overfitting,
            strengths=strengths,
            weaknesses=weaknesses,
            deterministic_narrative=narrative,
        )
    else:
        ai_narrative = dict(narrative)
        ai_narrative["ai_narrative"] = False

    return {
        "health_score": health,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "code_audit": code_audit,
        "parameter_recommendations": param_recs,
        "analysis": analysis,
        "data_warnings": data_warnings,
        "narrative": ai_narrative,
        "trade_count": len(trades),
        "has_mae_mfe": has_mae_mfe,
        "advanced_metrics": advanced_metrics,
        "per_pair": per_pair,
        "best_worst_trades": best_worst_trades,
        "concentration_risk": concentration_risk,
        "regime_analysis": regime_analysis,
        "drawdown_recovery": drawdown_recovery,
        "trade_clustering": trade_clustering,
        "root_cause_diagnosis": root_cause_diagnosis,
        "loss_patterns": loss_patterns,
        "signal_frequency": signal_frequency,
        "exit_quality": exit_quality,
        "overfitting": overfitting,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Health score
# ─────────────────────────────────────────────────────────────────────────────

def _compute_health_score(trades: list[dict], summary: dict, has_mae_mfe: bool, low_data: bool, code_audit: list[dict] | None = None, advanced_metrics: dict | None = None) -> dict:
    if not trades:
        return {
            "total": 0,
            "components": {
                "profitability": 0, "risk_control": 0, "consistency": 0,
                "trade_quality": 0, "stability": 0, "edge_quality": 0,
            },
            "explanation": "No trades to score.",
        }

    # Only use summary fields that are actually present and non-None
    total_profit_pct_raw = summary.get("totalProfitPct")
    avg_profit_raw = summary.get("avgProfit")
    profit_factor_raw = summary.get("profitFactor")
    max_drawdown_raw = summary.get("maxDrawdown")

    has_profit_data = total_profit_pct_raw is not None
    has_pf_data = profit_factor_raw is not None

    # 1. Profitability (0–20)
    if not has_profit_data:
        p_score = 0
        p_explanation = INSUFFICIENT
    else:
        total_profit_pct = float(total_profit_pct_raw)
        avg_profit = float(avg_profit_raw) if avg_profit_raw is not None else 0.0
        profit_factor = float(profit_factor_raw) if has_pf_data else 0.0

        p_score = 0
        if total_profit_pct > 20:
            p_score = 20
        elif total_profit_pct > 10:
            p_score = 16
        elif total_profit_pct > 5:
            p_score = 12
        elif total_profit_pct > 0:
            p_score = 8
        else:
            p_score = max(0, 4 + int(total_profit_pct))

        if has_pf_data:
            if profit_factor >= 2.0:
                p_score = min(20, p_score + 4)
            elif profit_factor >= 1.5:
                p_score = min(20, p_score + 2)

        p_explanation = (
            f"Total return {total_profit_pct:+.2f}%, avg profit/trade ${avg_profit:.2f}"
            + (f", profit factor {profit_factor:.2f}." if has_pf_data else ".")
        )

    # 2. Risk control (0–20) — only use trades with actual profit data
    trades_with_profit = [t for t in trades if t.get("profit") is not None]
    won = [t for t in trades_with_profit if t["profit"] > 0]
    lost = [t for t in trades_with_profit if t["profit"] <= 0]

    # avg_win / avg_loss are only valid when there are actual trades in each group
    avg_win: float | None = statistics.mean([t["profit"] for t in won]) if won else None
    avg_loss: float | None = statistics.mean([t["profit"] for t in lost]) if lost else None

    # Drawdown only from summary (requires summary to have provided it)
    max_drawdown: float | None = float(max_drawdown_raw) if max_drawdown_raw is not None else None

    # Stoploss presence from code audit (if code_audit is provided)
    # Penalize risk_control when stoploss is missing (-6pts) or very wide (-3pts)
    sl_missing = any(
        i.get("issue") == "Missing stoploss definition"
        for i in (code_audit or [])
    )
    sl_very_wide = any(
        i.get("issue") == "Very wide stoploss"
        for i in (code_audit or [])
    )

    if max_drawdown is None and avg_win is None:
        r_score = 0
        r_explanation = INSUFFICIENT
    else:
        r_score = 20
        if max_drawdown is not None:
            if max_drawdown > 40:
                r_score -= 12
            elif max_drawdown > 25:
                r_score -= 8
            elif max_drawdown > 15:
                r_score -= 4
            elif max_drawdown > 10:
                r_score -= 2

        if avg_win is not None and avg_loss is not None and avg_loss != 0 and abs(avg_loss) > avg_win:
            r_score -= 4

        # Stoploss code evidence
        if sl_missing:
            r_score -= 6
        elif sl_very_wide:
            r_score -= 3

        r_score = max(0, r_score)

        dd_str = f"Max drawdown {max_drawdown:.2f}%." if max_drawdown is not None else "Drawdown data unavailable."
        rr_str_r = (
            f"Avg win ${avg_win:.2f} vs avg loss ${avg_loss:.2f}."
            if avg_win is not None and avg_loss is not None
            else "Win/loss amounts unavailable."
        )
        sl_str = (
            " Stoploss not defined in code (high risk)."
            if sl_missing
            else (" Very wide stoploss detected." if sl_very_wide else "")
        )
        r_explanation = f"{dd_str} {rr_str_r}{sl_str}"

    # 3. Consistency (0–20)
    trades_with_profit = [t for t in trades if t.get("profit") is not None]
    if len(trades_with_profit) >= 5:
        profits = [t["profit"] for t in trades_with_profit]
        win_flags = [1 if p > 0 else 0 for p in profits]
        streak_lengths = _compute_streak_lengths(win_flags)
        max_losing_streak = max((s for t, s in streak_lengths if t == "loss"), default=0)
        rolling_wrs = _rolling_win_rate(win_flags, window=10)
        wr_std = statistics.stdev(rolling_wrs) * 100 if len(rolling_wrs) >= 2 else 0

        c_score = 20
        if max_losing_streak > 10:
            c_score -= 10
        elif max_losing_streak > 6:
            c_score -= 6
        elif max_losing_streak > 4:
            c_score -= 3

        if wr_std > 30:
            c_score -= 6
        elif wr_std > 20:
            c_score -= 3
        c_score = max(0, c_score)
        c_explanation = (
            f"Max consecutive losses: {max_losing_streak}. "
            f"Rolling win-rate standard deviation: {wr_std:.1f}%."
        )
    else:
        c_score = 0
        c_explanation = INSUFFICIENT

    # 4. Trade quality (0–20)
    # Only use MAE/MFE when the fields are actually present (not None)
    mae_vals_raw = [t["maePct"] for t in trades if t.get("maePct") is not None] if has_mae_mfe else []
    mfe_vals_raw = [t["mfePct"] for t in trades if t.get("mfePct") is not None] if has_mae_mfe else []
    can_use_mae_mfe = has_mae_mfe and len(mae_vals_raw) >= 3 and len(mfe_vals_raw) >= 3

    # avg_win / avg_loss are already None-safe from the earlier computation
    can_use_rr = avg_win is not None and avg_loss is not None and avg_loss != 0

    if can_use_mae_mfe:
        avg_mae = statistics.mean(mae_vals_raw)
        avg_mfe = statistics.mean(mfe_vals_raw)

        mfe_mae_ratio = avg_mfe / avg_mae if avg_mae > 0 else 0
        q_score = 10
        if mfe_mae_ratio >= 2.0:
            q_score = 20
        elif mfe_mae_ratio >= 1.5:
            q_score = 16
        elif mfe_mae_ratio >= 1.0:
            q_score = 12
        elif mfe_mae_ratio >= 0.5:
            q_score = 8

        if can_use_rr:
            rr = abs(avg_win / avg_loss)  # type: ignore[operator]
            if rr >= 2.0:
                q_score = min(20, q_score + 4)
            elif rr >= 1.5:
                q_score = min(20, q_score + 2)

        rr_str = f"{abs(avg_win / avg_loss):.2f}" if can_use_rr else "N/A"  # type: ignore[operator]
        q_explanation = (
            f"Avg MAE {avg_mae:.2f}%, avg MFE {avg_mfe:.2f}%. "
            f"MFE/MAE ratio {mfe_mae_ratio:.2f}. "
            f"Risk/reward {rr_str}."
        )
    elif can_use_rr:
        rr = abs(avg_win / avg_loss)  # type: ignore[operator]
        if rr >= 2.0:
            q_score = 18
        elif rr >= 1.5:
            q_score = 14
        elif rr >= 1.0:
            q_score = 10
        else:
            q_score = 5
        q_explanation = (
            f"MAE/MFE data unavailable. Risk/reward estimated from avg win vs avg loss: {rr:.2f}."
        )
    else:
        q_score = 0
        q_explanation = INSUFFICIENT

    # 5. Stability (0–20)
    # Re-use trades_with_profit computed above (only trades with actual profit data)
    if len(trades_with_profit) >= 10:
        profits = [t["profit"] for t in trades_with_profit]
        win_flags = [1 if p > 0 else 0 for p in profits]
        rolling = _rolling_win_rate(win_flags, window=max(5, len(win_flags) // 5))
        if len(rolling) >= 3:
            first_half_mean = statistics.mean(rolling[:len(rolling)//2])
            second_half_mean = statistics.mean(rolling[len(rolling)//2:])
            degradation = first_half_mean - second_half_mean

            s_score = 20
            if degradation > 0.25:
                s_score -= 12
            elif degradation > 0.15:
                s_score -= 8
            elif degradation > 0.05:
                s_score -= 4
            s_score = max(0, s_score)
            s_explanation = (
                f"Early win rate {first_half_mean*100:.1f}% vs late win rate {second_half_mean*100:.1f}%. "
                f"Degradation: {degradation*100:.1f} percentage points."
            )
        else:
            s_score = 10
            s_explanation = INSUFFICIENT + " — fewer than 3 rolling windows for robust stability analysis."
    else:
        s_score = 0
        s_explanation = INSUFFICIENT

    # 6. Edge Quality (0–20) — Sharpe-based scoring
    am = advanced_metrics or {}
    sharpe = am.get("sharpe_ratio")
    expectancy = am.get("expectancy")

    if sharpe is None and expectancy is None:
        e_score = 0
        e_explanation = INSUFFICIENT
    else:
        e_score = 0
        if sharpe is not None:
            if sharpe >= 2.0:
                e_score = 16
            elif sharpe >= 1.0:
                e_score = 12
            elif sharpe >= 0.5:
                e_score = 8
            elif sharpe >= 0.0:
                e_score = 4
            else:
                e_score = 0

        if expectancy is not None and expectancy > 0:
            e_score = min(20, e_score + 4)

        e_parts = []
        if sharpe is not None:
            e_parts.append(f"Sharpe ratio {sharpe:.2f}")
        if expectancy is not None:
            e_parts.append(f"Expectancy {expectancy:+.4f}")
        e_explanation = ". ".join(e_parts) + "." if e_parts else INSUFFICIENT

    if low_data:
        p_score = int(p_score * 0.8)
        r_score = int(r_score * 0.8)
        c_score = int(c_score * 0.8)
        q_score = int(q_score * 0.8)
        s_score = int(s_score * 0.8)
        e_score = int(e_score * 0.8)

    total = p_score + r_score + c_score + q_score + s_score + e_score

    return {
        "total": total,
        "components": {
            "profitability": p_score,
            "risk_control": r_score,
            "consistency": c_score,
            "trade_quality": q_score,
            "stability": s_score,
            "edge_quality": e_score,
        },
        "explanation": {
            "profitability": p_explanation,
            "risk_control": r_explanation,
            "consistency": c_explanation,
            "trade_quality": q_explanation,
            "stability": s_explanation,
            "edge_quality": e_explanation,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Strengths / Weaknesses
# ─────────────────────────────────────────────────────────────────────────────

def _compute_findings(trades: list[dict], summary: dict, low_data: bool) -> tuple[list[dict], list[dict]]:
    strengths: list[dict] = []
    weaknesses: list[dict] = []
    confidence = "low" if low_data else "medium"

    if not trades:
        return [], [{"title": "No trades", "evidence": "The backtest produced zero closed trades.", "impact": "No analysis possible.", "confidence": "high"}]

    # Use None for absent summary fields (never default to 0 for missing data)
    win_rate = summary.get("winRate")
    total_profit_pct = summary.get("totalProfitPct")
    profit_factor = summary.get("profitFactor")
    max_drawdown = summary.get("maxDrawdown")
    avg_profit = summary.get("avgProfit")

    won = [t for t in trades if t.get("profit") is not None and t["profit"] > 0]
    lost = [t for t in trades if t.get("profit") is not None and t["profit"] <= 0]
    avg_win: float | None = statistics.mean([t["profit"] for t in won]) if won else None
    avg_loss: float | None = statistics.mean([t["profit"] for t in lost]) if lost else None

    # Strengths
    if win_rate is not None and win_rate >= 60:
        strengths.append({
            "title": "High Win Rate",
            "evidence": f"Win rate is {win_rate}% ({len(won)} wins out of {len(trades)} trades).",
            "confidence": "high" if not low_data else "low",
        })

    if total_profit_pct is not None and total_profit_pct > 10:
        strengths.append({
            "title": "Positive Total Return",
            "evidence": f"Strategy returned {total_profit_pct:+.2f}% over the test period.",
            "confidence": "high" if not low_data else "low",
        })

    if profit_factor is not None and profit_factor >= 1.5:
        strengths.append({
            "title": "Strong Profit Factor",
            "evidence": f"Profit factor of {profit_factor:.2f} indicates gross profits are {profit_factor:.2f}× gross losses.",
            "confidence": "high" if not low_data else "low",
        })

    if avg_win is not None and avg_loss is not None and avg_win > 0 and avg_loss < 0 and abs(avg_win) > abs(avg_loss):
        rr = abs(avg_win / avg_loss)
        strengths.append({
            "title": "Favorable Risk/Reward Ratio",
            "evidence": f"Average win (${avg_win:.2f}) is {rr:.2f}× the average loss (${avg_loss:.2f}).",
            "confidence": confidence,
        })

    if max_drawdown is not None and total_profit_pct is not None and max_drawdown < 10 and total_profit_pct > 0:
        strengths.append({
            "title": "Controlled Drawdown",
            "evidence": f"Max drawdown of {max_drawdown:.2f}% is acceptably low given positive returns.",
            "confidence": confidence,
        })

    # Check duration patterns
    if len(won) >= 3 and len(lost) >= 3:
        dur_won = [t.get("tradeDuration", 0) or 0 for t in won]
        dur_lost = [t.get("tradeDuration", 0) or 0 for t in lost]
        avg_dur_won = statistics.mean(dur_won)
        avg_dur_lost = statistics.mean(dur_lost)
        if avg_dur_won < avg_dur_lost and avg_dur_won > 0:
            strengths.append({
                "title": "Winners Exit Faster Than Losers",
                "evidence": f"Winning trades average {avg_dur_won:.0f} min vs {avg_dur_lost:.0f} min for losers, suggesting exits may be capturing moves efficiently.",
                "confidence": confidence,
            })

    # Weaknesses
    if win_rate is not None and win_rate < 40:
        weaknesses.append({
            "title": "Low Win Rate",
            "evidence": f"Only {win_rate}% of trades are profitable ({len(won)} wins, {len(lost)} losses).",
            "impact": "Strategy relies on large wins to compensate for frequent losses. Small win-size reductions could erase profitability.",
            "confidence": "high" if not low_data else "low",
        })

    if total_profit_pct is not None and total_profit_pct < 0:
        weaknesses.append({
            "title": "Negative Total Return",
            "evidence": f"Strategy lost {abs(total_profit_pct):.2f}% of the initial stake over the test period.",
            "impact": "The strategy is unprofitable in this test window.",
            "confidence": "high" if not low_data else "low",
        })

    if profit_factor is not None and profit_factor < 1.0:
        weaknesses.append({
            "title": "Profit Factor Below 1.0",
            "evidence": f"Profit factor of {profit_factor:.2f} means gross losses exceed gross profits.",
            "impact": "The strategy destroys capital over time if continued.",
            "confidence": "high" if not low_data else "low",
        })

    if avg_win is not None and avg_loss is not None and avg_loss != 0 and abs(avg_loss) > abs(avg_win):
        rr = abs(avg_win / avg_loss)
        weaknesses.append({
            "title": "Unfavorable Risk/Reward Ratio",
            "evidence": f"Average loss (${abs(avg_loss):.2f}) is larger than average win (${avg_win:.2f}). Risk/reward ratio: {rr:.2f}.",
            "impact": f"The strategy needs a high win rate (>{int(1/(1+rr)*100)}%) to break even.",
            "confidence": confidence,
        })

    if max_drawdown is not None and max_drawdown > 25:
        weaknesses.append({
            "title": "High Maximum Drawdown",
            "evidence": f"Maximum drawdown reached {max_drawdown:.2f}% from peak equity.",
            "impact": "This level of drawdown may be psychologically or financially difficult to sustain.",
            "confidence": "high" if not low_data else "low",
        })

    if len(won) >= 3 and len(lost) >= 3:
        dur_won = [t.get("tradeDuration", 0) or 0 for t in won]
        dur_lost = [t.get("tradeDuration", 0) or 0 for t in lost]
        avg_dur_won = statistics.mean(dur_won)
        avg_dur_lost = statistics.mean(dur_lost)
        if avg_dur_lost > avg_dur_won * 1.5 and avg_dur_lost > 0:
            weaknesses.append({
                "title": "Losing Trades Held Too Long",
                "evidence": (
                    f"Losing trades average {avg_dur_lost:.0f} min vs {avg_dur_won:.0f} min for winners. "
                    "This suggests the strategy holds on to losers hoping for recovery."
                ),
                "impact": "Poor exit control ties up capital in losing positions and increases drawdown.",
                "confidence": confidence,
            })

    # Streak analysis — only use trades with actual profit data
    trades_with_p = [t for t in trades if t.get("profit") is not None]
    if len(trades_with_p) >= 5:
        profits = [t["profit"] for t in trades_with_p]
        win_flags = [1 if p > 0 else 0 for p in profits]
        streaks = _compute_streak_lengths(win_flags)
        max_loss_streak = max((s for t, s in streaks if t == "loss"), default=0)
        if max_loss_streak >= 6:
            weaknesses.append({
                "title": f"Long Losing Streak Detected",
                "evidence": f"Maximum consecutive losing trades: {max_loss_streak}.",
                "impact": "Extended losing streaks can accelerate drawdown and may indicate the strategy is vulnerable during certain market regimes.",
                "confidence": confidence,
            })

    return strengths, weaknesses


# ─────────────────────────────────────────────────────────────────────────────
# Advanced metrics (Sharpe, Sortino, Calmar, Expectancy)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_advanced_metrics(trades: list[dict], summary: dict) -> dict:
    """Compute risk-adjusted performance metrics from trade data."""
    profits = [t["profit"] for t in trades if t.get("profit") is not None]
    if len(profits) < 2:
        return {
            "sharpe_ratio": None,
            "sortino_ratio": None,
            "calmar_ratio": None,
            "expectancy": None,
            "recovery_factor": None,
            "profit_std_dev": None,
        }

    n = len(profits)
    mean_profit = statistics.mean(profits)
    std_profit = statistics.stdev(profits) if n >= 2 else 0

    # Annualised Sharpe: sqrt(252) * mean/std (per-trade approximation)
    if std_profit > 0:
        sharpe = round((mean_profit / std_profit) * sqrt(252), 4)
    else:
        sharpe = None

    # Sortino: uses only downside deviation
    losses_only = [p for p in profits if p < 0]
    if losses_only and len(losses_only) >= 2:
        downside_dev = statistics.stdev(losses_only)
        if downside_dev > 0:
            sortino = round((mean_profit / downside_dev) * sqrt(252), 4)
        else:
            sortino = None
    else:
        sortino = None

    # Calmar: total return % / max drawdown
    total_profit_pct = summary.get("totalProfitPct")
    total_profit = summary.get("totalProfit")
    max_drawdown = summary.get("maxDrawdown")
    if total_profit_pct is not None and max_drawdown is not None and max_drawdown > 0:
        calmar = round(float(total_profit_pct) / float(max_drawdown), 4)
    else:
        calmar = None

    # Expectancy: avg_win * win_rate - avg_loss * loss_rate
    won = [p for p in profits if p > 0]
    lost = [p for p in profits if p <= 0]
    if won and lost:
        avg_win = statistics.mean(won)
        avg_loss = abs(statistics.mean(lost))
        win_rate = len(won) / n
        loss_rate = len(lost) / n
        expectancy = round(avg_win * win_rate - avg_loss * loss_rate, 4)
    elif won:
        expectancy = round(statistics.mean(won), 4)
    else:
        expectancy = None

    # Recovery Factor: net profit / max drawdown in dollar terms
    # Uses total_profit (absolute $) from summary, falling back to sum of profits
    net_profit = float(total_profit) if total_profit is not None else sum(profits)
    # Compute peak-to-trough drawdown in $ from trade sequence
    running = 0.0
    peak = 0.0
    max_dd_abs = 0.0
    for p in profits:
        running += p
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd_abs:
            max_dd_abs = dd
    if max_dd_abs > 0:
        recovery_factor = round(net_profit / max_dd_abs, 4)
    else:
        recovery_factor = None

    # Profit std dev (per trade, in $)
    profit_std_dev = round(std_profit, 4) if std_profit > 0 else None

    return {
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "expectancy": expectancy,
        "recovery_factor": recovery_factor,
        "profit_std_dev": profit_std_dev,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Per-pair performance breakdown
# ─────────────────────────────────────────────────────────────────────────────

def _compute_per_pair_stats(
    trades: list[dict], low_data: bool,
    strengths: list[dict], weaknesses: list[dict]
) -> dict:
    """Aggregate trade stats by pair. Also surface best/worst pair as findings."""
    from collections import defaultdict

    pair_data: dict[str, dict] = defaultdict(lambda: {
        "trade_count": 0, "win_count": 0, "total_profit": 0.0, "profits": []
    })

    for t in trades:
        pair = t.get("pair")
        profit = t.get("profit")
        if not pair or profit is None:
            continue
        pair_data[pair]["trade_count"] += 1
        pair_data[pair]["total_profit"] += float(profit)
        pair_data[pair]["profits"].append(float(profit))
        if float(profit) > 0:
            pair_data[pair]["win_count"] += 1

    result: dict[str, dict] = {}
    for pair, d in pair_data.items():
        tc = d["trade_count"]
        wc = d["win_count"]
        tp = round(d["total_profit"], 4)
        avg_p = round(tp / tc, 4) if tc > 0 else 0.0
        wr = round(wc / tc * 100, 1) if tc > 0 else 0.0
        result[pair] = {
            "trade_count": tc,
            "win_count": wc,
            "total_profit": tp,
            "avg_profit": avg_p,
            "win_rate": wr,
        }

    MIN_PAIR_TRADES = 3
    qualified = {p: d for p, d in result.items() if d["trade_count"] >= MIN_PAIR_TRADES}
    confidence = "low" if low_data else "medium"

    new_strengths = list(strengths)
    new_weaknesses = list(weaknesses)

    if len(qualified) >= 2:
        best_pair = max(qualified, key=lambda p: qualified[p]["total_profit"])
        worst_pair = min(qualified, key=lambda p: qualified[p]["total_profit"])
        bd = qualified[best_pair]
        wd = qualified[worst_pair]

        if bd["total_profit"] > 0:
            new_strengths.append({
                "title": f"Best Pair: {best_pair}",
                "evidence": (
                    f"{best_pair} contributed ${bd['total_profit']:+.2f} across "
                    f"{bd['trade_count']} trades ({bd['win_rate']}% win rate)."
                ),
                "confidence": confidence,
            })

        if wd["total_profit"] < 0:
            new_weaknesses.append({
                "title": f"Worst Pair: {worst_pair}",
                "evidence": (
                    f"{worst_pair} produced ${wd['total_profit']:+.2f} across "
                    f"{wd['trade_count']} trades ({wd['win_rate']}% win rate)."
                ),
                "impact": f"Consider excluding {worst_pair} or reviewing signal logic for this pair.",
                "confidence": confidence,
            })

    result["_strengths"] = new_strengths  # type: ignore[assignment]
    result["_weaknesses"] = new_weaknesses  # type: ignore[assignment]
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Signal issue detection (overtrading + clustering)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_signal_issues(trades: list[dict]) -> list[dict]:
    """Detect overtrading and entry signal clustering patterns."""
    from collections import defaultdict
    from datetime import datetime, timezone

    issues: list[dict] = []
    if not trades:
        return issues

    # Group by pair
    pair_trades: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        pair = t.get("pair")
        if pair:
            pair_trades[pair].append(t)

    OVERTRADING_DAILY_THRESHOLD = 5
    WINDOW_DAYS = 7

    for pair, ptrades in pair_trades.items():
        # Parse timestamps
        dated: list[tuple[datetime, dict]] = []
        for t in ptrades:
            dt_str = t.get("openDate", "")
            if not dt_str:
                continue
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                dated.append((dt, t))
            except Exception:
                continue

        if not dated:
            continue

        dated.sort(key=lambda x: x[0])
        timestamps = [d[0] for d in dated]

        # Rolling 7-day window overtrading check
        from datetime import timedelta
        for i, (ts, _) in enumerate(dated):
            window_end = ts + timedelta(days=WINDOW_DAYS)
            count_in_window = sum(
                1 for other_ts in timestamps
                if ts <= other_ts <= window_end
            )
            daily_rate = count_in_window / WINDOW_DAYS
            if daily_rate > OVERTRADING_DAILY_THRESHOLD:
                issues.append({
                    "issue": f"Overtrading detected on {pair}",
                    "severity": "warning",
                    "evidence": (
                        f"{count_in_window} trades on {pair} within a 7-day window starting "
                        f"{ts.strftime('%Y-%m-%d')} ({daily_rate:.1f} trades/day avg). "
                        f"Threshold: >{OVERTRADING_DAILY_THRESHOLD} trades/day."
                    ),
                    "recommendation": (
                        f"Review entry conditions for {pair}. High-frequency entries may indicate "
                        "over-sensitive signals or redundant trade triggers."
                    ),
                })
                break  # Only flag once per pair

        # Signal clustering: back-to-back losses on same pair within the same calendar hour
        for i in range(len(dated) - 1):
            dt1, t1 = dated[i]
            dt2, t2 = dated[i + 1]
            p1 = t1.get("profit")
            p2 = t2.get("profit")
            if p1 is None or p2 is None:
                continue
            # Both losing AND the second trade opened within 60 minutes of the first
            time_gap_seconds = (dt2 - dt1).total_seconds()
            if p1 <= 0 and p2 <= 0 and 0 <= time_gap_seconds <= 3600:
                issues.append({
                    "issue": f"Signal clustering on {pair}",
                    "severity": "warning",
                    "evidence": (
                        f"Back-to-back losing trades on {pair} at {dt1.strftime('%Y-%m-%d %H:%M')} UTC "
                        f"and {dt2.strftime('%H:%M')} UTC ({p1:+.4f} then {p2:+.4f}). "
                        "Entry signals fired multiple times within the same hour window and both lost."
                    ),
                    "recommendation": (
                        f"Consider adding a cooldown period after a losing trade on {pair} "
                        "or reducing signal sensitivity during this period."
                    ),
                })
                break  # Only flag once per pair

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Code audit
# ─────────────────────────────────────────────────────────────────────────────

def _audit_code(source: str | None, strategy_name: str) -> list[dict]:
    issues: list[dict] = []

    if not source:
        issues.append({
            "issue": f"Strategy source file not found",
            "severity": "warning",
            "evidence": f"Could not locate {strategy_name}.py in {STRAT_DIR}/",
            "recommendation": "Ensure the strategy file is present for full code audit.",
        })
        return issues

    # Check stoploss
    has_stoploss = bool(re.search(r"stoploss\s*=\s*-?\d", source))
    if not has_stoploss:
        issues.append({
            "issue": "Missing stoploss definition",
            "severity": "critical",
            "evidence": "No `stoploss = ...` assignment detected in strategy class.",
            "recommendation": "Define `stoploss = -0.10` (or appropriate value) to limit per-trade losses.",
        })

    # Check stoploss value — if it's present but very large
    sl_match = re.search(r"stoploss\s*=\s*(-[\d.]+)", source)
    if sl_match:
        sl_val = float(sl_match.group(1))
        if sl_val < -0.30:
            issues.append({
                "issue": "Very wide stoploss",
                "severity": "warning",
                "evidence": f"Stoploss is set to {sl_val} ({abs(sl_val)*100:.0f}%), which allows large per-trade losses.",
                "recommendation": "Consider whether this stoploss level is intentional. Values below -0.15 carry high per-trade risk.",
            })

    # Check minimal_roi
    has_roi = bool(re.search(r"minimal_roi\s*=", source))
    if not has_roi:
        issues.append({
            "issue": "Missing minimal_roi definition",
            "severity": "warning",
            "evidence": "No `minimal_roi = ...` detected. Strategy relies solely on signal exits.",
            "recommendation": "Define `minimal_roi` to automatically take profit at target return levels.",
        })

    # Check trailing stop
    ts_match = re.search(r"trailing_stop\s*=\s*(True|False|true|false)", source)
    if ts_match:
        if ts_match.group(1).lower() == "false":
            issues.append({
                "issue": "Trailing stop is explicitly disabled",
                "severity": "info",
                "evidence": "`trailing_stop = False` found in strategy.",
                "recommendation": "Consider enabling trailing stop to protect gains on winning trades.",
            })

    # Check for conflicting signals using AST analysis
    conflicts = _detect_conflicting_signals(source)
    for conflict in conflicts:
        issues.append({
            "issue": "Conflicting entry/exit signals in same condition",
            "severity": "warning",
            "evidence": conflict,
            "recommendation": (
                "A condition block sets both entry and exit signals simultaneously. "
                "Verify this is intentional — conflicting signals may cause unexpected trade behavior."
            ),
        })

    # Detect unused parameters — parameters defined in class body but not referenced in populate_* methods
    unused = _detect_unused_params(source)
    for param in unused:
        issues.append({
            "issue": f"Potentially unused parameter: `{param}`",
            "severity": "info",
            "evidence": f"Parameter `{param}` is assigned in the class body but not referenced in populate_indicators, populate_entry_trend, or populate_exit_trend.",
            "recommendation": "Remove unused parameters or verify they are used via inheritance/configuration.",
        })

    return issues


def _detect_unused_params(source: str) -> list[str]:
    """Find class-level numeric assignments not referenced in strategy methods."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    class_body_assignments: set[str] = set()
    method_names = {"populate_indicators", "populate_entry_trend", "populate_exit_trend",
                    "populate_buy_trend", "populate_sell_trend", "custom_stoploss"}
    method_bodies: list[str] = []

    skip_keys = {"stoploss", "minimal_roi", "trailing_stop", "trailing_stop_positive",
                 "trailing_stop_positive_offset", "trailing_only_offset_is_reached",
                 "process_only_new_candles", "use_exit_signal", "exit_profit_only",
                 "ignore_roi_if_entry_signal", "timeframe", "startup_candle_count"}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id not in skip_keys:
                            if isinstance(item.value, (ast.Constant, ast.UnaryOp, ast.Dict)):
                                class_body_assignments.add(target.id)
                elif isinstance(item, ast.FunctionDef) and item.name in method_names:
                    method_bodies.append(ast.unparse(item))

    combined = "\n".join(method_bodies)
    unused = []
    for name in sorted(class_body_assignments):
        if name not in combined and not name.startswith("_"):
            unused.append(name)

    return unused[:5]  # cap at 5 to avoid noise


def _detect_conflicting_signals(source: str) -> list[str]:
    """
    Use AST to detect if a single If-block assigns both enter and exit signals
    (e.g., dataframe.loc[...,'enter_long'] = 1 and dataframe.loc[...,'exit_long'] = 1
    in the same if-body), which would be contradictory.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    ENTRY_PATTERNS = {"enter_long", "enter_short", "buy"}
    EXIT_PATTERNS = {"exit_long", "exit_short", "sell"}

    conflicts: list[str] = []

    def _extract_signal_names(stmts: list) -> tuple[set[str], set[str]]:
        """Return (entry_signals, exit_signals) assigned in a statement list."""
        entries: set[str] = set()
        exits: set[str] = set()
        for stmt in stmts:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Subscript):
                    # dataframe.loc[cond, 'enter_long'] = 1
                    try:
                        key_node = node.slice
                        if isinstance(key_node, ast.Tuple) and len(key_node.elts) >= 2:
                            col_node = key_node.elts[1]
                            if isinstance(col_node, ast.Constant) and isinstance(col_node.value, str):
                                col = col_node.value.lower()
                                if any(p in col for p in ENTRY_PATTERNS):
                                    entries.add(col)
                                elif any(p in col for p in EXIT_PATTERNS):
                                    exits.add(col)
                    except Exception:
                        pass
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            name = target.id.lower()
                            if any(p in name for p in ENTRY_PATTERNS):
                                entries.add(name)
                            elif any(p in name for p in EXIT_PATTERNS):
                                exits.add(name)
        return entries, exits

    def _check_body(stmts: list, depth: int = 0) -> None:
        if depth > 5:
            return
        for stmt in stmts:
            if isinstance(stmt, ast.If):
                entries, exits = _extract_signal_names(stmt.body)
                if entries and exits:
                    line = getattr(stmt, "lineno", "?")
                    conflicts.append(
                        f"Line {line}: same if-block assigns entry signal(s) {sorted(entries)} "
                        f"and exit signal(s) {sorted(exits)} simultaneously."
                    )
                _check_body(stmt.body, depth + 1)
                _check_body(stmt.orelse, depth + 1)
            elif isinstance(stmt, (ast.For, ast.While, ast.With, ast.FunctionDef)):
                _check_body(getattr(stmt, "body", []), depth + 1)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
            "populate_entry_trend", "populate_exit_trend",
            "populate_buy_trend", "populate_sell_trend",
        ):
            _check_body(node.body)

    return conflicts[:3]  # cap to avoid excessive noise


# ─────────────────────────────────────────────────────────────────────────────
# Parameter recommendations
# ─────────────────────────────────────────────────────────────────────────────

def _compute_param_recommendations(
    trades: list[dict], summary: dict, source: str | None, low_data: bool
) -> list[dict]:
    recs: list[dict] = []
    confidence = "low" if low_data else "medium"

    if not trades:
        return recs

    won = [t for t in trades if t.get("profit") is not None and t["profit"] > 0]
    lost = [t for t in trades if t.get("profit") is not None and t["profit"] <= 0]
    avg_win: float | None = statistics.mean([t["profit"] for t in won]) if won else None
    avg_loss: float | None = statistics.mean([t["profit"] for t in lost]) if lost else None
    win_rate = summary.get("winRate")
    max_drawdown = summary.get("maxDrawdown")

    if source:
        sl_match = re.search(r"stoploss\s*=\s*(-[\d.]+)", source)
        if sl_match and lost:
            sl_val = float(sl_match.group(1))
            loss_pcts = [t.get("profitPct") for t in lost if t.get("profitPct") is not None]
            if not loss_pcts:
                loss_pcts = []
            if loss_pcts:
                median_loss_pct = statistics.median(loss_pcts)
            else:
                median_loss_pct = None
            if median_loss_pct is not None and sl_val < -0.15 and median_loss_pct > -5:
                suggested = round(median_loss_pct * 1.5 / 100, 2)
                trades_cut = sum(1 for p in loss_pcts if p < (suggested * 100))
                recs.append({
                    "parameter": "stoploss",
                    "current_value": sl_val,
                    "suggestion": max(suggested, -0.15),
                    "reason": (
                        f"Your median loss is {median_loss_pct:.1f}%, but stoploss is at {sl_val*100:.0f}%. "
                        f"Tightening to {max(suggested, -0.15)*100:.0f}% would have cut "
                        f"{trades_cut} of your {len(lost)} losing trades earlier."
                    ),
                    "evidence": (
                        f"Median losing trade = {median_loss_pct:.1f}% across {len(lost)} losing trades; "
                        f"configured stoploss = {sl_val*100:.0f}%."
                    ),
                    "confidence": confidence,
                    "trades_affected": trades_cut,
                    "total_losing_trades": len(lost),
                    "median_loss_pct": round(median_loss_pct, 2),
                })

    if len(won) >= 3 and len(lost) >= 3:
        dur_won = [t.get("tradeDuration", 0) or 0 for t in won]
        dur_lost = [t.get("tradeDuration", 0) or 0 for t in lost]
        avg_dur_won = statistics.mean(dur_won)
        avg_dur_lost = statistics.mean(dur_lost)

        if avg_dur_lost > avg_dur_won * 2.0 and avg_dur_won > 0:
            cutoff = avg_dur_won * 1.5
            trades_would_exit = sum(1 for d in dur_lost if d > cutoff)
            recs.append({
                "parameter": "Trade exit timing / minimal_roi",
                "current_value": "Not specified or no time-based exit",
                "suggestion": f"Add ROI target that triggers after ~{int(cutoff)} minutes",
                "reason": (
                    f"Losing trades last {avg_dur_lost:.0f} min on average vs {avg_dur_won:.0f} min for winners. "
                    f"{trades_would_exit} of {len(lost)} losing trades exceeded the {int(cutoff)}-min cutoff "
                    f"and would have been exited earlier."
                ),
                "evidence": (
                    f"Average winner duration = {avg_dur_won:.0f} min; "
                    f"average loser duration = {avg_dur_lost:.0f} min."
                ),
                "confidence": confidence,
                "trades_affected": trades_would_exit,
                "total_losing_trades": len(lost),
                "avg_winner_duration": round(avg_dur_won, 1),
                "avg_loser_duration": round(avg_dur_lost, 1),
            })

    if (
        win_rate is not None and win_rate < 45
        and avg_win is not None and avg_loss is not None
        and avg_loss != 0 and abs(avg_loss) > abs(avg_win)
    ):
        recs.append({
            "parameter": "Entry signal threshold",
            "current_value": "Current entry conditions",
            "suggestion": "Tighten entry conditions to improve trade selectivity",
            "reason": (
                f"Win rate is {win_rate:.1f}% with {len(won)} wins and {len(lost)} losses. "
                f"Average loss (${abs(avg_loss):.2f}) exceeds average win (${avg_win:.2f}) by "
                f"${abs(avg_loss) - avg_win:.2f}. Stricter entry filters could improve selectivity."
            ),
            "evidence": (
                f"Win rate = {win_rate:.1f}% with average win ${avg_win:.2f} "
                f"vs average loss ${abs(avg_loss):.2f}."
            ),
            "confidence": "low",
            "trades_affected": len(lost),
            "total_trades": len(trades),
            "win_count": len(won),
            "loss_count": len(lost),
        })

    if max_drawdown is not None and max_drawdown > 25 and source:
        has_ts = bool(re.search(r"trailing_stop\s*=\s*True", source))
        if not has_ts:
            recs.append({
                "parameter": "trailing_stop",
                "current_value": False,
                "suggestion": True,
                "reason": (
                    f"Max drawdown reached {max_drawdown:.1f}% across {len(trades)} trades. "
                    f"Enabling trailing stop could lock in profits on your {len(won)} winning trades "
                    f"and reduce peak-to-trough drawdown."
                ),
                "evidence": (
                    f"Max drawdown = {max_drawdown:.1f}% across {len(trades)} trades; "
                    f"trailing stop is disabled in strategy source."
                ),
                "confidence": confidence,
                "max_drawdown_pct": round(max_drawdown, 2),
                "total_trades": len(trades),
                "winning_trades": len(won),
            })

    return recs


# ─────────────────────────────────────────────────────────────────────────────
# Analysis panels
# ─────────────────────────────────────────────────────────────────────────────

def _compute_analysis(trades: list[dict], summary: dict, has_mae_mfe: bool, low_data: bool) -> dict:
    confidence_note = " (low confidence — few trades)" if low_data else ""

    # Risk/Reward — only trades with actual profit data
    won = [t for t in trades if t.get("profit") is not None and t["profit"] > 0]
    lost = [t for t in trades if t.get("profit") is not None and t["profit"] <= 0]
    avg_win = statistics.mean([t["profit"] for t in won]) if won else None
    avg_loss = statistics.mean([t["profit"] for t in lost]) if lost else None

    if avg_win is not None and avg_loss is not None and avg_loss != 0:
        rr_ratio = abs(avg_win / avg_loss)
        rr_flag = None
        if avg_loss < 0 and abs(avg_loss) > avg_win:
            rr_flag = f"Losses (${abs(avg_loss):.2f}) exceed wins (${avg_win:.2f}); ratio {rr_ratio:.2f}. Strategy needs >{int(1/(1+rr_ratio)*100)}% win rate to break even."
        risk_reward = {
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "ratio": round(rr_ratio, 4),
            "flag": rr_flag,
            "note": f"Based on {len(won)} wins and {len(lost)} losses{confidence_note}.",
        }
    else:
        risk_reward = {"avg_win": None, "avg_loss": None, "ratio": None, "flag": None, "note": INSUFFICIENT}

    # Trade behavior (duration analysis)
    if len(won) >= 2 and len(lost) >= 2:
        dur_won = [t.get("tradeDuration", 0) or 0 for t in won]
        dur_lost = [t.get("tradeDuration", 0) or 0 for t in lost]
        avg_dur_won = statistics.mean(dur_won)
        avg_dur_lost = statistics.mean(dur_lost)
        poor_exit = avg_dur_lost > avg_dur_won * 1.5
        trade_behavior = {
            "avg_duration_winners_min": round(avg_dur_won, 1),
            "avg_duration_losers_min": round(avg_dur_lost, 1),
            "poor_exit_control": poor_exit,
            "note": (
                f"Winners held avg {avg_dur_won:.0f} min, losers {avg_dur_lost:.0f} min"
                + (". Losers are held significantly longer — suggests poor exit control." if poor_exit else ".")
                + confidence_note
            ),
        }
    else:
        trade_behavior = {
            "avg_duration_winners_min": None,
            "avg_duration_losers_min": None,
            "poor_exit_control": None,
            "note": INSUFFICIENT,
        }

    # Time patterns (hour-of-day, day-of-week)
    time_patterns = _analyze_time_patterns(trades, low_data)

    # MAE/MFE assessment — only include trades that have actual MAE/MFE data (not None)
    mae_vals_analysis = [t["maePct"] for t in trades if t.get("maePct") is not None] if has_mae_mfe else []
    mfe_vals_analysis = [t["mfePct"] for t in trades if t.get("mfePct") is not None] if has_mae_mfe else []
    can_compute_mae_mfe = has_mae_mfe and len(mae_vals_analysis) >= 3 and len(mfe_vals_analysis) >= 3

    if can_compute_mae_mfe:
        avg_mae = statistics.mean(mae_vals_analysis)
        avg_mfe = statistics.mean(mfe_vals_analysis)
        mae_mfe = {
            "avg_mae_pct": round(avg_mae, 4),
            "avg_mfe_pct": round(avg_mfe, 4),
            "ratio": round(avg_mfe / avg_mae, 4) if avg_mae > 0 else None,
            "note": (
                f"Avg MAE {avg_mae:.2f}% (max adverse excursion) vs avg MFE {avg_mfe:.2f}% (max favorable excursion). "
                + (f"MFE/MAE ratio of {avg_mfe/avg_mae:.2f} indicates good trade selection." if avg_mae > 0 and avg_mfe/avg_mae > 1.5 else "")
                + confidence_note
            ),
        }
    else:
        mae_mfe = {"avg_mae_pct": None, "avg_mfe_pct": None, "ratio": None, "note": INSUFFICIENT + " — MAE/MFE data not provided in this backtest."}

    # Stability (rolling win rate) — only use trades with actual profit data
    trades_with_profit_a = [t for t in trades if t.get("profit") is not None]
    if len(trades_with_profit_a) >= 10:
        win_flags = [1 if t["profit"] > 0 else 0 for t in trades_with_profit_a]
        rolling = _rolling_win_rate(win_flags, window=max(5, len(win_flags) // 5))
        first_half = statistics.mean(rolling[:len(rolling)//2]) if rolling else 0
        second_half = statistics.mean(rolling[len(rolling)//2:]) if rolling else 0
        degrading = second_half < first_half - 0.1
        stability = {
            "rolling_win_rate": [round(r * 100, 2) for r in rolling],
            "early_win_rate_pct": round(first_half * 100, 2),
            "late_win_rate_pct": round(second_half * 100, 2),
            "degrading": degrading,
            "note": (
                f"Early period win rate {first_half*100:.1f}% vs late period {second_half*100:.1f}%"
                + (". Strategy shows signs of degradation over time." if degrading else ". Win rate is relatively stable.")
                + confidence_note
            ),
        }
    else:
        stability = {
            "rolling_win_rate": [],
            "early_win_rate_pct": None,
            "late_win_rate_pct": None,
            "degrading": None,
            "note": INSUFFICIENT,
        }

    return {
        "risk_reward": risk_reward,
        "trade_behavior": trade_behavior,
        "time_patterns": time_patterns,
        "stability": stability,
        "mae_mfe": mae_mfe,
    }


def _analyze_time_patterns(trades: list[dict], low_data: bool) -> dict:
    """
    Time-pattern analysis with a strict significance test.

    A bucket is considered "qualified" only if it has at least MIN_BUCKET_TRADES trades.
    We only assert "best" or "worst" hour/day claims when those top/bottom buckets are
    qualified AND there is meaningful spread among qualified buckets (profit range
    across qualified buckets must exceed MIN_PROFIT_SPREAD).

    meaningful=True is set only when >= MIN_QUALIFIED_BUCKETS hour-buckets qualify
    and the profit spread is significant.
    """
    from datetime import datetime
    MIN_TOTAL_TRADES = 20       # gate before any computation
    MIN_BUCKET_TRADES = 3       # a bucket must have at least 3 trades to be "qualified"
    MIN_QUALIFIED_BUCKETS = 3   # need at least 3 qualified hour buckets for meaningful claim
    MIN_PROFIT_SPREAD = 0.0     # profit range across qualified buckets (currency units)

    if len(trades) < MIN_TOTAL_TRADES:
        return {
            "by_hour": {},
            "by_day": {},
            "meaningful": False,
            "note": (
                f"Only {len(trades)} trades available; at least {MIN_TOTAL_TRADES} required "
                "to generate time-of-day patterns."
            ),
        }

    hour_stats: dict[int, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "profit": 0.0})
    day_stats: dict[int, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "profit": 0.0})

    for t in trades:
        try:
            dt_str = t.get("openDate", "")
            if not dt_str:
                continue
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            hour = dt.hour
            day = dt.weekday()  # 0=Mon, 6=Sun
            # Only include trade if profit is actually present
            profit_raw = t.get("profit")
            if profit_raw is None:
                continue
            profit = float(profit_raw)
            is_win = profit > 0
            hour_stats[hour]["trades"] += 1
            hour_stats[hour]["wins"] += int(is_win)
            hour_stats[hour]["profit"] += profit
            day_stats[day]["trades"] += 1
            day_stats[day]["wins"] += int(is_win)
            day_stats[day]["profit"] += profit
        except Exception:
            continue

    def to_wr(s: dict) -> dict:
        n = s["trades"]
        return {
            "trades": n,
            "win_rate_pct": round(s["wins"] / n * 100, 1) if n else 0,
            "total_profit": round(s["profit"], 4),
        }

    by_hour = {h: to_wr(v) for h, v in sorted(hour_stats.items())}
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    by_day_raw = {d: to_wr(v) for d, v in sorted(day_stats.items())}
    by_day = {day_names[k]: v for k, v in by_day_raw.items()}

    # Significance: qualified hour buckets must have MIN_BUCKET_TRADES each
    qualified_hours = {h: d for h, d in by_hour.items() if d["trades"] >= MIN_BUCKET_TRADES}
    is_meaningful = len(qualified_hours) >= MIN_QUALIFIED_BUCKETS

    # Check profit spread across qualified buckets
    if is_meaningful:
        profits = [d["total_profit"] for d in qualified_hours.values()]
        profit_spread = max(profits) - min(profits)
        if profit_spread <= MIN_PROFIT_SPREAD:
            is_meaningful = False

    # Only surface best/worst hour claims when meaningful and from qualified buckets
    note_parts = [f"Patterns based on {len(trades)} trades (UTC open time)."]
    if is_meaningful and qualified_hours:
        best_hour_key = max(qualified_hours, key=lambda h: qualified_hours[h]["total_profit"])
        worst_hour_key = min(qualified_hours, key=lambda h: qualified_hours[h]["total_profit"])
        best = qualified_hours[best_hour_key]
        worst = qualified_hours[worst_hour_key]
        note_parts.append(
            f"Best hour: {best_hour_key}:00 UTC "
            f"(${best['total_profit']:.2f}, {best['trades']} trades)."
        )
        note_parts.append(
            f"Worst hour: {worst_hour_key}:00 UTC "
            f"(${worst['total_profit']:.2f}, {worst['trades']} trades)."
        )
    elif not is_meaningful:
        note_parts.append(
            f"Only {len(qualified_hours)} hour-bucket(s) had >= {MIN_BUCKET_TRADES} trades; "
            "insufficient concentration for meaningful time claims."
        )

    return {
        "by_hour": by_hour,
        "by_day": by_day,
        "meaningful": is_meaningful,
        "note": " ".join(note_parts),
    }


def _analyze_loss_patterns(trades: list[dict]) -> dict:
    """Groups losses by exit reason, hour, day, pair and identifies concentration."""
    lost = [t for t in trades if t.get("profit") is not None and t["profit"] <= 0]
    if not lost:
        return {"by_exit_reason": {}, "by_hour": {}, "by_day": {}, "dominant_pattern": "No losses to analyse", "concentration_score": 0.0}

    from datetime import datetime

    by_exit: dict[str, int] = {}
    by_hour: dict[int, int] = {}
    by_day: dict[str, int] = {}
    by_pair: dict[str, int] = {}
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for t in lost:
        reason = t.get("exitReason") or t.get("sell_reason") or "unknown"
        by_exit[reason] = by_exit.get(reason, 0) + 1

        pair = t.get("pair") or "unknown"
        by_pair[pair] = by_pair.get(pair, 0) + 1

        dt_str = t.get("openDate") or t.get("closeDate", "")
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                by_hour[dt.hour] = by_hour.get(dt.hour, 0) + 1
                by_day[day_names[dt.weekday()]] = by_day.get(day_names[dt.weekday()], 0) + 1
            except Exception:
                pass

    total = len(lost)

    dominant_pattern = "Losses are distributed evenly across exit reasons and times"
    concentration_score = 0.0

    top_exit = max(by_exit, key=by_exit.get) if by_exit else None
    if top_exit:
        top_exit_pct = by_exit[top_exit] / total
        if top_exit_pct > 0.70:
            dominant_pattern = f"{top_exit_pct:.0%} of losses exit via '{top_exit}' — concentrated exit reason"
            concentration_score = top_exit_pct

    top_pair = max(by_pair, key=by_pair.get) if by_pair else None
    if top_pair and concentration_score < 0.70:
        top_pair_pct = by_pair[top_pair] / total
        if top_pair_pct > 0.70:
            dominant_pattern = f"{top_pair_pct:.0%} of losses on pair '{top_pair}' — single-pair concentration"
            concentration_score = top_pair_pct

    return {
        "by_exit_reason": by_exit,
        "by_hour": {str(h): c for h, c in sorted(by_hour.items())},
        "by_day": {d: c for d, c in by_day.items()},
        "dominant_pattern": dominant_pattern,
        "concentration_score": round(concentration_score, 3),
    }


def _analyze_signal_frequency(
    trades: list[dict], summary: dict, run_config: dict, strategy_source: str | None
) -> dict:
    """Computes actual trades/day vs expected max signals and counts entry AND-conditions."""
    from datetime import datetime

    if not trades:
        return {
            "trades_per_day": 0,
            "expected_max_signals_per_day": 0,
            "signal_efficiency_pct": 0,
            "entry_condition_count": 0,
            "diagnosis": "No trades available",
        }

    dates = []
    for t in trades:
        dt_str = t.get("openDate") or t.get("closeDate", "")
        if dt_str:
            try:
                dates.append(datetime.fromisoformat(dt_str.replace("Z", "+00:00")))
            except Exception:
                pass

    if len(dates) < 2:
        trading_days = 1
    else:
        dates.sort()
        delta = (dates[-1] - dates[0]).total_seconds() / 86400.0
        trading_days = max(1.0, delta)

    trades_per_day = len(trades) / trading_days

    timeframe = run_config.get("timeframe", "")
    tf_to_signals: dict[str, int] = {
        "1m": 1440, "3m": 480, "5m": 288, "15m": 96, "30m": 48,
        "1h": 24, "2h": 12, "4h": 6, "8h": 3, "1d": 1,
    }
    expected = tf_to_signals.get(timeframe, 0)
    efficiency_pct = (trades_per_day / expected * 100) if expected > 0 else None

    entry_condition_count = 0
    if strategy_source:
        try:
            tree = ast.parse(strategy_source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in ("populate_entry_trend", "populate_buy_trend"):
                    for subnode in ast.walk(node):
                        if isinstance(subnode, ast.BoolOp) and isinstance(subnode.op, ast.And):
                            count = len(subnode.values)
                            if count > entry_condition_count:
                                entry_condition_count = count
        except Exception:
            pass

    if efficiency_pct is not None:
        if efficiency_pct < 5:
            diagnosis = f"Very low signal efficiency ({efficiency_pct:.1f}% of max capacity) — entry conditions are highly restrictive"
        elif efficiency_pct < 20:
            diagnosis = f"Low signal efficiency ({efficiency_pct:.1f}% of max capacity) — consider relaxing one entry condition"
        else:
            diagnosis = f"Signal efficiency is {efficiency_pct:.1f}% of theoretical maximum"
    else:
        if trades_per_day < 0.5:
            diagnosis = f"Only {trades_per_day:.2f} trades/day — very infrequent signals"
        else:
            diagnosis = f"Generating {trades_per_day:.2f} trades/day"

    if entry_condition_count > 2:
        diagnosis += f". {entry_condition_count} AND-conditions detected in entry logic"

    return {
        "trades_per_day": round(trades_per_day, 3),
        "expected_max_signals_per_day": expected,
        "signal_efficiency_pct": round(efficiency_pct, 1) if efficiency_pct is not None else None,
        "entry_condition_count": entry_condition_count,
        "diagnosis": diagnosis,
    }


def _analyze_exit_quality(trades: list[dict], summary: dict | None = None) -> dict:
    """Analyses MAE/MFE to determine if exits are too early or stops too tight."""
    trades_with_mfe = [t for t in trades if t.get("mfePct") is not None]
    trades_with_mae = [t for t in trades if t.get("maePct") is not None]

    if not trades_with_mfe or not trades_with_mae:
        return {
            "avg_mfe_captured_pct": None,
            "avg_mae_at_exit": None,
            "exit_quality_score": None,
            "early_exit_flag": False,
            "late_stop_flag": False,
            "notes": "MAE/MFE data not available for exit quality analysis.",
        }

    mfe_vals = [t["mfePct"] for t in trades_with_mfe]
    mae_vals = [t["maePct"] for t in trades_with_mae]
    profit_pcts = [t.get("profitPct") or 0 for t in trades_with_mfe]

    avg_mfe = statistics.mean(mfe_vals)
    avg_mae = statistics.mean(mae_vals)
    avg_profit = statistics.mean(profit_pcts)

    mfe_captured = (avg_profit / avg_mfe * 100) if avg_mfe > 0 else None

    sl_pct = None
    stoploss = summary.get("stoploss") if summary else None
    if stoploss is not None:
        try:
            sl_pct = abs(float(stoploss)) * 100
        except Exception:
            pass

    early_exit_flag = mfe_captured is not None and mfe_captured < 60
    late_stop_flag = sl_pct is not None and avg_mae > sl_pct

    quality_score = None
    if mfe_captured is not None:
        quality_score = min(100, max(0, mfe_captured))

    notes_parts = []
    if mfe_captured is not None:
        notes_parts.append(f"Strategy captures {mfe_captured:.1f}% of available MFE on average.")
    if early_exit_flag:
        notes_parts.append(f"Exits are leaving profit on the table — avg MFE at exit was {avg_mfe:.2f}%.")
    if late_stop_flag:
        notes_parts.append(f"Stop-loss is too tight — avg MAE before recovery ({avg_mae:.2f}%) exceeds stop level ({sl_pct:.2f}%).")

    return {
        "avg_mfe_captured_pct": round(mfe_captured, 1) if mfe_captured is not None else None,
        "avg_mae_at_exit": round(avg_mae, 3),
        "exit_quality_score": round(quality_score, 1) if quality_score is not None else None,
        "early_exit_flag": early_exit_flag,
        "late_stop_flag": late_stop_flag,
        "notes": " ".join(notes_parts) if notes_parts else "Exit quality data available.",
    }


def _detect_overfitting(trades: list[dict]) -> dict:
    """Splits trades chronologically and compares performance of each half."""
    from datetime import datetime

    if len(trades) < 10:
        return {
            "first_half": {},
            "second_half": {},
            "degradation_score": 0.0,
            "overfitting_risk": "low",
            "evidence": f"Only {len(trades)} trades — need at least 10 for overfitting detection.",
        }

    dated = []
    for t in trades:
        dt_str = t.get("openDate") or t.get("closeDate", "")
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                dated.append((dt, t))
            except Exception:
                pass

    if len(dated) < 10:
        return {"first_half": {}, "second_half": {}, "degradation_score": 0.0, "overfitting_risk": "low", "evidence": "Insufficient dated trades."}

    dated.sort(key=lambda x: x[0])
    mid = len(dated) // 2
    first_half_trades = [t for _, t in dated[:mid]]
    second_half_trades = [t for _, t in dated[mid:]]

    def _half_stats(half: list[dict]) -> dict:
        profits = [t["profit"] for t in half if t.get("profit") is not None]
        if not profits:
            return {"total_profit": 0, "win_rate": 0, "profit_factor": 0}
        won = [p for p in profits if p > 0]
        lost_abs = [abs(p) for p in profits if p <= 0]
        win_rate = len(won) / len(profits) * 100
        gross_profit = sum(won)
        gross_loss = sum(lost_abs)
        pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0)
        return {
            "total_profit": round(sum(profits), 4),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(min(pf, 99.0), 2),
            "trade_count": len(half),
        }

    fh = _half_stats(first_half_trades)
    sh = _half_stats(second_half_trades)

    fh_pf = fh.get("profit_factor", 0)
    sh_pf = sh.get("profit_factor", 0)
    fh_profit = fh.get("total_profit", 0)
    sh_profit = sh.get("total_profit", 0)
    fh_wr = fh.get("win_rate", 0)
    sh_wr = sh.get("win_rate", 0)

    degradation_score = 0.0
    if fh_pf > 0 and sh_pf < fh_pf:
        degradation_score = (fh_pf - sh_pf) / fh_pf

    wr_drop = fh_wr - sh_wr

    if (fh_profit > 0 and sh_profit < 0) or degradation_score > 0.5 or wr_drop > 15:
        risk = "high"
    elif degradation_score > 0.25 or wr_drop > 8:
        risk = "medium"
    else:
        risk = "low"

    evidence_parts = [f"First half: PF={fh_pf:.2f}, WR={fh_wr:.1f}%, profit={fh_profit:+.4f}."]
    evidence_parts.append(f"Second half: PF={sh_pf:.2f}, WR={sh_wr:.1f}%, profit={sh_profit:+.4f}.")
    if risk != "low":
        evidence_parts.append(f"Performance degradation of {degradation_score:.0%} detected — strategy may not generalise beyond the training period.")

    return {
        "first_half": fh,
        "second_half": sh,
        "degradation_score": round(degradation_score, 3),
        "overfitting_risk": risk,
        "evidence": " ".join(evidence_parts),
    }


# ─────────────────────────────────────────────────────────────────────────────
# AI Narrative
# ─────────────────────────────────────────────────────────────────────────────

_AI_NARRATIVE_SYSTEM_PROMPT = """\
You are an elite quantitative trading analyst. Diagnose why this strategy produced these backtest results.

Strict rules:
- Cite specific numbers ("48.5% win rate", not "low win rate")
- Trace causality explicitly: X because Y which causes Z
- Be surgical: no boilerplate, no filler
- If data is insufficient, name exactly what additional data is needed
- Do not repeat findings from one section in another section
- Maximum 4 sentences per section
- Output valid JSON only — no markdown outside the JSON"""


def _build_narrative_user_message(
    run: dict,
    summary: dict,
    strategy_name: str,
    trades: list[dict],
    advanced_metrics: dict | None,
    root_cause_diagnosis: dict,
    loss_patterns: dict,
    signal_frequency: dict,
    exit_quality: dict,
    overfitting: dict,
    strengths: list[dict],
    weaknesses: list[dict],
) -> str:
    parts: list[str] = []

    config = run.get("config", {}) or {}
    timeframe = config.get("timeframe") or run.get("timeframe", "?")
    timerange_start = config.get("timerangeStart", "?")
    timerange_end = config.get("timerangeEnd", "?")
    n = len(trades)
    parts.append(
        f"Strategy: {strategy_name} | Timeframe: {timeframe} | "
        f"Date range: {timerange_start} to {timerange_end} | Total trades: {n}"
    )

    win_rate = summary.get("winRate")
    total_profit_pct = summary.get("totalProfitPct")
    max_drawdown = summary.get("maxDrawdown")
    profit_factor = summary.get("profitFactor")
    am = advanced_metrics or {}
    sharpe = am.get("sharpe_ratio")
    expectancy = am.get("expectancy")

    metric_lines = []
    if total_profit_pct is not None:
        metric_lines.append(f"totalProfit%={total_profit_pct:+.2f}%")
    if win_rate is not None:
        metric_lines.append(f"winRate={win_rate}%")
    if max_drawdown is not None:
        metric_lines.append(f"maxDrawdown={max_drawdown:.2f}%")
    if profit_factor is not None:
        metric_lines.append(f"profitFactor={profit_factor:.2f}")
    if sharpe is not None:
        metric_lines.append(f"Sharpe={sharpe:.2f}")
    if expectancy is not None:
        metric_lines.append(f"Expectancy={expectancy:+.4f}")
    if metric_lines:
        parts.append("Key metrics: " + ", ".join(metric_lines))

    rcd = root_cause_diagnosis
    failure_label = rcd.get("primary_failure_label", "")
    severity = rcd.get("severity", "")
    causal_chain = rcd.get("causal_chain", [])
    fix_priority = rcd.get("fix_priority", [])
    causal_summary = " → ".join(
        step.get("finding", "") for step in causal_chain[:3] if step.get("finding")
    )
    fix_str = "; ".join(fix_priority[:3]) if fix_priority else "none identified"
    parts.append(
        f"Root cause: [{failure_label}] severity={severity}. "
        f"Causal chain: {causal_summary}. Fix priority: {fix_str}."
    )

    lp_pattern = loss_patterns.get("dominant_pattern", "")
    if lp_pattern:
        parts.append(f"Loss pattern: {lp_pattern}")

    sf_diag = signal_frequency.get("diagnosis", "")
    if sf_diag:
        parts.append(f"Signal frequency: {sf_diag}")

    eq = exit_quality or {}
    eq_eff = eq.get("exit_efficiency")
    eq_notes = eq.get("notes", "")
    if eq_eff is not None or eq_notes:
        eq_parts = []
        if eq_eff is not None:
            eq_parts.append(f"exit_efficiency={eq_eff:.2f}")
        if eq_notes:
            eq_parts.append(eq_notes)
        parts.append("Exit quality: " + "; ".join(eq_parts))

    ov = overfitting or {}
    ov_risk = ov.get("overfitting_risk", "low")
    if ov_risk in ("medium", "high"):
        ov_evidence = ov.get("evidence", "")
        parts.append(f"Overfitting evidence ({ov_risk} risk): {ov_evidence}")

    top_weaknesses = weaknesses[:3]
    if top_weaknesses:
        w_lines = [f"{w['title']}: {w.get('evidence', '')}" for w in top_weaknesses]
        parts.append("Top weaknesses: " + " | ".join(w_lines))

    NARRATIVE_PROMPT_CHAR_BUDGET = 7500
    user_msg = "\n".join(parts)
    if len(user_msg) > NARRATIVE_PROMPT_CHAR_BUDGET:
        user_msg = user_msg[:NARRATIVE_PROMPT_CHAR_BUDGET] + "\n[... truncated to fit context budget]"

    user_msg += "\n\nRespond with this JSON schema only:\n"
    user_msg += json.dumps({
        "summary": "2-3 sentences with specific numbers",
        "what_is_working": "evidence-grounded strengths (cite numbers)",
        "what_is_not_working": "root-cause-level, not symptom-listing",
        "risk_assessment": "specific risk profile with numbers",
        "next_steps": "3-5 ordered actions with expected impact",
    }, indent=2)
    return user_msg


def _try_ai_narrative(
    run_id: str,
    run: dict,
    summary: dict,
    strategy_name: str,
    trades: list[dict],
    advanced_metrics: dict | None,
    root_cause_diagnosis: dict,
    loss_patterns: dict,
    signal_frequency: dict,
    exit_quality: dict,
    overfitting: dict,
    strengths: list[dict],
    weaknesses: list[dict],
    deterministic_narrative: dict,
) -> dict:
    """Attempt AI narrative generation with caching. Falls back to deterministic on any error."""
    if run_id:
        cached = _narrative_cache_get(run_id) or _narrative_cache_load_from_disk(run_id)
        if cached:
            return cached

    try:
        user_msg = _build_narrative_user_message(
            run=run,
            summary=summary,
            strategy_name=strategy_name,
            trades=trades,
            advanced_metrics=advanced_metrics,
            root_cause_diagnosis=root_cause_diagnosis,
            loss_patterns=loss_patterns,
            signal_frequency=signal_frequency,
            exit_quality=exit_quality,
            overfitting=overfitting,
            strengths=strengths,
            weaknesses=weaknesses,
        )

        messages = [
            {"role": "system", "content": _AI_NARRATIVE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        raw_text = _run_async_sync(lambda: _chat_complete_with_timeout(messages))

        parsed = _parse_ai_narrative_response(raw_text)
        if parsed:
            parsed["ai_narrative"] = True
            if run_id:
                _narrative_cache_set(run_id, parsed)
            return parsed
    except Exception as exc:
        logger.info("AI narrative unavailable (%s), using deterministic fallback", exc)

    fallback = dict(deterministic_narrative)
    fallback["ai_narrative"] = False
    return fallback


async def _chat_complete_with_timeout(messages: list[dict]) -> str:
    from ..models.openrouter_client import chat_complete as _chat_complete
    return await asyncio.wait_for(
        _chat_complete(messages, model="meta-llama/llama-3.3-70b-instruct:free"),
        timeout=8.0,
    )


def _run_async_sync(coro_factory) -> Any:
    """Run an async factory from sync code without constructing leaked coroutines."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(coro_factory())
        except BaseException as exc:  # noqa: BLE001
            error["exc"] = exc

    thread = threading.Thread(target=_runner, name="deep-analysis-async-bridge", daemon=True)
    thread.start()
    thread.join()

    if "exc" in error:
        raise error["exc"]
    return result.get("value")


def _parse_ai_narrative_response(raw: str) -> dict | None:
    """Parse the AI JSON response, returning None if parsing fails."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"```[a-z]*\n?", "", text).strip().rstrip("`").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            return None
        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return None

    required_keys = {"summary", "what_is_working", "what_is_not_working", "risk_assessment", "next_steps"}
    if not required_keys.issubset(data.keys()):
        return None
    for key in required_keys:
        if not isinstance(data[key], str) or not data[key].strip():
            return None
    return {k: data[k] for k in required_keys}


# ─────────────────────────────────────────────────────────────────────────────
# Narrative (deterministic fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_narrative(
    trades: list[dict], summary: dict, health: dict, strengths: list[dict],
    weaknesses: list[dict], analysis: dict, strategy_name: str, low_data: bool,
    advanced_metrics: dict | None = None,
    root_cause_diagnosis: dict | None = None,
    loss_patterns: dict | None = None,
    signal_frequency: dict | None = None,
    exit_quality: dict | None = None,
    overfitting: dict | None = None,
) -> dict:
    n = len(trades)
    total = health.get("total", 0)
    comps = health.get("components", {})

    win_rate = summary.get("winRate")
    total_profit_pct = summary.get("totalProfitPct")
    profit_factor = summary.get("profitFactor")
    max_drawdown = summary.get("maxDrawdown")
    total_profit = summary.get("totalProfit")
    avg_profit = summary.get("avgProfit")
    am = advanced_metrics or {}

    fallback = _compute_narrative_fallback(
        n, total, comps, win_rate, total_profit_pct, profit_factor, max_drawdown,
        total_profit, avg_profit, strengths, weaknesses, analysis, strategy_name, low_data, am
    )

    try:
        ai_result = _call_openrouter_narrative(
            strategy_name=strategy_name,
            summary=summary,
            health=health,
            strengths=strengths,
            weaknesses=weaknesses,
            analysis=analysis,
            advanced_metrics=am,
            root_cause_diagnosis=root_cause_diagnosis or {},
            loss_patterns=loss_patterns or {},
            signal_frequency=signal_frequency or {},
            exit_quality=exit_quality or {},
            overfitting=overfitting or {},
            n_trades=n,
        )
        if ai_result and all(ai_result.get(k) for k in ("summary", "what_is_working", "what_is_not_working", "risk_assessment", "next_steps")):
            return ai_result
    except Exception as exc:
        logger.warning("AI narrative failed, using fallback: %s", exc)

    return fallback


def _compute_narrative_fallback(
    n: int, total: int, comps: dict, win_rate, total_profit_pct, profit_factor,
    max_drawdown, total_profit, avg_profit, strengths: list, weaknesses: list,
    analysis: dict, strategy_name: str, low_data: bool, am: dict
) -> dict:
    low_data_note = (
        " Note: This analysis is based on fewer than 30 trades, so conclusions should be treated as preliminary indicators rather than definitive findings."
        if low_data else ""
    )
    if total_profit_pct is not None and total_profit is not None and win_rate is not None:
        perf_str = (
            f"achieving a total return of {total_profit_pct:+.2f}% (${total_profit:+.2f}) "
            f"with a win rate of {win_rate}%"
        )
    else:
        perf_str = "with performance metrics partially unavailable"

    summary_text = (
        f"The {strategy_name} strategy completed {n} trade(s) during the backtest period, "
        f"{perf_str}. "
        f"The overall health score is {total}/120, driven by: "
        f"Profitability {comps.get('profitability',0)}/20, "
        f"Risk Control {comps.get('risk_control',0)}/20, "
        f"Consistency {comps.get('consistency',0)}/20, "
        f"Trade Quality {comps.get('trade_quality',0)}/20, "
        f"Stability {comps.get('stability',0)}/20, "
        f"Edge Quality {comps.get('edge_quality',0)}/20."
        + low_data_note
    )

    if strengths:
        working_parts = [f"{s['title']}: {s['evidence']}" for s in strengths[:4]]
        what_working = "The following aspects of the strategy show positive evidence: " + " | ".join(working_parts) + "."
    else:
        what_working = "No clear strengths were identified from the available trade data."

    if weaknesses:
        not_working_parts = [f"{w['title']}: {w['evidence']} Impact: {w.get('impact', 'Unknown.')}" for w in weaknesses[:4]]
        what_not_working = "The following issues require attention: " + " | ".join(not_working_parts) + "."
    else:
        what_not_working = "No significant weaknesses were identified from the available trade data."

    rr = analysis.get("risk_reward", {})
    rr_ratio = rr.get("ratio")
    tb = analysis.get("trade_behavior", {})
    poor_exit = tb.get("poor_exit_control")
    stab = analysis.get("stability", {})
    degrading = stab.get("degrading")

    risk_parts = []
    if max_drawdown is not None:
        risk_parts.append(f"Maximum drawdown was {max_drawdown:.2f}%, which is {'high' if max_drawdown > 25 else 'moderate' if max_drawdown > 15 else 'acceptable'}.")
    else:
        risk_parts.append("Maximum drawdown data was not available in the backtest result.")
    if rr_ratio is not None:
        risk_parts.append(f"The risk/reward ratio is {rr_ratio:.2f}, meaning average wins are {rr_ratio:.2f}× average losses.")
    if poor_exit:
        risk_parts.append("Losing trades are held significantly longer than winners, suggesting exit control could be improved.")
    if degrading:
        risk_parts.append("Rolling win rate analysis suggests the strategy may be degrading in the second half of the test period.")
    risk_assessment = " ".join(risk_parts)

    sharpe = am.get("sharpe_ratio")
    expectancy = am.get("expectancy")
    calmar = am.get("calmar_ratio")

    next_steps_parts = []
    if n < LOW_TRADE_THRESHOLD:
        next_steps_parts.append(f"Extend the backtest period to generate more than {LOW_TRADE_THRESHOLD} trades for statistically reliable results.")
    if sharpe is not None and sharpe < 1.0:
        next_steps_parts.append(f"Sharpe ratio of {sharpe:.2f} is below the 1.0 target — consider improving entry selectivity or reducing losing trades.")
    if expectancy is not None and expectancy <= 0:
        next_steps_parts.append(f"Expectancy of {expectancy:+.4f} is negative — focus on improving win/loss ratio or increasing average winner size.")
    elif expectancy is not None and 0 < expectancy < 0.5:
        next_steps_parts.append(f"Expectancy of {expectancy:+.4f} is positive but low — increase average win size or reduce average loss size.")
    if profit_factor is not None and profit_factor < 1.2 and profit_factor > 0:
        next_steps_parts.append("Review entry signal logic — a profit factor below 1.2 suggests limited edge.")
    if weaknesses:
        top_w = weaknesses[0]
        next_steps_parts.append(f"Address the top weakness: {top_w['title']}. {top_w.get('impact', '')}")
    if max_drawdown is not None and max_drawdown > 20:
        next_steps_parts.append("Implement or tighten stoploss and/or trailing stop to reduce drawdown.")
    if calmar is not None and calmar < 0.5 and max_drawdown is not None and max_drawdown > 0:
        next_steps_parts.append(f"Calmar ratio of {calmar:.2f} indicates drawdown is high relative to returns. Aim for Calmar above 1.0.")
    if degrading:
        next_steps_parts.append("Investigate whether the strategy is overfitted to the early part of the test period.")
    if not next_steps_parts:
        next_steps_parts.append("Continue monitoring strategy performance and re-test over different time periods and market conditions.")

    return {
        "summary": summary_text,
        "what_is_working": what_working,
        "what_is_not_working": what_not_working,
        "risk_assessment": risk_assessment,
        "next_steps": " ".join(f"{i+1}. {s}" for i, s in enumerate(next_steps_parts)),
    }


def _call_openrouter_narrative(
    strategy_name: str, summary: dict, health: dict, strengths: list, weaknesses: list,
    analysis: dict, advanced_metrics: dict, root_cause_diagnosis: dict,
    loss_patterns: dict, signal_frequency: dict, exit_quality: dict,
    overfitting: dict, n_trades: int,
) -> dict | None:
    from ..models.openrouter_client import has_api_keys

    if not has_api_keys():
        return None

    system_prompt = """You are an elite quantitative trading analyst. Your job is to diagnose exactly why a trading strategy produced these backtest results — not just name the symptoms, but trace the causal chain from symptoms to root cause in the strategy's logic, parameters, and market fit.

Rules you must follow:
- Always cite specific numbers from the data (e.g., "48.5% win rate" not "low win rate")
- Trace causality explicitly: "X because Y which causes Z"
- Be surgical and direct — no boilerplate, no filler sentences
- If the data is insufficient to draw a conclusion, say exactly what additional data would reveal it
- Never repeat what has already been stated
- Maximum 4 sentences per section"""

    rcd = root_cause_diagnosis
    comps = health.get("components", {})

    lines = [
        f"Strategy: {strategy_name} | Trades: {n_trades}",
        "",
        f"PRIMARY FAILURE MODE: {rcd.get('primary_failure_label', 'Unknown')} (Severity: {rcd.get('severity', 'unknown')})",
        f"Root cause conclusion: {rcd.get('root_cause_conclusion', '')}",
        "Causal chain: " + " → ".join(
            f"[{s.get('finding','')}] ({s.get('implication','')})"
            for s in rcd.get("causal_chain", [])
        ),
        f"Fix priority: {'; '.join(rcd.get('fix_priority', [])[:3])}",
        "",
        "HEALTH COMPONENTS (each /20):",
        f"  Profitability={comps.get('profitability',0)}, RiskControl={comps.get('risk_control',0)}, Consistency={comps.get('consistency',0)}, TradeQuality={comps.get('trade_quality',0)}, Stability={comps.get('stability',0)}, EdgeQuality={comps.get('edge_quality',0)}",
        "",
        "KEY METRICS:",
    ]

    sm = summary
    wr = sm.get("winRate")
    pct = sm.get("totalProfitPct")
    pf = sm.get("profitFactor")
    dd = sm.get("maxDrawdown")
    am = advanced_metrics

    if wr is not None: lines.append(f"  WinRate={wr}%")
    if pct is not None: lines.append(f"  TotalReturn={pct:+.2f}%")
    if pf is not None: lines.append(f"  ProfitFactor={pf:.2f}")
    if dd is not None: lines.append(f"  MaxDrawdown={dd:.2f}%")
    if am.get("sharpe_ratio") is not None: lines.append(f"  Sharpe={am['sharpe_ratio']:.2f}")
    if am.get("sortino_ratio") is not None: lines.append(f"  Sortino={am['sortino_ratio']:.2f}")
    if am.get("calmar_ratio") is not None: lines.append(f"  Calmar={am['calmar_ratio']:.2f}")
    if am.get("expectancy") is not None: lines.append(f"  Expectancy={am['expectancy']:+.4f}")

    lines += [
        "",
        f"LOSS PATTERNS: {loss_patterns.get('dominant_pattern', 'N/A')} (concentration={loss_patterns.get('concentration_score', 0):.0%})",
        f"SIGNAL FREQUENCY: {signal_frequency.get('diagnosis', 'N/A')}",
    ]

    if exit_quality.get("avg_mfe_captured_pct") is not None:
        lines.append(f"EXIT QUALITY: captures {exit_quality['avg_mfe_captured_pct']}% of available MFE. EarlyExit={exit_quality.get('early_exit_flag')}, LateStop={exit_quality.get('late_stop_flag')}")

    of = overfitting
    if of.get("overfitting_risk") in ("medium", "high"):
        lines.append(f"OVERFITTING: {of.get('overfitting_risk','').upper()} risk. {of.get('evidence','')}")

    if weaknesses:
        lines.append(f"TOP WEAKNESSES: {'; '.join(w['title'] for w in weaknesses[:3])}")
    if strengths:
        lines.append(f"TOP STRENGTHS: {'; '.join(s['title'] for s in strengths[:3])}")

    user_message = "\n".join(lines)

    if len(user_message) > 3000:
        user_message = user_message[:3000]

    response_schema = '{"summary":"2-3 sentences citing specific numbers","what_is_working":"Evidence-grounded strengths","what_is_not_working":"Root-cause-level diagnosis not just symptom listing","risk_assessment":"Specific risk profile with numbers","next_steps":"3-5 ordered actions with expected quantitative impact"}'

    user_message += f"\n\nRespond ONLY with a valid JSON object matching this schema (no markdown, no extra keys):\n{response_schema}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    try:
        from ..models.openrouter_client import chat_complete as _or_chat_complete

        async def _call_async() -> str:
            return await _or_chat_complete(messages, model="meta-llama/llama-3.3-70b-instruct:free")

        content = _run_async_sync(_call_async)

        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        parsed = json.loads(content)
        required = ("summary", "what_is_working", "what_is_not_working", "risk_assessment", "next_steps")
        if all(k in parsed and isinstance(parsed[k], str) for k in required):
            return {k: parsed[k] for k in required}
    except Exception as exc:
        logger.debug("OpenRouter narrative call failed: %s", exc)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Chart data helpers (exposed for frontend)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_monthly_pnl(trades: list[dict]) -> list[dict]:
    """Aggregate profit by calendar month. Returns list of {month, profit, trade_count}."""
    from collections import defaultdict
    from datetime import datetime

    monthly: dict[str, dict] = defaultdict(lambda: {"profit": 0.0, "trade_count": 0})

    for t in trades:
        dt_str = t.get("closeDate") or t.get("openDate", "")
        profit = t.get("profit")
        if not dt_str or profit is None:
            continue
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            key = dt.strftime("%Y-%m")
            monthly[key]["profit"] += float(profit)
            monthly[key]["trade_count"] += 1
        except Exception:
            continue

    return [
        {"month": k, "profit": round(v["profit"], 4), "trade_count": v["trade_count"]}
        for k, v in sorted(monthly.items())
    ]


def compute_chart_data(trades: list[dict]) -> dict:
    """Pre-compute chart data for the frontend visualizations."""
    if not trades:
        return {
            "streak_chart": [],
            "duration_scatter": [],
            "rr_histogram": [],
            "rolling_win_rate_chart": [],
            "monthly_pnl": [],
        }

    # Win/Loss streak chart — skip trades with no profit data
    streak_chart = []
    current_streak = 0
    current_type = None
    trade_idx = 0
    for t in trades:
        if t.get("profit") is None:
            continue
        trade_idx += 1
        is_win = t["profit"] > 0
        t_type = "win" if is_win else "loss"
        if t_type == current_type:
            current_streak += 1
        else:
            current_type = t_type
            current_streak = 1
        streak_chart.append({
            "trade": trade_idx,
            "streak": current_streak if is_win else -current_streak,
            "type": t_type,
            "date": t.get("closeDate", ""),
        })

    # Profit vs Duration scatter — only include trades with both profit and duration data
    duration_scatter = []
    for t in trades:
        dur = t.get("tradeDuration")
        profit_pct = t.get("profitPct")
        is_win_raw = t.get("profit")
        if dur is None or profit_pct is None or is_win_raw is None:
            continue
        if dur > 0:
            duration_scatter.append({
                "duration_min": dur,
                "profit_pct": round(float(profit_pct), 4),
                "pair": t.get("pair", ""),
                "is_win": float(is_win_raw) > 0,
            })

    # Risk/Reward histogram (profit_pct bins) — skip trades with no profitPct data
    rr_histogram: dict[str, int] = defaultdict(int)
    for t in trades:
        pct = t.get("profitPct")
        if pct is None:
            continue
        bucket = int(float(pct) // 1) * 1  # 1% buckets
        rr_histogram[str(bucket)] = rr_histogram[str(bucket)] + 1

    rr_hist_list = sorted(
        [{"bucket_pct": int(k), "count": v} for k, v in rr_histogram.items()],
        key=lambda x: x["bucket_pct"]
    )

    # Rolling win rate — only use trades with actual profit data
    win_flags = [1 if t["profit"] > 0 else 0 for t in trades if t.get("profit") is not None]
    rolling = _rolling_win_rate(win_flags, window=min(10, max(3, len(win_flags) // 5)))
    rolling_wr_chart = [
        {"trade": i + 1, "win_rate_pct": round(r * 100, 2)}
        for i, r in enumerate(rolling)
    ]

    monthly_pnl = _compute_monthly_pnl(trades)

    # Drawdown curve — running drawdown from equity peak
    drawdown_curve = []
    running_eq = 0.0
    peak_eq = 0.0
    trade_idx_dd = 0
    for t in trades:
        profit = t.get("profit")
        if profit is None:
            continue
        trade_idx_dd += 1
        running_eq += float(profit)
        if running_eq > peak_eq:
            peak_eq = running_eq
        dd = 0.0 if peak_eq == 0 else -((peak_eq - running_eq) / abs(peak_eq)) * 100
        drawdown_curve.append({
            "trade": trade_idx_dd,
            "drawdown_pct": round(dd, 4),
            "date": t.get("closeDate", ""),
        })

    return {
        "streak_chart": streak_chart,
        "duration_scatter": duration_scatter,
        "rr_histogram": rr_hist_list,
        "rolling_win_rate_chart": rolling_wr_chart,
        "monthly_pnl": monthly_pnl,
        "drawdown_curve": drawdown_curve,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Best / Worst trades
# ─────────────────────────────────────────────────────────────────────────────

def _compute_best_worst_trades(trades: list[dict], n: int = 5) -> dict:
    """Return the top-n and bottom-n trades by profit%."""
    valid = [
        t for t in trades
        if t.get("profitPct") is not None and t.get("profit") is not None
    ]
    if not valid:
        return {"best": [], "worst": []}

    sorted_by_pct = sorted(valid, key=lambda t: float(t["profitPct"]))
    worst = sorted_by_pct[:n]
    best = sorted_by_pct[-n:][::-1]

    def _shape(t: dict) -> dict:
        return {
            "pair": t.get("pair", ""),
            "profit": round(float(t["profit"]), 4),
            "profitPct": round(float(t["profitPct"]), 4),
            "openDate": t.get("openDate", ""),
            "closeDate": t.get("closeDate", ""),
            "exitReason": t.get("exitReason", ""),
            "tradeDuration": t.get("tradeDuration"),
        }

    return {"best": [_shape(t) for t in best], "worst": [_shape(t) for t in worst]}


# ─────────────────────────────────────────────────────────────────────────────
# Concentration risk
# ─────────────────────────────────────────────────────────────────────────────

def _compute_concentration_risk(trades: list[dict], per_pair: dict) -> dict:
    """Identify if profit is heavily concentrated in a single pair."""
    if not per_pair or not trades:
        return {"concentrated": False, "note": "Insufficient data."}

    total_profit = sum(d.get("total_profit", 0) for d in per_pair.values())
    if total_profit == 0:
        return {"concentrated": False, "note": "No net profit to analyse."}

    ranked = sorted(per_pair.items(), key=lambda x: abs(x[1].get("total_profit", 0)), reverse=True)
    top_pair, top_stats = ranked[0]
    top_profit = top_stats.get("total_profit", 0)
    share_pct = round(abs(top_profit) / abs(total_profit) * 100, 1) if total_profit != 0 else 0

    concentrated = share_pct >= 50
    direction = "profit" if top_profit > 0 else "loss"

    note = (
        f"{top_pair} accounts for {share_pct}% of total {direction}. "
        + ("This is high concentration — removing this pair could significantly change results." if concentrated else "Profit is reasonably distributed across pairs.")
    )

    return {
        "concentrated": concentrated,
        "top_pair": top_pair,
        "top_pair_profit": round(float(top_profit), 4),
        "top_pair_share_pct": share_pct,
        "note": note,
        "pair_count": len(per_pair),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _rolling_win_rate(win_flags: list[int], window: int) -> list[float]:
    if len(win_flags) < window:
        return [sum(win_flags) / len(win_flags)] if win_flags else []
    result = []
    for i in range(window, len(win_flags) + 1):
        chunk = win_flags[i - window:i]
        result.append(sum(chunk) / window)
    return result


def _compute_streak_lengths(win_flags: list[int]) -> list[tuple[str, int]]:
    streaks: list[tuple[str, int]] = []
    if not win_flags:
        return streaks
    current_type = "win" if win_flags[0] == 1 else "loss"
    current_len = 1
    for flag in win_flags[1:]:
        t = "win" if flag == 1 else "loss"
        if t == current_type:
            current_len += 1
        else:
            streaks.append((current_type, current_len))
            current_type = t
            current_len = 1
    streaks.append((current_type, current_len))
    return streaks


def _read_strategy_source(strategy_name: str) -> str | None:
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_\-]+", strategy_name):
        return None
    path = (STRAT_DIR / f"{strategy_name}.py").resolve()
    if not str(path).startswith(str(STRAT_DIR.resolve())):
        return None
    try:
        if path.exists():
            return path.read_text("utf-8")
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Regime Analysis (trending vs ranging)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_regime_analysis(trades: list[dict]) -> dict:
    from datetime import datetime

    if len(trades) < 10:
        return {
            "regimes": [],
            "per_regime_performance": {},
            "note": f"Only {len(trades)} trades — need at least 10 for regime analysis.",
        }

    dated_trades: list[tuple[datetime, dict]] = []
    for t in trades:
        dt_str = t.get("openDate") or t.get("closeDate", "")
        open_rate = t.get("openRate")
        close_rate = t.get("closeRate")
        min_rate = t.get("minRate")
        max_rate = t.get("maxRate")
        if not dt_str or open_rate is None or close_rate is None:
            continue
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            dated_trades.append((dt, {**t, "_open": float(open_rate), "_close": float(close_rate),
                                      "_min": float(min_rate) if min_rate is not None else float(min(open_rate, close_rate)),
                                      "_max": float(max_rate) if max_rate is not None else float(max(open_rate, close_rate))}))
        except Exception:
            continue

    if len(dated_trades) < 10:
        return {"regimes": [], "per_regime_performance": {}, "note": "Insufficient trades with price data for regime analysis."}

    dated_trades.sort(key=lambda x: x[0])

    window = max(5, len(dated_trades) // 4)
    regimes: list[dict] = []
    regime_trades: dict[str, list[dict]] = {"trending": [], "ranging": []}

    for i in range(len(dated_trades)):
        start_idx = max(0, i - window + 1)
        w_trades = [t for _, t in dated_trades[start_idx:i + 1]]
        if len(w_trades) < 3:
            continue

        closes = [t["_close"] for t in w_trades]
        n = len(closes)
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(closes)
        num = sum((j - x_mean) * (closes[j] - y_mean) for j in range(n))
        denom = sum((j - x_mean) ** 2 for j in range(n))
        slope = num / denom if denom > 0 else 0
        slope_pct = abs(slope / y_mean) * 100 if y_mean != 0 else 0

        true_ranges = []
        for t in w_trades:
            tr = t["_max"] - t["_min"]
            if tr > 0:
                true_ranges.append(tr)
        atr = statistics.mean(true_ranges) if true_ranges else 0
        atr_pct = (atr / y_mean * 100) if y_mean != 0 else 0

        if slope_pct > atr_pct * 0.3 and slope_pct > 0.05:
            regime = "trending"
        else:
            regime = "ranging"

        dt, trade = dated_trades[i]
        regime_trades[regime].append(trade)

        if not regimes or regimes[-1]["regime"] != regime:
            regimes.append({
                "regime": regime,
                "start_date": dt.strftime("%Y-%m-%d"),
                "trade_count": 1,
            })
        else:
            regimes[-1]["trade_count"] += 1

    if regimes:
        last_dt = dated_trades[-1][0]
        regimes[-1]["end_date"] = last_dt.strftime("%Y-%m-%d")
        for i in range(len(regimes) - 1):
            if i + 1 < len(regimes):
                regimes[i]["end_date"] = regimes[i + 1].get("start_date", "")

    per_regime: dict[str, dict] = {}
    for regime_type in ["trending", "ranging"]:
        rtrades = regime_trades[regime_type]
        if not rtrades:
            continue
        profits = [t.get("profit", 0) or 0 for t in rtrades]
        wins = [p for p in profits if p > 0]
        per_regime[regime_type] = {
            "trade_count": len(rtrades),
            "total_profit": round(sum(profits), 4),
            "avg_profit": round(statistics.mean(profits), 4) if profits else 0,
            "win_rate": round(len(wins) / len(profits) * 100, 1) if profits else 0,
        }

    note_parts = [f"Detected {len(regimes)} regime transitions across {len(dated_trades)} trades (price slope + ATR volatility method)."]
    for rt, stats in per_regime.items():
        note_parts.append(
            f"{rt.capitalize()}: {stats['trade_count']} trades, "
            f"${stats['total_profit']:+.2f} total, {stats['win_rate']}% win rate."
        )

    return {
        "regimes": regimes[:20],
        "per_regime_performance": per_regime,
        "note": " ".join(note_parts),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Drawdown Recovery Analysis
# ─────────────────────────────────────────────────────────────────────────────

def _compute_drawdown_recovery(trades: list[dict]) -> dict:
    if len(trades) < 5:
        return {
            "events": [],
            "avg_recovery_trades": None,
            "max_recovery_trades": None,
            "note": f"Only {len(trades)} trades — need at least 5 for drawdown recovery analysis.",
        }

    profits = []
    for t in trades:
        p = t.get("profit")
        if p is not None:
            profits.append(float(p))

    if len(profits) < 5:
        return {"events": [], "avg_recovery_trades": None, "max_recovery_trades": None, "note": "Insufficient profit data."}

    running = 0.0
    peak = 0.0
    events: list[dict] = []
    in_drawdown = False
    dd_start_idx = 0
    dd_peak = 0.0
    dd_trough = 0.0
    trough_idx = 0

    for i, p in enumerate(profits):
        running += p
        if running > peak:
            if in_drawdown:
                recovery_trades = i - dd_start_idx
                dd_depth = dd_peak - dd_trough
                trade_at_start = trades[dd_start_idx] if dd_start_idx < len(trades) else {}
                trade_at_trough = trades[trough_idx] if trough_idx < len(trades) else {}
                events.append({
                    "start_trade": dd_start_idx + 1,
                    "trough_trade": trough_idx + 1,
                    "recovery_trade": i + 1,
                    "depth_dollars": round(dd_depth, 4),
                    "recovery_trades": recovery_trades,
                    "start_date": trade_at_start.get("openDate", ""),
                    "trough_date": trade_at_trough.get("openDate", ""),
                    "recovery_date": trades[i].get("closeDate", "") if i < len(trades) else "",
                })
                in_drawdown = False
            peak = running
        elif running < peak:
            if not in_drawdown:
                in_drawdown = True
                dd_start_idx = i
                dd_peak = peak
                dd_trough = running
                trough_idx = i
            if running < dd_trough:
                dd_trough = running
                trough_idx = i

    if in_drawdown and len(profits) > dd_start_idx:
        dd_depth = dd_peak - dd_trough
        events.append({
            "start_trade": dd_start_idx + 1,
            "trough_trade": trough_idx + 1,
            "recovery_trade": None,
            "depth_dollars": round(dd_depth, 4),
            "recovery_trades": None,
            "start_date": trades[dd_start_idx].get("openDate", "") if dd_start_idx < len(trades) else "",
            "trough_date": trades[trough_idx].get("openDate", "") if trough_idx < len(trades) else "",
            "recovery_date": None,
        })

    recovered = [e for e in events if e["recovery_trades"] is not None]
    avg_recovery = round(statistics.mean([e["recovery_trades"] for e in recovered]), 1) if recovered else None
    max_recovery = max([e["recovery_trades"] for e in recovered]) if recovered else None

    note_parts = [f"Found {len(events)} drawdown event(s)."]
    if avg_recovery is not None:
        note_parts.append(f"Average recovery: {avg_recovery} trades.")
    if max_recovery is not None:
        note_parts.append(f"Longest recovery: {max_recovery} trades.")
    unrecovered = [e for e in events if e["recovery_trade"] is None]
    if unrecovered:
        note_parts.append(f"{len(unrecovered)} drawdown(s) not yet recovered.")

    return {
        "events": events[:15],
        "avg_recovery_trades": avg_recovery,
        "max_recovery_trades": max_recovery,
        "note": " ".join(note_parts),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Trade Clustering (temporal grouping of wins/losses)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_trade_clustering(trades: list[dict]) -> dict:
    from datetime import datetime, timedelta

    if len(trades) < 10:
        return {
            "clusters": [],
            "win_clusters": 0,
            "loss_clusters": 0,
            "note": f"Only {len(trades)} trades — need at least 10 for clustering analysis.",
        }

    dated: list[tuple[datetime, dict]] = []
    for t in trades:
        dt_str = t.get("openDate", "")
        profit = t.get("profit")
        if not dt_str or profit is None:
            continue
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            dated.append((dt, t))
        except Exception:
            continue

    if len(dated) < 10:
        return {"clusters": [], "win_clusters": 0, "loss_clusters": 0, "note": "Insufficient dated trades."}

    dated.sort(key=lambda x: x[0])

    GAP_HOURS = 4
    clusters: list[dict] = []
    current_cluster: list[tuple[datetime, dict]] = [dated[0]]

    for i in range(1, len(dated)):
        dt_prev = dated[i - 1][0]
        dt_curr = dated[i][0]
        gap = (dt_curr - dt_prev).total_seconds() / 3600.0

        if gap <= GAP_HOURS:
            current_cluster.append(dated[i])
        else:
            if len(current_cluster) >= 3:
                _add_cluster(clusters, current_cluster)
            current_cluster = [dated[i]]

    if len(current_cluster) >= 3:
        _add_cluster(clusters, current_cluster)

    win_clusters = sum(1 for c in clusters if c["dominant_outcome"] == "win")
    loss_clusters = sum(1 for c in clusters if c["dominant_outcome"] == "loss")

    note_parts = [f"Found {len(clusters)} trade cluster(s) (>= 3 trades within {GAP_HOURS}h gap)."]
    if win_clusters:
        note_parts.append(f"{win_clusters} predominantly winning cluster(s).")
    if loss_clusters:
        note_parts.append(f"{loss_clusters} predominantly losing cluster(s).")
    if loss_clusters > win_clusters and loss_clusters >= 2:
        note_parts.append("Losses tend to cluster together — consider adding cooldown logic after consecutive losses.")

    return {
        "clusters": clusters[:15],
        "win_clusters": win_clusters,
        "loss_clusters": loss_clusters,
        "note": " ".join(note_parts),
    }


def _add_cluster(clusters: list[dict], group: list[tuple]) -> None:
    from datetime import datetime
    profits = [t.get("profit", 0) or 0 for _, t in group]
    wins = sum(1 for p in profits if p > 0)
    losses = len(profits) - wins
    total_profit = sum(profits)
    dominant = "win" if wins > losses else "loss" if losses > wins else "mixed"

    start_dt: datetime = group[0][0]
    end_dt: datetime = group[-1][0]

    clusters.append({
        "start_date": start_dt.strftime("%Y-%m-%d %H:%M"),
        "end_date": end_dt.strftime("%Y-%m-%d %H:%M"),
        "trade_count": len(group),
        "wins": wins,
        "losses": losses,
        "total_profit": round(total_profit, 4),
        "dominant_outcome": dominant,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 Deterministic Diagnosis Engine
# ─────────────────────────────────────────────────────────────────────────────

_TIMEFRAME_PERIODS: dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
    "1d": 1440, "3d": 4320, "1w": 10080,
}


def _diagnose_root_causes(
    trades: list[dict],
    summary: dict,
    analysis: dict,
    advanced_metrics: dict,
    code_audit: list[dict],
    strategy_source: str | None,
    run_config: dict,
    overfitting: dict,
) -> dict:
    """Identify the single most impactful failure mode and its causal chain."""
    trades_with_profit = [t for t in trades if t.get("profit") is not None]
    total_trades = len(trades_with_profit)
    confidence = "low" if total_trades < 30 else ("medium" if total_trades <= 100 else "high")
    confidence_note = f"Based on {total_trades} trade(s)"
    if confidence == "low":
        confidence_note += " — conclusions are directionally useful but not statistically definitive"
    elif confidence == "medium":
        confidence_note += " — moderate statistical confidence"
    else:
        confidence_note += " — high statistical confidence"

    if total_trades == 0:
        backtest_days = summary.get("backtest_days") or summary.get("backtestDays") or 0
        trade_finding = (
            f"0 closed trades across {backtest_days} backtest day(s)"
            if backtest_days
            else "0 closed trades were recorded for this backtest"
        )
        return {
            "primary_failure_mode": "no_trades",
            "primary_failure_label": "No Trades — Strategy Never Triggered",
            "severity": "critical",
            "causal_chain": [
                {
                    "step": 1,
                    "finding": trade_finding,
                    "implication": "There is no executable trade sample to evaluate profitability, win rate, or drawdown behavior.",
                }
            ],
            "root_cause_conclusion": "No trades were generated during the backtest period.",
            "fix_priority": ["Check entry conditions", "Verify data availability for the selected pairs and timeframe"],
            "secondary_issues": [],
            "confidence": "low",
            "confidence_note": "No trades to analyze.",
        }

    won = [t for t in trades_with_profit if t["profit"] > 0]
    lost = [t for t in trades_with_profit if t["profit"] <= 0]
    avg_win_abs = statistics.mean([t["profit"] for t in won]) if won else 0.0
    avg_loss_abs = abs(statistics.mean([t["profit"] for t in lost])) if lost else 0.001

    win_rate_actual = len(won) / total_trades if total_trades > 0 else 0.0
    profit_factor = float(summary.get("profitFactor") or 0.0)
    max_drawdown_pct = float(summary.get("maxDrawdown") or 0.0)
    total_profit_pct = float(summary.get("totalProfitPct") or 0.0)

    code_audit_criticals = sum(1 for i in (code_audit or []) if i.get("severity") == "critical")
    trade_count_confidence_factor = min(1.0, total_trades / 50.0)

    candidates: list[dict] = []

    breakeven_wr = 1.0 / (1.0 + avg_win_abs / max(avg_loss_abs, 0.001))
    if win_rate_actual < 0.85 * breakeven_wr:
        severity = "critical" if win_rate_actual < 0.7 * breakeven_wr else "warning"
        magnitude = (breakeven_wr - win_rate_actual) / max(breakeven_wr, 0.001)
        severity_score = magnitude * trade_count_confidence_factor * (1 + 0.1 * code_audit_criticals)

        causal_chain = [
            {
                "step": 1,
                "finding": (
                    f"{win_rate_actual*100:.1f}% win rate; breakeven requires "
                    f"{breakeven_wr*100:.1f}%"
                ),
                "implication": "Actual win rate is below the breakeven threshold for this strategy's R:R ratio",
            }
        ]

        exit_reasons: dict[str, int] = defaultdict(int)
        for t in lost:
            reason = t.get("exitReason") or "unknown"
            exit_reasons[reason] += 1
        if exit_reasons:
            top_exit = max(exit_reasons, key=lambda k: exit_reasons[k])
            top_pct = round(exit_reasons[top_exit] / len(lost) * 100, 1)
            causal_chain.append({
                "step": 2,
                "finding": f"{top_pct}% of losses exit via {top_exit}",
                "implication": "Price immediately reverses after entry — entries may be poorly timed" if top_exit == "stop_loss" else f"Most losses close via {top_exit}",
            })

        dur_won = [t.get("tradeDuration", 0) or 0 for t in won]
        dur_lost = [t.get("tradeDuration", 0) or 0 for t in lost]
        if dur_won and dur_lost:
            avg_dur_won = statistics.mean(dur_won)
            avg_dur_lost = statistics.mean(dur_lost)
            if avg_dur_lost > avg_dur_won * 1.3:
                causal_chain.append({
                    "step": len(causal_chain) + 1,
                    "finding": f"Avg loss duration {avg_dur_lost/60:.1f}h vs avg win duration {avg_dur_won/60:.1f}h",
                    "implication": "Losers are held significantly longer — no early cut mechanism",
                })

        candidates.append({
            "primary_failure_mode": "high_loss_rate",
            "primary_failure_label": "High Loss Rate — Entries Not Well-Timed",
            "severity": severity,
            "severity_score": severity_score,
            "causal_chain": causal_chain,
            "root_cause_conclusion": (
                "Entries fire at suboptimal points; price reversal hits stop before profit target can be reached."
            ),
            "fix_priority": [
                "Add a trend-alignment filter to avoid counter-trend entries",
                "Review entry signal direction — ensure indicators confirm entry direction",
                "Consider reducing stoploss to cut losers faster",
            ],
        })

    timeframe = run_config.get("timeframe") or "1h"
    period_minutes = _TIMEFRAME_PERIODS.get(timeframe, 60)
    expected_max_per_day = 1440.0 / period_minutes
    open_dates = []
    for t in trades_with_profit:
        val = t.get("openDate")
        if val:
            try:
                from datetime import datetime as _dt
                open_dates.append(_dt.fromisoformat(val.replace("Z", "+00:00")))
            except Exception:
                pass
    trading_days = max(
        (max(open_dates) - min(open_dates)).total_seconds() / 86400.0, 1.0
    ) if len(open_dates) >= 2 else 1.0
    actual_per_day = total_trades / trading_days
    signal_efficiency = actual_per_day / expected_max_per_day if expected_max_per_day > 0 else 0.0

    if signal_efficiency < 0.05:
        severity = "critical" if signal_efficiency < 0.01 else "warning"
        magnitude = 1.0 - signal_efficiency / 0.05
        severity_score = magnitude * trade_count_confidence_factor * 0.8
        candidates.append({
            "primary_failure_mode": "low_trade_count",
            "primary_failure_label": "Low Signal Frequency — Strategy Rarely Triggers",
            "severity": severity,
            "severity_score": severity_score,
            "causal_chain": [
                {
                    "step": 1,
                    "finding": f"Signal efficiency: {signal_efficiency*100:.2f}% of maximum possible {timeframe} signals",
                    "implication": "Strategy triggers far less often than the timeframe allows — statistical conclusions have wide uncertainty",
                },
                {
                    "step": 2,
                    "finding": f"{actual_per_day:.2f} trades/day vs {expected_max_per_day:.1f} maximum possible",
                    "implication": "Entry conditions may be over-filtered or indicator combinations rarely align",
                },
            ],
            "root_cause_conclusion": (
                "Entry conditions are extremely selective — strategy generates too few signals for reliable evaluation."
            ),
            "fix_priority": [
                "Log raw indicator values to understand alignment frequency",
                "Relax the most restrictive entry condition and re-test",
                "Consider a longer backtest period to gather more trades",
            ],
        })

    if avg_win_abs / max(avg_loss_abs, 0.001) < 1.0 and profit_factor < 1.1:
        severity = "critical" if profit_factor < 1.0 else "warning"
        magnitude = (avg_loss_abs - avg_win_abs) / max(avg_loss_abs, 0.001)
        severity_score = magnitude * trade_count_confidence_factor * (1 + 0.15 * code_audit_criticals)

        exit_reasons_won: dict[str, int] = defaultdict(int)
        for t in won:
            reason = t.get("exitReason") or "unknown"
            exit_reasons_won[reason] += 1
        roi_exits = exit_reasons_won.get("roi", 0)
        roi_pct = round(roi_exits / max(len(won), 1) * 100, 1)

        causal_chain_rr = [
            {
                "step": 1,
                "finding": f"Avg win ${avg_win_abs:.2f} vs avg loss ${avg_loss_abs:.2f} — losses are larger",
                "implication": "Strategy requires a very high win rate to break even",
            },
        ]
        if roi_pct > 60:
            causal_chain_rr.append({
                "step": 2,
                "finding": f"{roi_pct:.0f}% of wins close at ROI target",
                "implication": "Profit is consistently capped at the ROI limit — consider raising ROI targets",
            })
        else:
            causal_chain_rr.append({
                "step": 2,
                "finding": "Win exits are variable (not dominated by ROI target)",
                "implication": "Exit timing is inconsistent — review exit logic for profit-taking",
            })

        candidates.append({
            "primary_failure_mode": "poor_risk_reward",
            "primary_failure_label": "Poor Risk/Reward — Losses Exceed Wins",
            "severity": severity,
            "severity_score": severity_score,
            "causal_chain": causal_chain_rr,
            "root_cause_conclusion": (
                "Average losses outpace average wins. The strategy needs an unusually high win rate to remain profitable."
            ),
            "fix_priority": [
                "Raise the ROI target to allow winners more room to run",
                "Tighten the stoploss to reduce average loss size",
                "Review exit conditions to avoid cutting winners short",
            ],
        })

    drawdown_multiple = max_drawdown_pct / max(total_profit_pct, 0.01)
    if drawdown_multiple > 5 and max_drawdown_pct > 15:
        severity = "critical" if drawdown_multiple > 10 else "warning"
        magnitude = min(drawdown_multiple / 10.0, 1.0)
        severity_score = magnitude * trade_count_confidence_factor

        profits_seq = [t["profit"] for t in trades_with_profit]
        win_flags = [1 if p > 0 else 0 for p in profits_seq]
        streaks = _compute_streak_lengths(win_flags)
        max_loss_streak = max((s for tp, s in streaks if tp == "loss"), default=0)

        causal_chain_dd: list[dict] = [
            {
                "step": 1,
                "finding": f"Max drawdown {max_drawdown_pct:.1f}% is {drawdown_multiple:.1f}× total profit",
                "implication": "Risk taken is severely disproportionate to profit earned",
            },
        ]
        if max_loss_streak >= 4:
            causal_chain_dd.append({
                "step": 2,
                "finding": f"Longest consecutive loss streak: {max_loss_streak} trades",
                "implication": "Loss clustering amplifies drawdown — strategy may be sensitive to specific market regimes",
            })

        candidates.append({
            "primary_failure_mode": "excessive_drawdown",
            "primary_failure_label": "Excessive Drawdown — Risk Disproportionate to Return",
            "severity": severity,
            "severity_score": severity_score,
            "causal_chain": causal_chain_dd,
            "root_cause_conclusion": (
                f"Max drawdown of {max_drawdown_pct:.1f}% is {drawdown_multiple:.1f}× total profit "
                "— the strategy incurs far more risk than the return justifies."
            ),
            "fix_priority": [
                "Add a daily loss limit or circuit breaker to halt trading during losing streaks",
                "Reduce position size to limit per-trade dollar loss",
                "Review stoploss width — a tighter stop may reduce drawdown depth",
            ],
        })

    if not candidates:
        if profit_factor >= 1.2:
            pf_label = "ok"
        elif profit_factor >= 1.05:
            pf_label = "warning"
        else:
            pf_label = "critical"

        return {
            "primary_failure_mode": "none" if pf_label == "ok" else "marginal_profit_factor",
            "primary_failure_label": "No Critical Failure Mode Detected" if pf_label == "ok" else "Marginal Profit Factor",
            "severity": "ok" if pf_label == "ok" else pf_label,
            "causal_chain": [],
            "root_cause_conclusion": (
                "Strategy metrics are within acceptable ranges. Focus on improving consistency and robustness."
                if pf_label == "ok"
                else f"Profit factor of {profit_factor:.2f} is below the 1.2 threshold for a comfortable edge."
            ),
            "fix_priority": [],
            "secondary_issues": [],
            "confidence": confidence,
            "confidence_note": confidence_note,
        }

    candidates.sort(key=lambda c: c["severity_score"], reverse=True)
    primary = candidates[0]

    overfitting_risk = overfitting.get("overfitting_risk", "low")
    overfitting_secondary: list[str] = []
    if overfitting_risk in ("medium", "high"):
        overfitting_secondary.append(
            f"Overfitting risk ({overfitting_risk}): {overfitting.get('evidence', 'Performance degrades in second half of trades.')}"
        )

    secondary_issues: list[str] = [
        f"{c['primary_failure_mode']}: {c['causal_chain'][0]['finding'] if c['causal_chain'] else c['root_cause_conclusion']}"
        for c in candidates[1:]
    ] + overfitting_secondary

    causal_chain_final = list(primary["causal_chain"])
    if overfitting_risk == "high":
        causal_chain_final.append({
            "step": len(causal_chain_final) + 1,
            "finding": overfitting.get("evidence", "Performance degradation detected in second half."),
            "implication": "Strategy may be overfitted to historical data — forward performance could be worse",
        })

    return {
        "primary_failure_mode": primary["primary_failure_mode"],
        "primary_failure_label": primary["primary_failure_label"],
        "severity": primary["severity"],
        "causal_chain": causal_chain_final,
        "root_cause_conclusion": primary["root_cause_conclusion"],
        "fix_priority": primary["fix_priority"],
        "secondary_issues": secondary_issues,
        "confidence": confidence,
        "confidence_note": confidence_note,
    }
