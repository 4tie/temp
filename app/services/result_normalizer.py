from __future__ import annotations

import ast
import math
import statistics
from typing import Any


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    return int(_to_float(value) or 0)


def _to_int_or_none(value: Any) -> int | None:
    numeric = _to_float(value)
    if numeric is None:
        return None
    return int(numeric)


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _merge_unique_warnings(*warning_lists: list[Any]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for warnings in warning_lists:
        for warning in warnings or []:
            text = str(warning).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def _drawdown_to_pct(value: Any) -> float | None:
    numeric = _to_float(value)
    if numeric is None:
        return None
    numeric = abs(numeric)
    if numeric <= 1.0:
        return numeric * 100.0
    return numeric


def _coerce_rate_pct(value: Any) -> float | None:
    numeric = _to_float(value)
    if numeric is None:
        return None
    if abs(numeric) <= 1.0:
        return numeric * 100.0
    if abs(numeric) > 100.0 and abs(numeric / 100.0) <= 100.0:
        return numeric / 100.0
    return numeric


def _coerce_profit_pct(
    raw_value: Any,
    *,
    ratio_value: Any = None,
    abs_value: Any = None,
    starting_balance: Any = None,
    final_balance: Any = None,
) -> float | None:
    raw = _to_float(raw_value)
    derived: float | None = None

    starting = _to_float(starting_balance)
    ending = _to_float(final_balance)
    absolute = _to_float(abs_value)
    ratio = _to_float(ratio_value)

    if starting and ending is not None:
        derived = ((ending - starting) / starting) * 100.0
    elif starting and absolute is not None:
        derived = (absolute / starting) * 100.0
    elif ratio is not None:
        derived = ratio * 100.0 if abs(ratio) <= 1.0 else ratio

    if raw is None:
        return derived

    if derived is not None:
        tolerance = max(0.5, abs(derived) * 0.05)
        if abs(raw - derived) <= tolerance:
            return raw

        scaled = raw / 100.0
        if abs(scaled - derived) <= tolerance:
            return scaled

        if abs(raw) > max(250.0, abs(derived) * 3.0 + 25.0):
            return derived

    if abs(raw) <= 1.0:
        return raw * 100.0

    if abs(raw) > 1000.0 and abs(raw / 100.0) <= 1000.0:
        return raw / 100.0

    return raw


def _stringify_key(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for candidate in ("key", "pair", "label", "name"):
            nested = value.get(candidate)
            if nested not in (None, "", [], {}):
                return _stringify_key(nested)
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                parsed = None
            if parsed is not None and parsed is not value:
                return _stringify_key(parsed)
        return value
    if isinstance(value, (list, tuple)):
        return " -> ".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def _normalize_trade(trade: dict[str, Any]) -> dict[str, Any]:
    profit_abs = _coalesce(trade.get("profit"), trade.get("profit_abs"), trade.get("profitAbs"))
    profit_pct = _coalesce(trade.get("profitPct"), trade.get("profit_pct"), trade.get("profit_percent"))
    if profit_pct is None:
        profit_pct = _coerce_profit_pct(trade.get("profit_ratio"), ratio_value=trade.get("profit_ratio"))

    open_date = _coalesce(trade.get("openDate"), trade.get("open_date"))
    close_date = _coalesce(trade.get("closeDate"), trade.get("close_date"))
    exit_reason = _coalesce(trade.get("exitReason"), trade.get("exit_reason"), trade.get("sell_reason"))
    open_rate = _coalesce(trade.get("openRate"), trade.get("open_rate"))
    close_rate = _coalesce(trade.get("closeRate"), trade.get("close_rate"))
    min_rate = _coalesce(trade.get("minRate"), trade.get("min_rate"), trade.get("mae"))
    max_rate = _coalesce(trade.get("maxRate"), trade.get("max_rate"), trade.get("mfe"))
    orders = trade.get("orders")

    normalized = dict(trade)
    normalized.update(
        {
            "pair": trade.get("pair", ""),
            "enter_tag": trade.get("enter_tag", ""),
            "direction": trade.get("direction", trade.get("trade_direction", "short" if trade.get("is_short") else "long")),
            "profit": _to_float(profit_abs),
            "profit_abs": _to_float(profit_abs),
            "profitPct": _to_float(profit_pct),
            "profit_pct": _to_float(profit_pct),
            "openDate": open_date,
            "open_date": open_date,
            "closeDate": close_date,
            "close_date": close_date,
            "openTimestamp": _to_float(trade.get("openTimestamp", trade.get("open_timestamp"))),
            "closeTimestamp": _to_float(trade.get("closeTimestamp", trade.get("close_timestamp"))),
            "exitReason": exit_reason,
            "exit_reason": exit_reason,
            "openRate": _to_float(open_rate),
            "open_rate": _to_float(open_rate),
            "closeRate": _to_float(close_rate),
            "close_rate": _to_float(close_rate),
            "stakeAmount": _to_float(trade.get("stakeAmount", trade.get("stake_amount"))),
            "stake_amount": _to_float(trade.get("stakeAmount", trade.get("stake_amount"))),
            "amount": _to_float(trade.get("amount")),
            "leverage": _to_float(trade.get("leverage")),
            "minRate": _to_float(min_rate),
            "min_rate": _to_float(min_rate),
            "maxRate": _to_float(max_rate),
            "max_rate": _to_float(max_rate),
            "isOpen": bool(trade.get("isOpen", trade.get("is_open"))),
            "is_open": bool(trade.get("isOpen", trade.get("is_open"))),
            "is_short": bool(trade.get("is_short", False)),
            "duration": _coalesce(trade.get("duration"), trade.get("trade_duration")),
            "fee_open": _to_float(trade.get("fee_open")),
            "fee_close": _to_float(trade.get("fee_close")),
            "funding_fees": _to_float(trade.get("funding_fees")),
            "initial_stop_loss_abs": _to_float(trade.get("initial_stop_loss_abs")),
            "initial_stop_loss_ratio": _to_float(trade.get("initial_stop_loss_ratio")),
            "stop_loss_abs": _to_float(trade.get("stop_loss_abs")),
            "stop_loss_ratio": _to_float(trade.get("stop_loss_ratio")),
            "weekday": trade.get("weekday"),
            "orders": orders if isinstance(orders, list) else [],
        }
    )
    return normalized


def _derive_avg_profit_pct_from_trades(trades: list[dict[str, Any]]) -> float | None:
    values = []
    for trade in trades or []:
        value = _to_float(_coalesce(trade.get("profitPct"), trade.get("profit_pct"), trade.get("profit_percent")))
        if value is not None:
            values.append(value)
    if not values:
        return None
    return statistics.mean(values)


def _normalize_per_pair(entry: dict[str, Any], starting_balance: float | None = None) -> dict[str, Any]:
    pair = _coalesce(entry.get("pair"), entry.get("key"))
    trades = _coalesce(entry.get("trades"), entry.get("total_trades"))
    profit_percent = _coalesce(entry.get("profit_percent"), entry.get("profit_sum_pct"), entry.get("profit_total_pct"))
    max_drawdown = _coalesce(entry.get("max_drawdown"), entry.get("max_drawdown_account"))
    winrate = _coalesce(entry.get("winrate"), entry.get("win_rate"))

    normalized = dict(entry)
    normalized_profit_pct = _coerce_profit_pct(
        profit_percent,
        ratio_value=entry.get("profit_total"),
        abs_value=entry.get("profit_total_abs"),
        starting_balance=starting_balance,
    )
    normalized_profit_mean_pct = _coerce_profit_pct(
        entry.get("profit_mean_pct"),
        ratio_value=entry.get("profit_mean"),
        abs_value=entry.get("profit_mean_abs"),
        starting_balance=starting_balance,
    )
    normalized.update(
        {
            "pair": _stringify_key(pair),
            "key": pair,
            "label": _stringify_key(pair),
            "trades": _to_int(trades),
            "profit_percent": normalized_profit_pct,
            "profit_sum_pct": normalized_profit_pct,
            "profit_total_pct": normalized_profit_pct,
            "profit_total": _to_float(entry.get("profit_total")),
            "profit_mean": _to_float(entry.get("profit_mean")),
            "profit_mean_pct": normalized_profit_mean_pct,
            "profit_total_abs": _to_float(entry.get("profit_total_abs")) or 0.0,
            "profit_factor": _to_float(entry.get("profit_factor")) or 0.0,
            "max_drawdown": _drawdown_to_pct(max_drawdown),
            "max_drawdown_account": _drawdown_to_pct(entry.get("max_drawdown_account")),
            "max_drawdown_abs": _to_float(entry.get("max_drawdown_abs")) or 0.0,
            "wins": _to_int(entry.get("wins")),
            "losses": _to_int(entry.get("losses")),
            "draws": _to_int(entry.get("draws")),
            "winrate": _coerce_rate_pct(winrate) or 0.0,
            "win_rate": _coerce_rate_pct(winrate) or 0.0,
            "duration_avg": entry.get("duration_avg"),
            "cagr": _coerce_profit_pct(entry.get("cagr"), ratio_value=entry.get("cagr")),
            "expectancy": _to_float(entry.get("expectancy")),
            "expectancy_ratio": _to_float(entry.get("expectancy_ratio")),
            "sortino": _to_float(entry.get("sortino")),
            "sharpe": _to_float(entry.get("sharpe")),
            "calmar": _to_float(entry.get("calmar")),
            "sqn": _to_float(entry.get("sqn")),
        }
    )
    return normalized


def _build_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result.get("summary") or {})
    overview = dict(result.get("overview") or {})
    summary_metrics = dict(result.get("summary_metrics") or {})
    balance_metrics = dict(result.get("balance_metrics") or {})
    risk_metrics = dict(result.get("risk_metrics") or {})
    run_metadata = dict(result.get("run_metadata") or {})

    total_trades = _coalesce(summary.get("totalTrades"), overview.get("total_trades"), run_metadata.get("total_trades"))
    starting_balance = _to_float(_coalesce(summary.get("startingBalance"), balance_metrics.get("starting_balance"), overview.get("starting_balance")))
    final_balance = _to_float(_coalesce(summary.get("finalBalance"), balance_metrics.get("final_balance"), overview.get("final_balance")))
    total_profit_abs = _to_float(_coalesce(summary.get("totalProfit"), balance_metrics.get("profit_total_abs"), overview.get("profit_total_abs")))
    total_profit_ratio = _to_float(_coalesce(balance_metrics.get("profit_total"), overview.get("profit_total")))
    total_profit_pct = _coerce_profit_pct(
        _coalesce(summary.get("totalProfitPct"), overview.get("profit_percent")),
        ratio_value=total_profit_ratio,
        abs_value=total_profit_abs,
        starting_balance=starting_balance,
        final_balance=final_balance,
    )

    avg_profit = summary.get("avgProfit")
    if avg_profit is None:
        trades_count_val = _to_float(total_trades) or 0.0
        if trades_count_val > 0 and total_profit_abs is not None:
            avg_profit = total_profit_abs / trades_count_val

    avg_profit_pct = _coerce_profit_pct(
        _coalesce(summary.get("avgProfitPct"), overview.get("avg_profit_pct"), summary_metrics.get("profit_mean_pct")),
        ratio_value=summary_metrics.get("profit_mean"),
    )
    profit_factor = _to_float(_coalesce(summary.get("profitFactor"), overview.get("profit_factor"), summary_metrics.get("profit_factor")))
    win_rate = _coerce_rate_pct(_coalesce(summary.get("winRate"), overview.get("win_rate"), summary_metrics.get("winrate")))
    max_drawdown = _drawdown_to_pct(_coalesce(summary.get("maxDrawdown"), overview.get("max_drawdown"), risk_metrics.get("max_drawdown"), risk_metrics.get("max_drawdown_account")))
    max_drawdown_abs = _to_float(_coalesce(summary.get("maxDrawdownAbs"), overview.get("max_drawdown_abs"), risk_metrics.get("max_drawdown_abs")))
    max_drawdown_account = _drawdown_to_pct(_coalesce(summary.get("maxDrawdownAccount"), overview.get("max_drawdown_account"), risk_metrics.get("max_drawdown_account")))
    sharpe_ratio = _to_float(_coalesce(summary.get("sharpeRatio"), summary.get("sharpe_ratio"), summary_metrics.get("sharpe")))

    normalized = dict(summary)
    normalized.update(
        {
            "totalTrades": _to_int(total_trades),
            "totalProfit": total_profit_abs,
            "totalProfitPct": total_profit_pct,
            "avgProfit": _to_float(avg_profit),
            "avgProfitPct": avg_profit_pct,
            "profitFactor": profit_factor,
            "winRate": win_rate,
            "maxDrawdown": max_drawdown,
            "maxDrawdownAbs": max_drawdown_abs,
            "maxDrawdownAccount": max_drawdown_account,
            "startingBalance": starting_balance,
            "finalBalance": final_balance,
            "timeframe": _coalesce(summary.get("timeframe"), run_metadata.get("timeframe"), overview.get("timeframe"), ""),
            "stakeCurrency": _coalesce(summary.get("stakeCurrency"), run_metadata.get("stake_currency"), overview.get("stake_currency"), ""),
            "stakeAmount": _coalesce(summary.get("stakeAmount"), run_metadata.get("stake_amount"), overview.get("stake_amount"), ""),
            "maxOpenTrades": _to_int(_coalesce(summary.get("maxOpenTrades"), run_metadata.get("max_open_trades"), overview.get("max_open_trades"))),
            "bestPair": _stringify_key(_coalesce(summary.get("bestPair"), run_metadata.get("best_pair"), overview.get("best_pair"), "")),
            "worstPair": _stringify_key(_coalesce(summary.get("worstPair"), run_metadata.get("worst_pair"), overview.get("worst_pair"), "")),
            "tradingVolume": _to_float(_coalesce(summary.get("tradingVolume"), overview.get("trading_volume"), summary_metrics.get("total_volume"))),
            "sharpe_ratio": sharpe_ratio,
            "sharpeRatio": sharpe_ratio,
            "cagr": _coerce_profit_pct(summary_metrics.get("cagr"), ratio_value=summary_metrics.get("cagr")),
            "calmarRatio": _to_float(summary_metrics.get("calmar")),
            "sortinoRatio": _to_float(summary_metrics.get("sortino")),
            "sqn": _to_float(summary_metrics.get("sqn")),
            "expectancy": _to_float(summary_metrics.get("expectancy")),
            "expectancyRatio": _to_float(summary_metrics.get("expectancy_ratio")),
            "profitMedian": _to_float(summary_metrics.get("profit_median")),
            "avgStakeAmount": _to_float(summary_metrics.get("avg_stake_amount")),
            "marketChange": _coerce_profit_pct(summary_metrics.get("market_change"), ratio_value=summary_metrics.get("market_change")),
            "bestDayPct": _coerce_profit_pct(summary_metrics.get("backtest_best_day"), ratio_value=summary_metrics.get("backtest_best_day")),
            "bestDayAbs": _to_float(summary_metrics.get("backtest_best_day_abs")),
            "worstDayPct": _coerce_profit_pct(summary_metrics.get("backtest_worst_day"), ratio_value=summary_metrics.get("backtest_worst_day")),
            "worstDayAbs": _to_float(summary_metrics.get("backtest_worst_day_abs")),
            "winningDays": _to_int(run_metadata.get("winning_days")),
            "losingDays": _to_int(run_metadata.get("losing_days")),
            "drawDays": _to_int(run_metadata.get("draw_days")),
            "maxConsecutiveWins": _to_int(risk_metrics.get("max_consecutive_wins")),
            "maxConsecutiveLosses": _to_int(risk_metrics.get("max_consecutive_losses")),
            "maxRelativeDrawdown": _drawdown_to_pct(risk_metrics.get("max_relative_drawdown")),
            "drawdownStart": risk_metrics.get("drawdown_start"),
            "drawdownEnd": risk_metrics.get("drawdown_end"),
            "drawdownDuration": risk_metrics.get("drawdown_duration"),
            "tradeCountLong": _to_int_or_none(run_metadata.get("trade_count_long")),
            "tradeCountShort": _to_int_or_none(run_metadata.get("trade_count_short")),
            "totalProfitLong": _to_float(balance_metrics.get("profit_total_long_abs")),
            "totalProfitLongPct": _coerce_profit_pct(
                balance_metrics.get("profit_total_long"),
                ratio_value=balance_metrics.get("profit_total_long"),
                abs_value=balance_metrics.get("profit_total_long_abs"),
                starting_balance=starting_balance,
            ),
            "totalProfitShort": _to_float(balance_metrics.get("profit_total_short_abs")),
            "totalProfitShortPct": _coerce_profit_pct(
                balance_metrics.get("profit_total_short"),
                ratio_value=balance_metrics.get("profit_total_short"),
                abs_value=balance_metrics.get("profit_total_short_abs"),
                starting_balance=starting_balance,
            ),
            "holdingAvg": run_metadata.get("holding_avg"),
            "winnerHoldingAvg": run_metadata.get("winner_holding_avg"),
            "loserHoldingAvg": run_metadata.get("loser_holding_avg"),
        }
    )

    normalized.update(
        {
            "total_trades": normalized["totalTrades"],
            "profit_total": normalized["totalProfit"],
            "profit_total_pct": normalized["totalProfitPct"],
            "avg_profit": normalized["avgProfit"],
            "avg_profit_pct": normalized["avgProfitPct"],
            "profit_factor": normalized["profitFactor"],
            "win_rate": normalized["winRate"],
            "max_drawdown_pct": normalized["maxDrawdown"],
            "max_drawdown_abs": normalized["maxDrawdownAbs"],
            "sharpe_ratio": normalized["sharpe_ratio"],
        }
    )
    return normalized


def _build_overview(summary: dict[str, Any]) -> dict[str, Any]:
    profit_total_abs = _to_float(summary.get("totalProfit"))
    starting_balance = _to_float(summary.get("startingBalance"))
    final_balance = _to_float(summary.get("finalBalance"))
    if starting_balance and profit_total_abs is not None:
        profit_total_ratio = profit_total_abs / starting_balance
    else:
        profit_total_ratio = None

    profit_percent = _coerce_profit_pct(
        summary.get("totalProfitPct"),
        ratio_value=profit_total_ratio,
        abs_value=profit_total_abs,
        starting_balance=starting_balance,
        final_balance=final_balance,
    )

    return {
        "total_trades": _to_int(summary.get("totalTrades")),
        "profit_total": profit_total_ratio,
        "profit_total_abs": profit_total_abs,
        "profit_percent": profit_percent,
        "profit_factor": _to_float(summary.get("profitFactor")),
        "win_rate": _coerce_rate_pct(summary.get("winRate")),
        "max_drawdown": (_to_float(summary.get("maxDrawdown")) / 100.0) if _to_float(summary.get("maxDrawdown")) is not None else None,
        "max_drawdown_abs": _to_float(summary.get("maxDrawdownAbs")),
        "max_drawdown_account": (_to_float(summary.get("maxDrawdownAccount")) / 100.0) if _to_float(summary.get("maxDrawdownAccount")) is not None else None,
        "avg_profit_pct": _to_float(summary.get("avgProfitPct")),
        "best_pair": summary.get("bestPair", ""),
        "worst_pair": summary.get("worstPair", ""),
        "trading_volume": _to_float(summary.get("tradingVolume")),
        "starting_balance": starting_balance,
        "final_balance": final_balance,
        "timeframe": summary.get("timeframe", ""),
        "stake_currency": summary.get("stakeCurrency", ""),
        "stake_amount": summary.get("stakeAmount", ""),
        "max_open_trades": _to_int(summary.get("maxOpenTrades")),
        "sharpe_ratio": _to_float(summary.get("sharpeRatio", summary.get("sharpe_ratio"))),
    }


def _compute_advanced_metrics(trades: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
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

    total_profit_pct = _to_float(summary.get("totalProfitPct"))
    max_drawdown_pct = _to_float(summary.get("maxDrawdown"))
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

    net_profit = _to_float(summary.get("totalProfit"))
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


def _normalize_summary_metrics(result: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("summary_metrics") or {})
    normalized = dict(section)
    normalized.update(
        {
            "cagr": _coerce_profit_pct(section.get("cagr"), ratio_value=section.get("cagr")),
            "calmar": _to_float(section.get("calmar")),
            "sortino": _to_float(section.get("sortino")),
            "sharpe": _to_float(section.get("sharpe", summary.get("sharpeRatio"))),
            "sqn": _to_float(section.get("sqn")),
            "expectancy": _to_float(section.get("expectancy")),
            "expectancy_ratio": _to_float(section.get("expectancy_ratio")),
            "profit_mean": _to_float(section.get("profit_mean")),
            "profit_mean_pct": _coerce_profit_pct(section.get("profit_mean_pct"), ratio_value=section.get("profit_mean")),
            "profit_median": _to_float(section.get("profit_median")),
            "avg_stake_amount": _to_float(section.get("avg_stake_amount")),
            "total_volume": _to_float(section.get("total_volume")),
            "market_change": _coerce_profit_pct(section.get("market_change"), ratio_value=section.get("market_change")),
            "backtest_best_day": _coerce_profit_pct(section.get("backtest_best_day"), ratio_value=section.get("backtest_best_day")),
            "backtest_best_day_abs": _to_float(section.get("backtest_best_day_abs")),
            "backtest_worst_day": _coerce_profit_pct(section.get("backtest_worst_day"), ratio_value=section.get("backtest_worst_day")),
            "backtest_worst_day_abs": _to_float(section.get("backtest_worst_day_abs")),
            "profit_factor": _to_float(section.get("profit_factor")),
            "wins": _to_int(section.get("wins")),
            "losses": _to_int(section.get("losses")),
            "draws": _to_int(section.get("draws")),
            "winrate": _coerce_rate_pct(section.get("winrate")),
        }
    )
    return normalized


def _normalize_balance_metrics(result: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("balance_metrics") or {})
    starting_balance = _to_float(_coalesce(section.get("starting_balance"), summary.get("startingBalance"), result.get("overview", {}).get("starting_balance"))) or 0.0
    final_balance = _to_float(_coalesce(section.get("final_balance"), summary.get("finalBalance"), result.get("overview", {}).get("final_balance"))) or 0.0
    normalized = dict(section)
    normalized.update(
        {
            "starting_balance": starting_balance,
            "final_balance": final_balance,
            "dry_run_wallet": _to_float(section.get("dry_run_wallet")),
            "profit_total": _to_float(section.get("profit_total")),
            "profit_total_abs": _to_float(section.get("profit_total_abs")),
            "profit_total_pct": _coerce_profit_pct(
                _coalesce(section.get("profit_total_pct"), summary.get("totalProfitPct")),
                ratio_value=section.get("profit_total"),
                abs_value=section.get("profit_total_abs"),
                starting_balance=starting_balance,
                final_balance=final_balance,
            ),
            "profit_total_long": _to_float(section.get("profit_total_long")),
            "profit_total_long_abs": _to_float(section.get("profit_total_long_abs")),
            "profit_total_long_pct": _coerce_profit_pct(
                section.get("profit_total_long"),
                ratio_value=section.get("profit_total_long"),
                abs_value=section.get("profit_total_long_abs"),
                starting_balance=starting_balance,
            ),
            "profit_total_short": _to_float(section.get("profit_total_short")),
            "profit_total_short_abs": _to_float(section.get("profit_total_short_abs")),
            "profit_total_short_pct": _coerce_profit_pct(
                section.get("profit_total_short"),
                ratio_value=section.get("profit_total_short"),
                abs_value=section.get("profit_total_short_abs"),
                starting_balance=starting_balance,
            ),
        }
    )
    return normalized


def _normalize_risk_metrics(result: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("risk_metrics") or {})
    normalized = dict(section)
    normalized.update(
        {
            "max_drawdown": _drawdown_to_pct(_coalesce(section.get("max_drawdown"), summary.get("maxDrawdown"))),
            "max_drawdown_pct": _drawdown_to_pct(_coalesce(section.get("max_drawdown_account"), section.get("max_drawdown"), summary.get("maxDrawdown"))),
            "max_drawdown_abs": _to_float(_coalesce(section.get("max_drawdown_abs"), summary.get("maxDrawdownAbs"))),
            "max_drawdown_account": _drawdown_to_pct(_coalesce(section.get("max_drawdown_account"), summary.get("maxDrawdownAccount"))),
            "max_relative_drawdown": _drawdown_to_pct(section.get("max_relative_drawdown")),
            "drawdown_start": section.get("drawdown_start"),
            "drawdown_start_ts": _to_float(section.get("drawdown_start_ts")),
            "drawdown_end": section.get("drawdown_end"),
            "drawdown_end_ts": _to_float(section.get("drawdown_end_ts")),
            "drawdown_duration": section.get("drawdown_duration"),
            "drawdown_duration_s": _to_float(section.get("drawdown_duration_s")),
            "max_drawdown_high": _to_float(section.get("max_drawdown_high")),
            "max_drawdown_low": _to_float(section.get("max_drawdown_low")),
            "max_consecutive_wins": _to_int(section.get("max_consecutive_wins")),
            "max_consecutive_losses": _to_int(section.get("max_consecutive_losses")),
        }
    )
    return normalized


def _normalize_run_metadata(result: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("run_metadata") or {})
    normalized = dict(section)
    normalized.update(
        {
            "strategy_name": _coalesce(section.get("strategy_name"), result.get("strategy_name"), result.get("strategy")),
            "backtest_start": section.get("backtest_start"),
            "backtest_start_ts": _to_float(section.get("backtest_start_ts")),
            "backtest_end": section.get("backtest_end"),
            "backtest_end_ts": _to_float(section.get("backtest_end_ts")),
            "backtest_run_start_ts": _to_float(section.get("backtest_run_start_ts")),
            "backtest_run_end_ts": _to_float(section.get("backtest_run_end_ts")),
            "timeframe": _coalesce(section.get("timeframe"), summary.get("timeframe")),
            "timeframe_detail": section.get("timeframe_detail"),
            "timerange": section.get("timerange"),
            "stake_currency": _coalesce(section.get("stake_currency"), summary.get("stakeCurrency")),
            "stake_currency_decimals": _to_int(section.get("stake_currency_decimals")),
            "stake_amount": _coalesce(section.get("stake_amount"), summary.get("stakeAmount")),
            "max_open_trades": _to_int(_coalesce(section.get("max_open_trades"), summary.get("maxOpenTrades"))),
            "max_open_trades_setting": _to_int(section.get("max_open_trades_setting")),
            "trade_count_long": _to_int(section.get("trade_count_long")),
            "trade_count_short": _to_int(section.get("trade_count_short")),
            "trading_mode": section.get("trading_mode"),
            "margin_mode": section.get("margin_mode"),
            "backtest_days": _to_int(section.get("backtest_days")),
            "trades_per_day": _to_float(section.get("trades_per_day")),
            "winning_days": _to_int(section.get("winning_days")),
            "losing_days": _to_int(section.get("losing_days")),
            "draw_days": _to_int(section.get("draw_days")),
            "best_pair": _stringify_key(section.get("best_pair")),
            "worst_pair": _stringify_key(section.get("worst_pair")),
            "avg_duration": section.get("avg_duration"),
            "holding_avg": section.get("holding_avg"),
            "holding_avg_s": _to_float(section.get("holding_avg_s")),
            "winner_holding_avg": section.get("winner_holding_avg"),
            "winner_holding_avg_s": _to_float(section.get("winner_holding_avg_s")),
            "winner_holding_min": section.get("winner_holding_min"),
            "winner_holding_min_s": _to_float(section.get("winner_holding_min_s")),
            "winner_holding_max": section.get("winner_holding_max"),
            "winner_holding_max_s": _to_float(section.get("winner_holding_max_s")),
            "loser_holding_avg": section.get("loser_holding_avg"),
            "loser_holding_avg_s": _to_float(section.get("loser_holding_avg_s")),
            "loser_holding_min": section.get("loser_holding_min"),
            "loser_holding_min_s": _to_float(section.get("loser_holding_min_s")),
            "loser_holding_max": section.get("loser_holding_max"),
            "loser_holding_max_s": _to_float(section.get("loser_holding_max_s")),
        }
    )
    return normalized


def _normalize_config_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("config_snapshot") or {})
    normalized = dict(section)
    normalized.update(
        {
            "stoploss": _coerce_profit_pct(section.get("stoploss"), ratio_value=section.get("stoploss")),
            "minimal_roi": section.get("minimal_roi") if isinstance(section.get("minimal_roi"), dict) else {},
            "trailing_stop": bool(section.get("trailing_stop")) if section.get("trailing_stop") is not None else False,
            "trailing_stop_positive": _coerce_profit_pct(section.get("trailing_stop_positive"), ratio_value=section.get("trailing_stop_positive")),
            "trailing_stop_positive_offset": _coerce_profit_pct(section.get("trailing_stop_positive_offset"), ratio_value=section.get("trailing_stop_positive_offset")),
            "trailing_only_offset_is_reached": bool(section.get("trailing_only_offset_is_reached")) if section.get("trailing_only_offset_is_reached") is not None else False,
            "use_custom_stoploss": bool(section.get("use_custom_stoploss")) if section.get("use_custom_stoploss") is not None else False,
            "use_exit_signal": bool(section.get("use_exit_signal")) if section.get("use_exit_signal") is not None else False,
            "exit_profit_only": bool(section.get("exit_profit_only")) if section.get("exit_profit_only") is not None else False,
            "exit_profit_offset": _coerce_profit_pct(section.get("exit_profit_offset"), ratio_value=section.get("exit_profit_offset")),
            "ignore_roi_if_entry_signal": bool(section.get("ignore_roi_if_entry_signal")) if section.get("ignore_roi_if_entry_signal") is not None else False,
            "enable_protections": bool(section.get("enable_protections")) if section.get("enable_protections") is not None else False,
            "locks": section.get("locks") if isinstance(section.get("locks"), list) else [],
            "pairlist": section.get("pairlist") if isinstance(section.get("pairlist"), list) else [],
            "freqai_identifier": section.get("freqai_identifier"),
            "freqaimodel": section.get("freqaimodel"),
        }
    )
    return normalized


def _normalize_raw_artifact(raw_artifact: dict[str, Any] | None) -> dict[str, Any]:
    section = dict(raw_artifact or {})
    return {
        "available": bool(section.get("available")),
        "type": section.get("type"),
        "file_name": section.get("file_name"),
        "file_path": section.get("file_path"),
        "inner_file_name": section.get("inner_file_name"),
        "run_local": bool(section.get("run_local")),
    }


def _normalize_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("diagnostics") or {})
    warnings = list(_coalesce(section.get("warnings"), result.get("warnings"), []))
    return {
        "rejected_signals": _to_int(section.get("rejected_signals")),
        "canceled_entry_orders": _to_int(section.get("canceled_entry_orders")),
        "canceled_trade_entries": _to_int(section.get("canceled_trade_entries")),
        "replaced_entry_orders": _to_int(section.get("replaced_entry_orders")),
        "timedout_entry_orders": _to_int(section.get("timedout_entry_orders")),
        "timedout_exit_orders": _to_int(section.get("timedout_exit_orders")),
        "locks": section.get("locks") if isinstance(section.get("locks"), list) else [],
        "warnings": warnings,
        "raw_artifact": _normalize_raw_artifact(_coalesce(section.get("raw_artifact"), result.get("raw_artifact"))),
    }


def _collect_integrity_warnings(
    result: dict[str, Any],
    summary: dict[str, Any],
    balance_metrics: dict[str, Any],
    run_metadata: dict[str, Any],
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    warnings: list[str] = []
    raw_summary = dict(result.get("summary") or {})
    raw_balance = dict(result.get("balance_metrics") or {})

    # Missing critical metrics should not silently appear as zero.
    critical_metrics = {
        "summary.avgProfitPct": summary.get("avgProfitPct"),
        "balance.starting_balance": balance_metrics.get("starting_balance"),
        "balance.final_balance": balance_metrics.get("final_balance"),
        "balance.profit_total_long_abs": balance_metrics.get("profit_total_long_abs"),
        "balance.profit_total_long_pct": balance_metrics.get("profit_total_long_pct"),
        "balance.profit_total_short_abs": balance_metrics.get("profit_total_short_abs"),
        "balance.profit_total_short_pct": balance_metrics.get("profit_total_short_pct"),
    }
    for key, value in critical_metrics.items():
        if not _has_value(value):
            warnings.append(f"Missing metric: {key}")

    # totalProfitPct consistency: enforce canonical balance-derived value.
    starting = _to_float(balance_metrics.get("starting_balance"))
    ending = _to_float(balance_metrics.get("final_balance"))
    if starting and ending is not None:
        derived_total_pct = ((ending - starting) / starting) * 100.0
        raw_total_pct = _to_float(summary.get("totalProfitPct"))
        original_total_pct = _to_float(_coalesce(raw_summary.get("totalProfitPct"), raw_summary.get("profit_total_pct")))
        if raw_total_pct is None:
            summary["totalProfitPct"] = derived_total_pct
        else:
            tolerance = max(0.5, abs(derived_total_pct) * 0.05)
            if abs(raw_total_pct - derived_total_pct) > tolerance:
                summary["totalProfitPct"] = derived_total_pct
                warnings.append(
                    "Corrected metric mismatch: summary.totalProfitPct recalculated from final_balance and starting_balance."
                )
            elif original_total_pct is not None and abs(original_total_pct - derived_total_pct) > tolerance:
                warnings.append(
                    "Corrected metric mismatch: summary.totalProfitPct recalculated from final_balance and starting_balance."
                )

    # avgProfitPct consistency: align with summary_metrics.profit_mean_pct when both available.
    profit_mean_pct = _coerce_profit_pct(
        _coalesce(
            result.get("summary_metrics", {}).get("profit_mean_pct"),
            result.get("summary_metrics", {}).get("profit_mean"),
        ),
        ratio_value=result.get("summary_metrics", {}).get("profit_mean"),
    )
    avg_profit_pct = _to_float(summary.get("avgProfitPct"))
    if profit_mean_pct is not None and avg_profit_pct is not None:
        tolerance = max(0.1, abs(profit_mean_pct) * 0.05)
        if abs(avg_profit_pct - profit_mean_pct) > tolerance:
            summary["avgProfitPct"] = profit_mean_pct
            warnings.append("Corrected metric mismatch: summary.avgProfitPct aligned with summary_metrics.profit_mean_pct.")
    elif profit_mean_pct is not None and avg_profit_pct is None:
        summary["avgProfitPct"] = profit_mean_pct

    # Long/short pct consistency against starting balance.
    if starting:
        for side in ("long", "short"):
            abs_key = f"profit_total_{side}_abs"
            pct_key = f"profit_total_{side}_pct"
            abs_value = _to_float(balance_metrics.get(abs_key))
            pct_value = _to_float(balance_metrics.get(pct_key))
            original_pct = _to_float(raw_balance.get(pct_key))
            if abs_value is None:
                continue
            derived_pct = (abs_value / starting) * 100.0
            if pct_value is None:
                balance_metrics[pct_key] = derived_pct
                continue
            tolerance = max(0.1, abs(derived_pct) * 0.05)
            if abs(pct_value - derived_pct) > tolerance:
                balance_metrics[pct_key] = derived_pct
                warnings.append(
                    f"Corrected metric mismatch: balance.{pct_key} recalculated from {abs_key} and starting_balance."
                )
            elif original_pct is not None and abs(original_pct - derived_pct) > tolerance:
                warnings.append(
                    f"Corrected metric mismatch: balance.{pct_key} recalculated from {abs_key} and starting_balance."
                )

    if _to_int_or_none(run_metadata.get("trade_count_short")) is None:
        warnings.append("Missing metric: run_metadata.trade_count_short")

    return warnings, summary, balance_metrics


def _normalize_stat_row(entry: dict[str, Any], starting_balance: float | None = None) -> dict[str, Any]:
    label = _stringify_key(entry.get("key"))
    profit_total_pct = _coerce_profit_pct(
        _coalesce(entry.get("profit_total_pct"), entry.get("profit_sum_pct")),
        ratio_value=entry.get("profit_total"),
        abs_value=entry.get("profit_total_abs"),
        starting_balance=starting_balance,
    )
    profit_mean_pct = _coerce_profit_pct(
        entry.get("profit_mean_pct"),
        ratio_value=entry.get("profit_mean"),
        starting_balance=starting_balance,
    )

    normalized = dict(entry)
    normalized.update(
        {
            "label": label,
            "key": entry.get("key"),
            "trades": _to_int(entry.get("trades")),
            "profit_mean": _to_float(entry.get("profit_mean")),
            "profit_mean_pct": profit_mean_pct,
            "profit_total": _to_float(entry.get("profit_total")),
            "profit_total_abs": _to_float(entry.get("profit_total_abs")) or 0.0,
            "profit_total_pct": profit_total_pct,
            "profit_sum_pct": profit_total_pct,
            "duration_avg": entry.get("duration_avg"),
            "wins": _to_int(entry.get("wins")),
            "draws": _to_int(entry.get("draws")),
            "losses": _to_int(entry.get("losses")),
            "winrate": _coerce_rate_pct(entry.get("winrate")) or 0.0,
            "win_rate": _coerce_rate_pct(entry.get("winrate")) or 0.0,
            "cagr": _coerce_profit_pct(entry.get("cagr"), ratio_value=entry.get("cagr")),
            "expectancy": _to_float(entry.get("expectancy")),
            "expectancy_ratio": _to_float(entry.get("expectancy_ratio")),
            "sortino": _to_float(entry.get("sortino")),
            "sharpe": _to_float(entry.get("sharpe")),
            "calmar": _to_float(entry.get("calmar")),
            "sqn": _to_float(entry.get("sqn")),
            "profit_factor": _to_float(entry.get("profit_factor")) or 0.0,
            "max_drawdown_account": _drawdown_to_pct(entry.get("max_drawdown_account")),
            "max_drawdown_abs": _to_float(entry.get("max_drawdown_abs")) or 0.0,
        }
    )
    return normalized


def _normalize_stat_rows(rows: list[dict[str, Any]], starting_balance: float | None = None) -> list[dict[str, Any]]:
    return [_normalize_stat_row(row, starting_balance=starting_balance) for row in rows or [] if isinstance(row, dict)]


def _normalize_daily_profit(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(result.get("daily_profit") or result.get("equity_curve") or [])
    normalized: list[dict[str, Any]] = []
    cumulative = 0.0
    for row in rows:
        if isinstance(row, dict):
            date = _coalesce(row.get("date"), row.get("label"))
            profit = _to_float(_coalesce(row.get("profit"), row.get("profit_abs"), row.get("abs_profit"))) or 0.0
            cumulative = _to_float(row.get("cumulative")) if row.get("cumulative") is not None else cumulative + profit
            normalized.append(
                {
                    **row,
                    "date": date,
                    "profit": profit,
                    "cumulative": cumulative,
                }
            )
    return normalized


def _normalize_periodic_breakdown(result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
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
            profit_abs = _to_float(_coalesce(row.get("profit_abs"), row.get("abs_profit"))) or 0.0
            cumulative += profit_abs
            wins = _to_int(row.get("wins"))
            losses = _to_int(row.get("losses"))
            draws = _to_int(row.get("draws"))
            trades = _to_int(row.get("trades"))
            normalized_rows.append(
                {
                    **row,
                    "date": row.get("date"),
                    "date_ts": _to_float(row.get("date_ts")),
                    "profit_abs": profit_abs,
                    "wins": wins,
                    "losses": losses,
                    "draws": draws,
                    "trades": trades,
                    "profit_factor": _to_float(row.get("profit_factor")) or 0.0,
                    "win_rate": _coerce_rate_pct((wins / trades) if trades else 0.0) or 0.0,
                    "cumulative_profit": cumulative,
                }
            )
        normalized[str(period)] = normalized_rows
    return normalized


def normalize_backtest_result(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {
            "summary": {},
            "overview": {},
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

    normalized = dict(result)
    normalized_trades = [_normalize_trade(trade) for trade in result.get("trades") or [] if isinstance(trade, dict)]
    summary = _build_summary(result)
    overview = _build_overview(summary)
    advanced_metrics = dict(result.get("advanced_metrics") or {})

    computed_advanced = _compute_advanced_metrics(normalized_trades, summary)
    for key, value in computed_advanced.items():
        advanced_metrics.setdefault(key, value)

    # If source did not provide avg profit %, derive it from normalized trades
    # to avoid silently showing 0.00% for missing fields.
    if not _has_value(_coalesce(result.get("summary", {}).get("avgProfitPct"), result.get("overview", {}).get("avg_profit_pct"), result.get("summary_metrics", {}).get("profit_mean_pct"))):
        derived_avg_pct = _derive_avg_profit_pct_from_trades(normalized_trades)
        if derived_avg_pct is not None:
            summary["avgProfitPct"] = derived_avg_pct
            summary["avg_profit_pct"] = derived_avg_pct
            overview["avg_profit_pct"] = derived_avg_pct

    sharpe = _coalesce(summary.get("sharpe_ratio"), advanced_metrics.get("sharpe_ratio"))
    summary["sharpe_ratio"] = sharpe
    summary["sharpeRatio"] = sharpe
    overview["sharpe_ratio"] = sharpe

    starting_balance = _to_float(summary.get("startingBalance"))
    normalized_per_pair = [
        _normalize_per_pair(entry, starting_balance=starting_balance)
        for entry in result.get("per_pair") or []
        if isinstance(entry, dict)
    ]
    summary_metrics = _normalize_summary_metrics(result, summary)
    balance_metrics = _normalize_balance_metrics(result, summary)
    risk_metrics = _normalize_risk_metrics(result, summary)
    run_metadata = _normalize_run_metadata(result, summary)
    integrity_warnings, summary, balance_metrics = _collect_integrity_warnings(
        result=result,
        summary=summary,
        balance_metrics=balance_metrics,
        run_metadata=run_metadata,
    )
    overview = _build_overview(summary)
    config_snapshot = _normalize_config_snapshot(result)
    diagnostics = _normalize_diagnostics(result)
    diagnostics["warnings"] = _merge_unique_warnings(diagnostics.get("warnings") or [], integrity_warnings)
    diagnostics["integrity_warnings"] = integrity_warnings
    daily_profit = _normalize_daily_profit(result)
    periodic_breakdown = _normalize_periodic_breakdown(result)
    raw_artifact = diagnostics["raw_artifact"]

    normalized.update(
        {
            "summary": summary,
            "overview": overview,
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
            "exit_reason_summary": _normalize_stat_rows(result.get("exit_reason_summary") or [], starting_balance=starting_balance),
            "results_per_enter_tag": _normalize_stat_rows(result.get("results_per_enter_tag") or [], starting_balance=starting_balance),
            "mix_tag_stats": _normalize_stat_rows(result.get("mix_tag_stats") or [], starting_balance=starting_balance),
            "left_open_trades": _normalize_stat_rows(result.get("left_open_trades") or [], starting_balance=starting_balance),
            "periodic_breakdown": periodic_breakdown,
            "warnings": _merge_unique_warnings(result.get("warnings") or [], diagnostics.get("warnings") or []),
            "raw_artifact": raw_artifact,
        }
    )
    if "strategy" not in normalized and result.get("strategy_name"):
        normalized["strategy"] = result.get("strategy_name")
    return normalized
