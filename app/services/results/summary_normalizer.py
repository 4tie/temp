from __future__ import annotations

import ast
from typing import Any


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int:
    return int(to_float(value) or 0)


def to_int_or_none(value: Any) -> int | None:
    numeric = to_float(value)
    if numeric is None:
        return None
    return int(numeric)


def coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def has_value(value: Any) -> bool:
    return value is not None and value != ""


def merge_unique_warnings(*warning_lists: list[Any]) -> list[str]:
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


def drawdown_to_pct(value: Any) -> float | None:
    numeric = to_float(value)
    if numeric is None:
        return None
    numeric = abs(numeric)
    if numeric <= 1.0:
        return numeric * 100.0
    return numeric


def coerce_rate_pct(value: Any) -> float | None:
    numeric = to_float(value)
    if numeric is None:
        return None
    if abs(numeric) <= 1.0:
        return numeric * 100.0
    if abs(numeric) > 100.0 and abs(numeric / 100.0) <= 100.0:
        return numeric / 100.0
    return numeric


def coerce_profit_pct(
    raw_value: Any,
    *,
    ratio_value: Any = None,
    abs_value: Any = None,
    starting_balance: Any = None,
    final_balance: Any = None,
) -> float | None:
    raw = to_float(raw_value)
    derived: float | None = None

    starting = to_float(starting_balance)
    ending = to_float(final_balance)
    absolute = to_float(abs_value)
    ratio = to_float(ratio_value)

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


def stringify_key(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for candidate in ("key", "pair", "label", "name"):
            nested = value.get(candidate)
            if nested not in (None, "", [], {}):
                return stringify_key(nested)
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                parsed = None
            if parsed is not None and parsed is not value:
                return stringify_key(parsed)
        return value
    if isinstance(value, (list, tuple)):
        return " -> ".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result.get("summary") or {})
    overview = dict(result.get("overview") or {})
    summary_metrics = dict(result.get("summary_metrics") or {})
    balance_metrics = dict(result.get("balance_metrics") or {})
    risk_metrics = dict(result.get("risk_metrics") or {})
    run_metadata = dict(result.get("run_metadata") or {})

    total_trades = coalesce(summary.get("totalTrades"), overview.get("total_trades"), run_metadata.get("total_trades"))
    starting_balance = to_float(coalesce(summary.get("startingBalance"), balance_metrics.get("starting_balance"), overview.get("starting_balance")))
    final_balance = to_float(coalesce(summary.get("finalBalance"), balance_metrics.get("final_balance"), overview.get("final_balance")))
    total_profit_abs = to_float(coalesce(summary.get("totalProfit"), balance_metrics.get("profit_total_abs"), overview.get("profit_total_abs")))
    total_profit_ratio = to_float(coalesce(balance_metrics.get("profit_total"), overview.get("profit_total")))
    total_profit_pct = coerce_profit_pct(
        coalesce(summary.get("totalProfitPct"), overview.get("profit_percent")),
        ratio_value=total_profit_ratio,
        abs_value=total_profit_abs,
        starting_balance=starting_balance,
        final_balance=final_balance,
    )

    avg_profit = summary.get("avgProfit")
    if avg_profit is None:
        trades_count_val = to_float(total_trades) or 0.0
        if trades_count_val > 0 and total_profit_abs is not None:
            avg_profit = total_profit_abs / trades_count_val

    avg_profit_pct = coerce_profit_pct(
        coalesce(summary.get("avgProfitPct"), overview.get("avg_profit_pct"), summary_metrics.get("profit_mean_pct")),
        ratio_value=summary_metrics.get("profit_mean"),
    )
    profit_factor = to_float(coalesce(summary.get("profitFactor"), overview.get("profit_factor"), summary_metrics.get("profit_factor")))
    win_rate = coerce_rate_pct(coalesce(summary.get("winRate"), overview.get("win_rate"), summary_metrics.get("winrate")))
    max_drawdown = drawdown_to_pct(coalesce(summary.get("maxDrawdown"), overview.get("max_drawdown"), risk_metrics.get("max_drawdown"), risk_metrics.get("max_drawdown_account")))
    max_drawdown_abs = to_float(coalesce(summary.get("maxDrawdownAbs"), overview.get("max_drawdown_abs"), risk_metrics.get("max_drawdown_abs")))
    max_drawdown_account = drawdown_to_pct(coalesce(summary.get("maxDrawdownAccount"), overview.get("max_drawdown_account"), risk_metrics.get("max_drawdown_account")))
    sharpe_ratio = to_float(coalesce(summary.get("sharpeRatio"), summary.get("sharpe_ratio"), summary_metrics.get("sharpe")))

    normalized = dict(summary)
    normalized.update(
        {
            "totalTrades": to_int(total_trades),
            "totalProfit": total_profit_abs,
            "totalProfitPct": total_profit_pct,
            "avgProfit": to_float(avg_profit),
            "avgProfitPct": avg_profit_pct,
            "profitFactor": profit_factor,
            "winRate": win_rate,
            "maxDrawdown": max_drawdown,
            "maxDrawdownAbs": max_drawdown_abs,
            "maxDrawdownAccount": max_drawdown_account,
            "startingBalance": starting_balance,
            "finalBalance": final_balance,
            "timeframe": coalesce(summary.get("timeframe"), run_metadata.get("timeframe"), overview.get("timeframe"), ""),
            "stakeCurrency": coalesce(summary.get("stakeCurrency"), run_metadata.get("stake_currency"), overview.get("stake_currency"), ""),
            "stakeAmount": coalesce(summary.get("stakeAmount"), run_metadata.get("stake_amount"), overview.get("stake_amount"), ""),
            "maxOpenTrades": to_int(coalesce(summary.get("maxOpenTrades"), run_metadata.get("max_open_trades"), overview.get("max_open_trades"))),
            "bestPair": stringify_key(coalesce(summary.get("bestPair"), run_metadata.get("best_pair"), overview.get("best_pair"), "")),
            "worstPair": stringify_key(coalesce(summary.get("worstPair"), run_metadata.get("worst_pair"), overview.get("worst_pair"), "")),
            "tradingVolume": to_float(coalesce(summary.get("tradingVolume"), overview.get("trading_volume"), summary_metrics.get("total_volume"))),
            "sharpe_ratio": sharpe_ratio,
            "sharpeRatio": sharpe_ratio,
            "cagr": coerce_profit_pct(summary_metrics.get("cagr"), ratio_value=summary_metrics.get("cagr")),
            "calmarRatio": to_float(summary_metrics.get("calmar")),
            "sortinoRatio": to_float(summary_metrics.get("sortino")),
            "sqn": to_float(summary_metrics.get("sqn")),
            "expectancy": to_float(summary_metrics.get("expectancy")),
            "expectancyRatio": to_float(summary_metrics.get("expectancy_ratio")),
            "profitMedian": to_float(summary_metrics.get("profit_median")),
            "avgStakeAmount": to_float(summary_metrics.get("avg_stake_amount")),
            "marketChange": coerce_profit_pct(summary_metrics.get("market_change"), ratio_value=summary_metrics.get("market_change")),
            "bestDayPct": coerce_profit_pct(summary_metrics.get("backtest_best_day"), ratio_value=summary_metrics.get("backtest_best_day")),
            "bestDayAbs": to_float(summary_metrics.get("backtest_best_day_abs")),
            "worstDayPct": coerce_profit_pct(summary_metrics.get("backtest_worst_day"), ratio_value=summary_metrics.get("backtest_worst_day")),
            "worstDayAbs": to_float(summary_metrics.get("backtest_worst_day_abs")),
            "winningDays": to_int(run_metadata.get("winning_days")),
            "losingDays": to_int(run_metadata.get("losing_days")),
            "drawDays": to_int(run_metadata.get("draw_days")),
            "maxConsecutiveWins": to_int(risk_metrics.get("max_consecutive_wins")),
            "maxConsecutiveLosses": to_int(risk_metrics.get("max_consecutive_losses")),
            "maxRelativeDrawdown": drawdown_to_pct(risk_metrics.get("max_relative_drawdown")),
            "drawdownStart": risk_metrics.get("drawdown_start"),
            "drawdownEnd": risk_metrics.get("drawdown_end"),
            "drawdownDuration": risk_metrics.get("drawdown_duration"),
            "tradeCountLong": to_int_or_none(run_metadata.get("trade_count_long")),
            "tradeCountShort": to_int_or_none(run_metadata.get("trade_count_short")),
            "totalProfitLong": to_float(balance_metrics.get("profit_total_long_abs")),
            "totalProfitLongPct": coerce_profit_pct(
                balance_metrics.get("profit_total_long"),
                ratio_value=balance_metrics.get("profit_total_long"),
                abs_value=balance_metrics.get("profit_total_long_abs"),
                starting_balance=starting_balance,
            ),
            "totalProfitShort": to_float(balance_metrics.get("profit_total_short_abs")),
            "totalProfitShortPct": coerce_profit_pct(
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


def normalize_summary_metrics(result: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("summary_metrics") or {})
    normalized = dict(section)
    normalized.update(
        {
            "cagr": coerce_profit_pct(section.get("cagr"), ratio_value=section.get("cagr")),
            "calmar": to_float(section.get("calmar")),
            "sortino": to_float(section.get("sortino")),
            "sharpe": to_float(section.get("sharpe", summary.get("sharpeRatio"))),
            "sqn": to_float(section.get("sqn")),
            "expectancy": to_float(section.get("expectancy")),
            "expectancy_ratio": to_float(section.get("expectancy_ratio")),
            "profit_mean": to_float(section.get("profit_mean")),
            "profit_mean_pct": coerce_profit_pct(section.get("profit_mean_pct"), ratio_value=section.get("profit_mean")),
            "profit_median": to_float(section.get("profit_median")),
            "avg_stake_amount": to_float(section.get("avg_stake_amount")),
            "total_volume": to_float(section.get("total_volume")),
            "market_change": coerce_profit_pct(section.get("market_change"), ratio_value=section.get("market_change")),
            "backtest_best_day": coerce_profit_pct(section.get("backtest_best_day"), ratio_value=section.get("backtest_best_day")),
            "backtest_best_day_abs": to_float(section.get("backtest_best_day_abs")),
            "backtest_worst_day": coerce_profit_pct(section.get("backtest_worst_day"), ratio_value=section.get("backtest_worst_day")),
            "backtest_worst_day_abs": to_float(section.get("backtest_worst_day_abs")),
            "profit_factor": to_float(section.get("profit_factor")),
            "wins": to_int(section.get("wins")),
            "losses": to_int(section.get("losses")),
            "draws": to_int(section.get("draws")),
            "winrate": coerce_rate_pct(section.get("winrate")),
        }
    )
    return normalized


def normalize_balance_metrics(result: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("balance_metrics") or {})
    starting_balance = to_float(coalesce(section.get("starting_balance"), summary.get("startingBalance"), result.get("overview", {}).get("starting_balance"))) or 0.0
    final_balance = to_float(coalesce(section.get("final_balance"), summary.get("finalBalance"), result.get("overview", {}).get("final_balance"))) or 0.0
    normalized = dict(section)
    normalized.update(
        {
            "starting_balance": starting_balance,
            "final_balance": final_balance,
            "dry_run_wallet": to_float(section.get("dry_run_wallet")),
            "profit_total": to_float(section.get("profit_total")),
            "profit_total_abs": to_float(section.get("profit_total_abs")),
            "profit_total_pct": coerce_profit_pct(
                coalesce(section.get("profit_total_pct"), summary.get("totalProfitPct")),
                ratio_value=section.get("profit_total"),
                abs_value=section.get("profit_total_abs"),
                starting_balance=starting_balance,
                final_balance=final_balance,
            ),
            "profit_total_long": to_float(section.get("profit_total_long")),
            "profit_total_long_abs": to_float(section.get("profit_total_long_abs")),
            "profit_total_long_pct": coerce_profit_pct(
                section.get("profit_total_long"),
                ratio_value=section.get("profit_total_long"),
                abs_value=section.get("profit_total_long_abs"),
                starting_balance=starting_balance,
            ),
            "profit_total_short": to_float(section.get("profit_total_short")),
            "profit_total_short_abs": to_float(section.get("profit_total_short_abs")),
            "profit_total_short_pct": coerce_profit_pct(
                section.get("profit_total_short"),
                ratio_value=section.get("profit_total_short"),
                abs_value=section.get("profit_total_short_abs"),
                starting_balance=starting_balance,
            ),
        }
    )
    return normalized


def normalize_run_metadata(result: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("run_metadata") or {})
    normalized = dict(section)
    normalized.update(
        {
            "strategy_name": coalesce(section.get("strategy_name"), result.get("strategy_name"), result.get("strategy")),
            "backtest_start": section.get("backtest_start"),
            "backtest_start_ts": to_float(section.get("backtest_start_ts")),
            "backtest_end": section.get("backtest_end"),
            "backtest_end_ts": to_float(section.get("backtest_end_ts")),
            "backtest_run_start_ts": to_float(section.get("backtest_run_start_ts")),
            "backtest_run_end_ts": to_float(section.get("backtest_run_end_ts")),
            "timeframe": coalesce(section.get("timeframe"), summary.get("timeframe")),
            "timeframe_detail": section.get("timeframe_detail"),
            "timerange": section.get("timerange"),
            "stake_currency": coalesce(section.get("stake_currency"), summary.get("stakeCurrency")),
            "stake_currency_decimals": to_int(section.get("stake_currency_decimals")),
            "stake_amount": coalesce(section.get("stake_amount"), summary.get("stakeAmount")),
            "max_open_trades": to_int(coalesce(section.get("max_open_trades"), summary.get("maxOpenTrades"))),
            "max_open_trades_setting": to_int(section.get("max_open_trades_setting")),
            "trade_count_long": to_int(section.get("trade_count_long")),
            "trade_count_short": to_int(section.get("trade_count_short")),
            "trading_mode": section.get("trading_mode"),
            "margin_mode": section.get("margin_mode"),
            "backtest_days": to_int(section.get("backtest_days")),
            "trades_per_day": to_float(section.get("trades_per_day")),
            "winning_days": to_int(section.get("winning_days")),
            "losing_days": to_int(section.get("losing_days")),
            "draw_days": to_int(section.get("draw_days")),
            "best_pair": stringify_key(section.get("best_pair")),
            "worst_pair": stringify_key(section.get("worst_pair")),
            "avg_duration": section.get("avg_duration"),
            "holding_avg": section.get("holding_avg"),
            "holding_avg_s": to_float(section.get("holding_avg_s")),
            "winner_holding_avg": section.get("winner_holding_avg"),
            "winner_holding_avg_s": to_float(section.get("winner_holding_avg_s")),
            "winner_holding_min": section.get("winner_holding_min"),
            "winner_holding_min_s": to_float(section.get("winner_holding_min_s")),
            "winner_holding_max": section.get("winner_holding_max"),
            "winner_holding_max_s": to_float(section.get("winner_holding_max_s")),
            "loser_holding_avg": section.get("loser_holding_avg"),
            "loser_holding_avg_s": to_float(section.get("loser_holding_avg_s")),
            "loser_holding_min": section.get("loser_holding_min"),
            "loser_holding_min_s": to_float(section.get("loser_holding_min_s")),
            "loser_holding_max": section.get("loser_holding_max"),
            "loser_holding_max_s": to_float(section.get("loser_holding_max_s")),
        }
    )
    return normalized


def normalize_config_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("config_snapshot") or {})
    normalized = dict(section)
    normalized.update(
        {
            "stoploss": coerce_profit_pct(section.get("stoploss"), ratio_value=section.get("stoploss")),
            "minimal_roi": section.get("minimal_roi") if isinstance(section.get("minimal_roi"), dict) else {},
            "trailing_stop": bool(section.get("trailing_stop")) if section.get("trailing_stop") is not None else False,
            "trailing_stop_positive": coerce_profit_pct(section.get("trailing_stop_positive"), ratio_value=section.get("trailing_stop_positive")),
            "trailing_stop_positive_offset": coerce_profit_pct(section.get("trailing_stop_positive_offset"), ratio_value=section.get("trailing_stop_positive_offset")),
            "trailing_only_offset_is_reached": bool(section.get("trailing_only_offset_is_reached")) if section.get("trailing_only_offset_is_reached") is not None else False,
            "use_custom_stoploss": bool(section.get("use_custom_stoploss")) if section.get("use_custom_stoploss") is not None else False,
            "use_exit_signal": bool(section.get("use_exit_signal")) if section.get("use_exit_signal") is not None else False,
            "exit_profit_only": bool(section.get("exit_profit_only")) if section.get("exit_profit_only") is not None else False,
            "exit_profit_offset": coerce_profit_pct(section.get("exit_profit_offset"), ratio_value=section.get("exit_profit_offset")),
            "ignore_roi_if_entry_signal": bool(section.get("ignore_roi_if_entry_signal")) if section.get("ignore_roi_if_entry_signal") is not None else False,
            "enable_protections": bool(section.get("enable_protections")) if section.get("enable_protections") is not None else False,
            "locks": section.get("locks") if isinstance(section.get("locks"), list) else [],
            "pairlist": section.get("pairlist") if isinstance(section.get("pairlist"), list) else [],
            "freqai_identifier": section.get("freqai_identifier"),
            "freqaimodel": section.get("freqaimodel"),
        }
    )
    return normalized


def normalize_raw_artifact(raw_artifact: dict[str, Any] | None) -> dict[str, Any]:
    section = dict(raw_artifact or {})
    return {
        "available": bool(section.get("available")),
        "type": section.get("type"),
        "file_name": section.get("file_name"),
        "file_path": section.get("file_path"),
        "inner_file_name": section.get("inner_file_name"),
        "run_local": bool(section.get("run_local")),
    }


def normalize_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    section = dict(result.get("diagnostics") or {})
    warnings = list(coalesce(section.get("warnings"), result.get("warnings"), []))
    return {
        "rejected_signals": to_int(section.get("rejected_signals")),
        "canceled_entry_orders": to_int(section.get("canceled_entry_orders")),
        "canceled_trade_entries": to_int(section.get("canceled_trade_entries")),
        "replaced_entry_orders": to_int(section.get("replaced_entry_orders")),
        "timedout_entry_orders": to_int(section.get("timedout_entry_orders")),
        "timedout_exit_orders": to_int(section.get("timedout_exit_orders")),
        "locks": section.get("locks") if isinstance(section.get("locks"), list) else [],
        "warnings": warnings,
        "raw_artifact": normalize_raw_artifact(coalesce(section.get("raw_artifact"), result.get("raw_artifact"))),
    }


def collect_integrity_warnings(
    result: dict[str, Any],
    summary: dict[str, Any],
    balance_metrics: dict[str, Any],
    run_metadata: dict[str, Any],
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    warnings: list[str] = []
    raw_summary = dict(result.get("summary") or {})
    raw_balance = dict(result.get("balance_metrics") or {})

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
        if not has_value(value):
            warnings.append(f"Missing metric: {key}")

    starting = to_float(balance_metrics.get("starting_balance"))
    ending = to_float(balance_metrics.get("final_balance"))
    if starting and ending is not None:
        derived_total_pct = ((ending - starting) / starting) * 100.0
        raw_total_pct = to_float(summary.get("totalProfitPct"))
        original_total_pct = coerce_profit_pct(
            coalesce(raw_summary.get("totalProfitPct"), raw_summary.get("profit_total_pct")),
            ratio_value=coalesce(raw_balance.get("profit_total"), result.get("overview", {}).get("profit_total")),
            abs_value=coalesce(raw_balance.get("profit_total_abs"), result.get("overview", {}).get("profit_total_abs")),
            starting_balance=starting,
            final_balance=ending,
        )
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

    profit_mean_pct = coerce_profit_pct(
        coalesce(
            result.get("summary_metrics", {}).get("profit_mean_pct"),
            result.get("summary_metrics", {}).get("profit_mean"),
        ),
        ratio_value=result.get("summary_metrics", {}).get("profit_mean"),
    )
    avg_profit_pct = to_float(summary.get("avgProfitPct"))
    if profit_mean_pct is not None and avg_profit_pct is not None:
        tolerance = max(0.1, abs(profit_mean_pct) * 0.05)
        if abs(avg_profit_pct - profit_mean_pct) > tolerance:
            summary["avgProfitPct"] = profit_mean_pct
            warnings.append("Corrected metric mismatch: summary.avgProfitPct aligned with summary_metrics.profit_mean_pct.")
    elif profit_mean_pct is not None and avg_profit_pct is None:
        summary["avgProfitPct"] = profit_mean_pct

    if starting:
        for side in ("long", "short"):
            abs_key = f"profit_total_{side}_abs"
            pct_key = f"profit_total_{side}_pct"
            abs_value = to_float(balance_metrics.get(abs_key))
            pct_value = to_float(balance_metrics.get(pct_key))
            original_pct = coerce_profit_pct(
                raw_balance.get(pct_key),
                ratio_value=raw_balance.get(f"profit_total_{side}"),
                abs_value=raw_balance.get(abs_key),
                starting_balance=starting,
            )
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

    if to_int_or_none(run_metadata.get("trade_count_short")) is None:
        warnings.append("Missing metric: run_metadata.trade_count_short")

    return warnings, summary, balance_metrics


__all__ = [
    "build_summary",
    "coalesce",
    "coerce_profit_pct",
    "coerce_rate_pct",
    "collect_integrity_warnings",
    "drawdown_to_pct",
    "has_value",
    "merge_unique_warnings",
    "normalize_balance_metrics",
    "normalize_config_snapshot",
    "normalize_diagnostics",
    "normalize_raw_artifact",
    "normalize_run_metadata",
    "normalize_summary_metrics",
    "stringify_key",
    "to_float",
    "to_int",
    "to_int_or_none",
]
