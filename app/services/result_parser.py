from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


_SUMMARY_METRIC_KEYS = [
    "cagr",
    "calmar",
    "sortino",
    "sharpe",
    "sqn",
    "expectancy",
    "expectancy_ratio",
    "profit_mean",
    "profit_median",
    "avg_stake_amount",
    "total_volume",
    "market_change",
    "backtest_best_day",
    "backtest_best_day_abs",
    "backtest_worst_day",
    "backtest_worst_day_abs",
    "profit_factor",
    "wins",
    "losses",
    "draws",
    "winrate",
]

_BALANCE_METRIC_KEYS = [
    "starting_balance",
    "final_balance",
    "dry_run_wallet",
    "profit_total",
    "profit_total_abs",
    "profit_total_long",
    "profit_total_long_abs",
    "profit_total_short",
    "profit_total_short_abs",
]

_RISK_METRIC_KEYS = [
    "max_drawdown",
    "max_drawdown_abs",
    "max_drawdown_account",
    "max_relative_drawdown",
    "drawdown_start",
    "drawdown_start_ts",
    "drawdown_end",
    "drawdown_end_ts",
    "drawdown_duration",
    "drawdown_duration_s",
    "max_drawdown_high",
    "max_drawdown_low",
    "max_consecutive_wins",
    "max_consecutive_losses",
]

_RUN_METADATA_KEYS = [
    "strategy_name",
    "backtest_start",
    "backtest_start_ts",
    "backtest_end",
    "backtest_end_ts",
    "backtest_run_start_ts",
    "backtest_run_end_ts",
    "timeframe",
    "timeframe_detail",
    "timerange",
    "stake_currency",
    "stake_currency_decimals",
    "stake_amount",
    "max_open_trades",
    "max_open_trades_setting",
    "trade_count_long",
    "trade_count_short",
    "trading_mode",
    "margin_mode",
    "backtest_days",
    "trades_per_day",
    "winning_days",
    "losing_days",
    "draw_days",
    "best_pair",
    "worst_pair",
    "avg_duration",
    "holding_avg",
    "holding_avg_s",
    "winner_holding_avg",
    "winner_holding_avg_s",
    "winner_holding_min",
    "winner_holding_min_s",
    "winner_holding_max",
    "winner_holding_max_s",
    "loser_holding_avg",
    "loser_holding_avg_s",
    "loser_holding_min",
    "loser_holding_min_s",
    "loser_holding_max",
    "loser_holding_max_s",
]

_CONFIG_SNAPSHOT_KEYS = [
    "stoploss",
    "minimal_roi",
    "trailing_stop",
    "trailing_stop_positive",
    "trailing_stop_positive_offset",
    "trailing_only_offset_is_reached",
    "use_custom_stoploss",
    "use_exit_signal",
    "exit_profit_only",
    "exit_profit_offset",
    "ignore_roi_if_entry_signal",
    "enable_protections",
    "locks",
    "pairlist",
    "freqai_identifier",
    "freqaimodel",
]

_DIAGNOSTIC_KEYS = [
    "rejected_signals",
    "canceled_entry_orders",
    "canceled_trade_entries",
    "replaced_entry_orders",
    "timedout_entry_orders",
    "timedout_exit_orders",
]


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


def parse_backtest_results(result_dir: Path) -> dict[str, Any]:
    bundle = load_backtest_result_payload(result_dir)
    if bundle is None:
        return empty_backtest_result("No result file found")

    raw_payload = bundle["raw_payload"]
    strategy_key = bundle["strategy_name"]
    strat_data = bundle["strategy_data"]
    if not isinstance(strat_data, dict):
        return empty_backtest_result(
            "Unrecognized result format",
            raw_keys=sorted(raw_payload.keys()) if isinstance(raw_payload, dict) else [],
        )

    warnings = list(strat_data.get("backtest_warnings") or [])

    return {
        "overview": _extract_overview(strat_data),
        "summary_metrics": _extract_section(strat_data, _SUMMARY_METRIC_KEYS),
        "balance_metrics": _extract_section(strat_data, _BALANCE_METRIC_KEYS),
        "risk_metrics": _extract_section(strat_data, _RISK_METRIC_KEYS),
        "run_metadata": _extract_section(strat_data, _RUN_METADATA_KEYS),
        "config_snapshot": _extract_section(strat_data, _CONFIG_SNAPSHOT_KEYS),
        "diagnostics": {
            **_extract_section(strat_data, _DIAGNOSTIC_KEYS),
            "locks": strat_data.get("locks") or [],
            "warnings": warnings,
            "raw_artifact": bundle["artifact"],
        },
        "trades": _extract_trades(strat_data),
        "per_pair": _extract_per_pair(strat_data),
        "equity_curve": _extract_equity_curve(strat_data),
        "daily_profit": _extract_daily_profit(strat_data),
        "exit_reason_summary": _extract_grouped_rows(strat_data.get("exit_reason_summary")),
        "results_per_enter_tag": _extract_grouped_rows(strat_data.get("results_per_enter_tag")),
        "mix_tag_stats": _extract_grouped_rows(strat_data.get("mix_tag_stats")),
        "left_open_trades": _extract_grouped_rows(strat_data.get("left_open_trades")),
        "periodic_breakdown": _extract_periodic_breakdown(strat_data),
        "warnings": warnings,
        "strategy_name": strategy_key or strat_data.get("strategy_name"),
        "raw_artifact": bundle["artifact"],
    }


def load_backtest_result_payload(result_dir: Path) -> dict[str, Any] | None:
    artifact_path = _find_local_result_artifact(result_dir)
    if artifact_path is None:
        return None

    inner_name: str | None = None
    if artifact_path.suffix.lower() == ".zip":
        loaded = _load_from_zip(artifact_path)
        if loaded is None:
            return None
        raw_payload, inner_name = loaded
        artifact_type = "zip"
    else:
        try:
            raw_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        if isinstance(raw_payload, dict):
            latest = raw_payload.get("latest_backtest")
            if isinstance(latest, str) and latest:
                candidate = result_dir / latest
                if candidate.exists() and candidate.is_file():
                    if candidate.suffix.lower() == ".zip":
                        loaded = _load_from_zip(candidate)
                        if loaded is None:
                            return None
                        raw_payload, inner_name = loaded
                        artifact_path = candidate
                        artifact_type = "zip"
                    elif candidate.suffix.lower() == ".json":
                        try:
                            raw_payload = json.loads(candidate.read_text(encoding="utf-8"))
                        except (json.JSONDecodeError, OSError):
                            return None
                        artifact_path = candidate
                        artifact_type = "json"
                    else:
                        artifact_type = "json"
                else:
                    artifact_type = "json"
            else:
                artifact_type = "json"
        else:
            artifact_type = "json"

    strategy_name, strategy_data = _resolve_strategy_payload(raw_payload)
    return {
        "raw_payload": raw_payload,
        "strategy_name": strategy_name,
        "strategy_data": strategy_data,
        "artifact": {
            "available": True,
            "type": artifact_type,
            "file_name": artifact_path.name,
            "file_path": str(artifact_path),
            "inner_file_name": inner_name,
            "run_local": artifact_path.parent.resolve() == result_dir.resolve(),
        },
    }


def find_run_local_result_artifact(result_dir: Path) -> dict[str, Any]:
    bundle = load_backtest_result_payload(result_dir)
    if bundle is None:
        return {"available": False}
    return dict(bundle["artifact"])


def _find_local_result_artifact(result_dir: Path) -> Path | None:
    for name in ("result.json", "backtest-result.json"):
        candidate = result_dir / name
        if candidate.exists():
            return candidate

    meta_file = result_dir / "meta.json"
    parsed_file = result_dir / "parsed_results.json"
    json_files = [
        path
        for path in result_dir.glob("*.json")
        if path not in (meta_file, parsed_file) and not path.name.endswith(".meta.json")
    ]
    if json_files:
        return sorted(json_files, key=lambda path: path.stat().st_mtime, reverse=True)[0]

    zip_files = list(result_dir.glob("*.zip"))
    if zip_files:
        return sorted(zip_files, key=lambda path: path.stat().st_mtime, reverse=True)[0]

    return None


def _load_from_zip(zip_path: Path) -> tuple[dict[str, Any], str | None] | None:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if not name.endswith(".json") or "_config" in name:
                    continue
                data = json.loads(zf.read(name))
                strategy_name, strategy_data = _resolve_strategy_payload(data)
                if strategy_data is not None:
                    return data, name
                if strategy_name is not None:
                    return data, name
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError):
        return None
    return None


def _resolve_strategy_payload(raw: Any) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(raw, dict):
        return None, None

    wrapped = raw.get("latest_backtest")
    if isinstance(wrapped, str) and wrapped:
        try:
            decoded = json.loads(wrapped)
            if isinstance(decoded, dict) and decoded:
                wrapped = decoded
        except (json.JSONDecodeError, TypeError):
            pass

    if isinstance(wrapped, dict) and wrapped:
        raw = wrapped

    strategy_block = raw.get("strategy")
    if isinstance(strategy_block, dict) and strategy_block:
        strategy_name = next(iter(strategy_block))
        strategy_data = strategy_block.get(strategy_name)
        if isinstance(strategy_data, dict):
            return strategy_name, strategy_data

    if isinstance(raw.get("trades"), list):
        strategy_name = raw.get("strategy_name")
        return strategy_name if isinstance(strategy_name, str) else None, raw

    strategy_comparison = raw.get("strategy_comparison")
    if isinstance(strategy_comparison, list) and strategy_comparison:
        first = strategy_comparison[0]
        if isinstance(first, dict):
            strategy_name = first.get("key")
            return strategy_name if isinstance(strategy_name, str) else None, first

    return None, None


def _extract_section(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: data.get(key) for key in keys if key in data}


def _extract_overview(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_trades": data.get("total_trades", 0),
        "profit_total": data.get("profit_total", 0),
        "profit_total_abs": data.get("profit_total_abs", 0),
        "profit_percent": round(data.get("profit_total", 0) * 100, 4),
        "profit_factor": data.get("profit_factor", 0),
        "win_rate": _calc_win_rate(data),
        "max_drawdown": data.get("max_drawdown", 0) or data.get("max_drawdown_account", 0) or 0,
        "max_drawdown_abs": data.get("max_drawdown_abs", 0) or 0,
        "max_drawdown_account": data.get("max_drawdown_account", 0) or 0,
        "avg_profit_pct": data.get("avg_profit_pct", data.get("profit_mean_pct")),
        "avg_duration": data.get("avg_duration", ""),
        "best_pair": _row_key_to_string(data.get("best_pair", {}).get("key", data.get("best_pair", ""))),
        "worst_pair": _row_key_to_string(data.get("worst_pair", {}).get("key", data.get("worst_pair", ""))),
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


def _calc_win_rate(data: dict[str, Any]) -> float:
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


def _extract_trades(data: dict[str, Any]) -> list[dict[str, Any]]:
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


def _extract_per_pair(data: dict[str, Any]) -> list[dict[str, Any]]:
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
                "pair": _row_key_to_string(row.get("key", row.get("pair", ""))),
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


def _extract_daily_profit(data: dict[str, Any]) -> list[dict[str, Any]]:
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


def _extract_equity_curve(data: dict[str, Any]) -> list[dict[str, Any]]:
    return list(_extract_daily_profit(data))


def _extract_grouped_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = dict(row)
        normalized["label"] = _row_key_to_string(row.get("key"))
        normalized_rows.append(normalized)
    return normalized_rows


def _extract_periodic_breakdown(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
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


def _row_key_to_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " -> ".join(str(item) for item in value if item not in (None, ""))
    return str(value)
