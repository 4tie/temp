from __future__ import annotations

from typing import Any

from app.services.results.summary_normalizer import (
    coerce_profit_pct,
    coerce_rate_pct,
    stringify_key,
    to_float,
    to_int,
)


def calc_win_rate(data: dict[str, Any]) -> float:
    total = data.get("total_trades", 0)
    if total == 0:
        return 0.0

    if data.get("winrate") is not None:
        try:
            winrate = float(data["winrate"])
            return round(winrate * 100 if abs(winrate) <= 1 else winrate, 2)
        except (TypeError, ValueError):
            pass

    wins = data.get("wins", 0)
    return round((wins / total) * 100, 2)


def extract_overview(data: dict[str, Any]) -> dict[str, Any]:
    best_pair = data.get("best_pair", "")
    if isinstance(best_pair, dict):
        best_pair = best_pair.get("key", best_pair)

    worst_pair = data.get("worst_pair", "")
    if isinstance(worst_pair, dict):
        worst_pair = worst_pair.get("key", worst_pair)

    return {
        "total_trades": data.get("total_trades", 0),
        "profit_total": data.get("profit_total", 0),
        "profit_total_abs": data.get("profit_total_abs", 0),
        "profit_percent": round(data.get("profit_total", 0) * 100, 4),
        "profit_factor": data.get("profit_factor", 0),
        "win_rate": calc_win_rate(data),
        "max_drawdown": data.get("max_drawdown", 0) or data.get("max_drawdown_account", 0) or 0,
        "max_drawdown_abs": data.get("max_drawdown_abs", 0) or 0,
        "max_drawdown_account": data.get("max_drawdown_account", 0) or 0,
        "avg_profit_pct": data.get("avg_profit_pct", data.get("profit_mean_pct")),
        "avg_duration": data.get("avg_duration", ""),
        "best_pair": stringify_key(best_pair),
        "worst_pair": stringify_key(worst_pair),
        "trading_volume": data.get("trading_volume", data.get("total_volume", 0)),
        "trade_count_long": data.get("trade_count_long", 0),
        "trade_count_short": data.get("trade_count_short", 0),
        "starting_balance": data.get("starting_balance", 0),
        "final_balance": data.get("final_balance", 0),
        "backtest_start": data.get("backtest_start", ""),
        "backtest_end": data.get("backtest_end", ""),
        "timeframe": data.get("timeframe", ""),
        "stake_currency": data.get("stake_currency", ""),
        "stake_amount": data.get("stake_amount", ""),
        "max_open_trades": data.get("max_open_trades", 0),
    }


def build_overview(summary: dict[str, Any]) -> dict[str, Any]:
    profit_total_abs = to_float(summary.get("totalProfit"))
    starting_balance = to_float(summary.get("startingBalance"))
    final_balance = to_float(summary.get("finalBalance"))
    if starting_balance and profit_total_abs is not None:
        profit_total_ratio = profit_total_abs / starting_balance
    else:
        profit_total_ratio = None

    profit_percent = coerce_profit_pct(
        summary.get("totalProfitPct"),
        ratio_value=profit_total_ratio,
        abs_value=profit_total_abs,
        starting_balance=starting_balance,
        final_balance=final_balance,
    )

    max_drawdown = to_float(summary.get("maxDrawdown"))
    max_drawdown_account = to_float(summary.get("maxDrawdownAccount"))

    return {
        "total_trades": to_int(summary.get("totalTrades")),
        "profit_total": profit_total_ratio,
        "profit_total_abs": profit_total_abs,
        "profit_percent": profit_percent,
        "profit_factor": to_float(summary.get("profitFactor")),
        "win_rate": coerce_rate_pct(summary.get("winRate")),
        "max_drawdown": (max_drawdown / 100.0) if max_drawdown is not None else None,
        "max_drawdown_abs": to_float(summary.get("maxDrawdownAbs")),
        "max_drawdown_account": (max_drawdown_account / 100.0) if max_drawdown_account is not None else None,
        "avg_profit_pct": to_float(summary.get("avgProfitPct")),
        "best_pair": summary.get("bestPair", ""),
        "worst_pair": summary.get("worstPair", ""),
        "trading_volume": to_float(summary.get("tradingVolume")),
        "starting_balance": starting_balance,
        "final_balance": final_balance,
        "timeframe": summary.get("timeframe", ""),
        "stake_currency": summary.get("stakeCurrency", ""),
        "stake_amount": summary.get("stakeAmount", ""),
        "max_open_trades": to_int(summary.get("maxOpenTrades")),
        "sharpe_ratio": to_float(summary.get("sharpeRatio", summary.get("sharpe_ratio"))),
    }


__all__ = ["build_overview", "calc_win_rate", "extract_overview"]
