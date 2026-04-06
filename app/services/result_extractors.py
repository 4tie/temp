from __future__ import annotations

from typing import Any


def extract_section(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: data.get(key) for key in keys if key in data}


def extract_overview(data: dict[str, Any]) -> dict[str, Any]:
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
        "best_pair": row_key_to_string(data.get("best_pair", {}).get("key", data.get("best_pair", ""))),
        "worst_pair": row_key_to_string(data.get("worst_pair", {}).get("key", data.get("worst_pair", ""))),
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


def extract_trades(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_trades = data.get("trades", [])
    trades = []
    for trade in raw_trades:
        if not isinstance(trade, dict):
            continue
        profit_ratio = trade.get("profit_ratio")
        if profit_ratio is not None:
            profit_pct = profit_ratio * 100
        else:
            profit_pct = trade.get("profit_percent", trade.get("profit_pct", 0))

        orders = trade.get("orders")
        trade_data = {
            "pair": trade.get("pair", ""),
            "profit_pct": profit_pct,
            "profit_abs": trade.get("profit_abs", 0),
            "open_date": trade.get("open_date", ""),
            "close_date": trade.get("close_date", ""),
            "open_timestamp": trade.get("open_timestamp"),
            "close_timestamp": trade.get("close_timestamp"),
            "duration": trade.get("trade_duration", trade.get("duration", "")),
            "is_open": trade.get("is_open", False),
            "is_short": trade.get("is_short", False),
            "open_rate": trade.get("open_rate", 0),
            "close_rate": trade.get("close_rate", 0),
            "stake_amount": trade.get("stake_amount", 0),
            "amount": trade.get("amount"),
            "leverage": trade.get("leverage"),
            "enter_tag": trade.get("enter_tag", ""),
            "exit_reason": trade.get("exit_reason", trade.get("sell_reason", "")),
            "direction": trade.get("direction", trade.get("trade_direction", "short" if trade.get("is_short") else "long")),
            "mae": trade.get("min_rate", trade.get("mae", 0)),
            "mfe": trade.get("max_rate", trade.get("mfe", 0)),
            "fee_open": trade.get("fee_open"),
            "fee_close": trade.get("fee_close"),
            "funding_fees": trade.get("funding_fees"),
            "initial_stop_loss_abs": trade.get("initial_stop_loss_abs"),
            "initial_stop_loss_ratio": trade.get("initial_stop_loss_ratio"),
            "stop_loss_abs": trade.get("stop_loss_abs"),
            "stop_loss_ratio": trade.get("stop_loss_ratio"),
            "weekday": trade.get("weekday"),
            "orders": orders if isinstance(orders, list) else [],
        }
        trades.append(trade_data)
    return trades


def extract_per_pair(data: dict[str, Any]) -> list[dict[str, Any]]:
    results = data.get("results_per_pair", [])
    pairs = []
    for row in results:
        if not isinstance(row, dict):
            continue
        profit_mean_pct = row.get("profit_mean_pct")
        if profit_mean_pct is None:
            profit_mean = row.get("profit_mean", 0)
            profit_mean_pct = (profit_mean * 100) if profit_mean else 0

        profit_sum_pct = row.get("profit_sum_pct")
        if profit_sum_pct is None:
            profit_total_pct = row.get("profit_total_pct")
            if profit_total_pct is not None:
                profit_sum_pct = profit_total_pct
            else:
                profit_total = row.get("profit_total", 0)
                profit_sum_pct = (profit_total * 100) if profit_total else 0

        pairs.append(
            {
                "pair": row_key_to_string(row.get("key", row.get("pair", ""))),
                "key": row.get("key", row.get("pair", "")),
                "trades": row.get("trades", 0),
                "profit_mean": row.get("profit_mean"),
                "profit_mean_pct": profit_mean_pct,
                "profit_sum_pct": profit_sum_pct,
                "profit_total": row.get("profit_total"),
                "profit_total_abs": row.get("profit_total_abs", 0),
                "profit_factor": row.get("profit_factor", 0),
                "max_drawdown": row.get("max_drawdown", row.get("max_drawdown_account", 0)),
                "max_drawdown_abs": row.get("max_drawdown_abs"),
                "wins": row.get("wins", 0),
                "losses": row.get("losses", 0),
                "draws": row.get("draws", 0),
                "winrate": row.get("winrate"),
                "cagr": row.get("cagr"),
                "expectancy": row.get("expectancy"),
                "expectancy_ratio": row.get("expectancy_ratio"),
                "sortino": row.get("sortino"),
                "sharpe": row.get("sharpe"),
                "calmar": row.get("calmar"),
                "sqn": row.get("sqn"),
                "duration_avg": row.get("duration_avg"),
            }
        )
    return pairs


def extract_daily_profit(data: dict[str, Any]) -> list[dict[str, Any]]:
    daily_stats = data.get("daily_profit", [])
    if not daily_stats:
        return []

    daily_profit: list[dict[str, Any]] = []
    cumulative = 0.0
    for entry in daily_stats:
        if isinstance(entry, dict):
            date = entry.get("date", "")
            profit = entry.get("abs_profit", entry.get("profit_abs", 0))
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            date = entry[0]
            profit = entry[1]
        else:
            continue
        cumulative += float(profit or 0)
        daily_profit.append({"date": date, "profit": profit, "cumulative": cumulative})
    return daily_profit


def extract_equity_curve(data: dict[str, Any]) -> list[dict[str, Any]]:
    return list(extract_daily_profit(data))


def extract_grouped_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = dict(row)
        normalized["label"] = row_key_to_string(row.get("key"))
        normalized_rows.append(normalized)
    return normalized_rows


def extract_periodic_breakdown(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    periodic = data.get("periodic_breakdown")
    if not isinstance(periodic, dict):
        return {}

    extracted: dict[str, list[dict[str, Any]]] = {}
    for key, rows in periodic.items():
        if not isinstance(rows, list):
            continue
        normalized_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized_rows.append(dict(row))
        extracted[str(key)] = normalized_rows
    return extracted


def row_key_to_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " -> ".join(str(item) for item in value if item not in (None, ""))
    return str(value)
