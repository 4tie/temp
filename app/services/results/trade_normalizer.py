from __future__ import annotations

import statistics
from typing import Any

from app.services.results.summary_normalizer import (
    coalesce,
    coerce_profit_pct,
    coerce_rate_pct,
    drawdown_to_pct,
    stringify_key,
    to_float,
    to_int,
)


def normalize_trade(trade: dict[str, Any]) -> dict[str, Any]:
    profit_abs = coalesce(trade.get("profit"), trade.get("profit_abs"), trade.get("profitAbs"))
    profit_pct = coalesce(trade.get("profitPct"), trade.get("profit_pct"), trade.get("profit_percent"))
    if profit_pct is None:
        profit_pct = coerce_profit_pct(trade.get("profit_ratio"), ratio_value=trade.get("profit_ratio"))

    open_date = coalesce(trade.get("openDate"), trade.get("open_date"))
    close_date = coalesce(trade.get("closeDate"), trade.get("close_date"))
    exit_reason = coalesce(trade.get("exitReason"), trade.get("exit_reason"), trade.get("sell_reason"))
    open_rate = coalesce(trade.get("openRate"), trade.get("open_rate"))
    close_rate = coalesce(trade.get("closeRate"), trade.get("close_rate"))
    min_rate = coalesce(trade.get("minRate"), trade.get("min_rate"), trade.get("mae"))
    max_rate = coalesce(trade.get("maxRate"), trade.get("max_rate"), trade.get("mfe"))
    orders = trade.get("orders")

    normalized = dict(trade)
    normalized.update(
        {
            "pair": trade.get("pair", ""),
            "enter_tag": trade.get("enter_tag", ""),
            "direction": trade.get("direction", trade.get("trade_direction", "short" if trade.get("is_short") else "long")),
            "profit": to_float(profit_abs),
            "profit_abs": to_float(profit_abs),
            "profitPct": to_float(profit_pct),
            "profit_pct": to_float(profit_pct),
            "openDate": open_date,
            "open_date": open_date,
            "closeDate": close_date,
            "close_date": close_date,
            "openTimestamp": to_float(trade.get("openTimestamp", trade.get("open_timestamp"))),
            "closeTimestamp": to_float(trade.get("closeTimestamp", trade.get("close_timestamp"))),
            "exitReason": exit_reason,
            "exit_reason": exit_reason,
            "openRate": to_float(open_rate),
            "open_rate": to_float(open_rate),
            "closeRate": to_float(close_rate),
            "close_rate": to_float(close_rate),
            "stakeAmount": to_float(trade.get("stakeAmount", trade.get("stake_amount"))),
            "stake_amount": to_float(trade.get("stakeAmount", trade.get("stake_amount"))),
            "amount": to_float(trade.get("amount")),
            "leverage": to_float(trade.get("leverage")),
            "minRate": to_float(min_rate),
            "min_rate": to_float(min_rate),
            "maxRate": to_float(max_rate),
            "max_rate": to_float(max_rate),
            "isOpen": bool(trade.get("isOpen", trade.get("is_open"))),
            "is_open": bool(trade.get("isOpen", trade.get("is_open"))),
            "is_short": bool(trade.get("is_short", False)),
            "duration": coalesce(trade.get("duration"), trade.get("trade_duration")),
            "fee_open": to_float(trade.get("fee_open")),
            "fee_close": to_float(trade.get("fee_close")),
            "funding_fees": to_float(trade.get("funding_fees")),
            "initial_stop_loss_abs": to_float(trade.get("initial_stop_loss_abs")),
            "initial_stop_loss_ratio": to_float(trade.get("initial_stop_loss_ratio")),
            "stop_loss_abs": to_float(trade.get("stop_loss_abs")),
            "stop_loss_ratio": to_float(trade.get("stop_loss_ratio")),
            "weekday": trade.get("weekday"),
            "orders": orders if isinstance(orders, list) else [],
        }
    )
    return normalized


def derive_avg_profit_pct_from_trades(trades: list[dict[str, Any]]) -> float | None:
    values = []
    for trade in trades or []:
        value = to_float(coalesce(trade.get("profitPct"), trade.get("profit_pct"), trade.get("profit_percent")))
        if value is not None:
            values.append(value)
    if not values:
        return None
    return statistics.mean(values)


def normalize_per_pair(entry: dict[str, Any], starting_balance: float | None = None) -> dict[str, Any]:
    pair = coalesce(entry.get("pair"), entry.get("key"))
    trades = coalesce(entry.get("trades"), entry.get("total_trades"))
    profit_percent = coalesce(entry.get("profit_percent"), entry.get("profit_sum_pct"), entry.get("profit_total_pct"))
    max_drawdown = coalesce(entry.get("max_drawdown"), entry.get("max_drawdown_account"))
    winrate = coalesce(entry.get("winrate"), entry.get("win_rate"))

    normalized = dict(entry)
    normalized_profit_pct = coerce_profit_pct(
        profit_percent,
        ratio_value=entry.get("profit_total"),
        abs_value=entry.get("profit_total_abs"),
        starting_balance=starting_balance,
    )
    normalized_profit_mean_pct = coerce_profit_pct(
        entry.get("profit_mean_pct"),
        ratio_value=entry.get("profit_mean"),
        abs_value=entry.get("profit_mean_abs"),
        starting_balance=starting_balance,
    )
    normalized.update(
        {
            "pair": stringify_key(pair),
            "key": pair,
            "label": stringify_key(pair),
            "trades": to_int(trades),
            "profit_percent": normalized_profit_pct,
            "profit_sum_pct": normalized_profit_pct,
            "profit_total_pct": normalized_profit_pct,
            "profit_total": to_float(entry.get("profit_total")),
            "profit_mean": to_float(entry.get("profit_mean")),
            "profit_mean_pct": normalized_profit_mean_pct,
            "profit_total_abs": to_float(entry.get("profit_total_abs")) or 0.0,
            "profit_factor": to_float(entry.get("profit_factor")) or 0.0,
            "max_drawdown": drawdown_to_pct(max_drawdown),
            "max_drawdown_account": drawdown_to_pct(entry.get("max_drawdown_account")),
            "max_drawdown_abs": to_float(entry.get("max_drawdown_abs")) or 0.0,
            "wins": to_int(entry.get("wins")),
            "losses": to_int(entry.get("losses")),
            "draws": to_int(entry.get("draws")),
            "winrate": coerce_rate_pct(winrate) or 0.0,
            "win_rate": coerce_rate_pct(winrate) or 0.0,
            "duration_avg": entry.get("duration_avg"),
            "cagr": coerce_profit_pct(entry.get("cagr"), ratio_value=entry.get("cagr")),
            "expectancy": to_float(entry.get("expectancy")),
            "expectancy_ratio": to_float(entry.get("expectancy_ratio")),
            "sortino": to_float(entry.get("sortino")),
            "sharpe": to_float(entry.get("sharpe")),
            "calmar": to_float(entry.get("calmar")),
            "sqn": to_float(entry.get("sqn")),
        }
    )
    return normalized


def normalize_stat_row(entry: dict[str, Any], starting_balance: float | None = None) -> dict[str, Any]:
    label = stringify_key(entry.get("key"))
    profit_total_pct = coerce_profit_pct(
        coalesce(entry.get("profit_total_pct"), entry.get("profit_sum_pct")),
        ratio_value=entry.get("profit_total"),
        abs_value=entry.get("profit_total_abs"),
        starting_balance=starting_balance,
    )
    profit_mean_pct = coerce_profit_pct(
        entry.get("profit_mean_pct"),
        ratio_value=entry.get("profit_mean"),
        starting_balance=starting_balance,
    )

    normalized = dict(entry)
    normalized.update(
        {
            "label": label,
            "key": entry.get("key"),
            "trades": to_int(entry.get("trades")),
            "profit_mean": to_float(entry.get("profit_mean")),
            "profit_mean_pct": profit_mean_pct,
            "profit_total": to_float(entry.get("profit_total")),
            "profit_total_abs": to_float(entry.get("profit_total_abs")) or 0.0,
            "profit_total_pct": profit_total_pct,
            "profit_sum_pct": profit_total_pct,
            "duration_avg": entry.get("duration_avg"),
            "wins": to_int(entry.get("wins")),
            "draws": to_int(entry.get("draws")),
            "losses": to_int(entry.get("losses")),
            "winrate": coerce_rate_pct(entry.get("winrate")) or 0.0,
            "win_rate": coerce_rate_pct(entry.get("winrate")) or 0.0,
            "cagr": coerce_profit_pct(entry.get("cagr"), ratio_value=entry.get("cagr")),
            "expectancy": to_float(entry.get("expectancy")),
            "expectancy_ratio": to_float(entry.get("expectancy_ratio")),
            "sortino": to_float(entry.get("sortino")),
            "sharpe": to_float(entry.get("sharpe")),
            "calmar": to_float(entry.get("calmar")),
            "sqn": to_float(entry.get("sqn")),
            "profit_factor": to_float(entry.get("profit_factor")) or 0.0,
            "max_drawdown_account": drawdown_to_pct(entry.get("max_drawdown_account")),
            "max_drawdown_abs": to_float(entry.get("max_drawdown_abs")) or 0.0,
        }
    )
    return normalized


def normalize_stat_rows(rows: list[dict[str, Any]], starting_balance: float | None = None) -> list[dict[str, Any]]:
    return [normalize_stat_row(row, starting_balance=starting_balance) for row in rows or [] if isinstance(row, dict)]


def normalize_daily_profit(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(result.get("daily_profit") or result.get("equity_curve") or [])
    normalized: list[dict[str, Any]] = []
    cumulative = 0.0
    for row in rows:
        if isinstance(row, dict):
            date = coalesce(row.get("date"), row.get("label"))
            profit = to_float(coalesce(row.get("profit"), row.get("profit_abs"), row.get("abs_profit"))) or 0.0
            cumulative = to_float(row.get("cumulative")) if row.get("cumulative") is not None else cumulative + profit
            normalized.append(
                {
                    **row,
                    "date": date,
                    "profit": profit,
                    "cumulative": cumulative,
                }
            )
    return normalized


def normalize_periodic_breakdown(result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    periodic = result.get("periodic_breakdown") or {}
    if not isinstance(periodic, dict):
        return {}

    normalized: dict[str, list[dict[str, Any]]] = {}
    for period, rows in periodic.items():
        if not isinstance(rows, list):
            continue
        cumulative = 0.0
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            profit_abs = to_float(coalesce(row.get("profit_abs"), row.get("abs_profit"))) or 0.0
            cumulative += profit_abs
            wins = to_int(row.get("wins"))
            losses = to_int(row.get("losses"))
            draws = to_int(row.get("draws"))
            trades = to_int(row.get("trades"))
            normalized_rows.append(
                {
                    **row,
                    "date": row.get("date"),
                    "date_ts": to_float(row.get("date_ts")),
                    "profit_abs": profit_abs,
                    "wins": wins,
                    "losses": losses,
                    "draws": draws,
                    "trades": trades,
                    "profit_factor": to_float(row.get("profit_factor")) or 0.0,
                    "win_rate": coerce_rate_pct((wins / trades) if trades else 0.0) or 0.0,
                    "cumulative_profit": cumulative,
                }
            )
        normalized[str(period)] = normalized_rows
    return normalized


__all__ = [
    "derive_avg_profit_pct_from_trades",
    "normalize_daily_profit",
    "normalize_per_pair",
    "normalize_periodic_breakdown",
    "normalize_stat_row",
    "normalize_stat_rows",
    "normalize_trade",
]
