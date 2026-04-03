import json
import zipfile
from pathlib import Path
from typing import Any, Optional

from app.core.config import BACKTEST_RESULTS_DIR


def parse_backtest_results(result_dir: Path) -> dict[str, Any]:
    raw = _load_result_data(result_dir)
    if raw is None:
        return {"error": "No result file found", "overview": {}, "trades": [], "per_pair": [], "warnings": []}

    strategy_key = next(iter(raw.get("strategy", {})), None)
    if not strategy_key:
        strategy_key = next(iter(raw.get("strategy_comparison", [])), None)

    if strategy_key and "strategy" in raw:
        strat_data = raw["strategy"][strategy_key]
    elif isinstance(raw, dict) and "trades" in raw:
        strat_data = raw
    else:
        return {"error": "Unrecognized result format", "overview": {}, "trades": [], "per_pair": [], "warnings": [], "raw_keys": list(raw.keys())}

    overview = _extract_overview(strat_data)
    trades = _extract_trades(strat_data)
    per_pair = _extract_per_pair(strat_data)
    equity_curve = _extract_equity_curve(strat_data)
    warnings = strat_data.get("backtest_warnings", [])

    return {
        "overview": overview,
        "trades": trades,
        "per_pair": per_pair,
        "equity_curve": equity_curve,
        "warnings": warnings,
        "strategy_name": strategy_key,
    }


def _load_result_data(result_dir: Path) -> Optional[dict]:
    for name in ["result.json", "backtest-result.json"]:
        f = result_dir / name
        if f.exists():
            try:
                return json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue

    json_files = list(result_dir.glob("*.json"))
    meta_file = result_dir / "meta.json"
    parsed_file = result_dir / "parsed_results.json"
    json_files = [f for f in json_files if f not in (meta_file, parsed_file) and not f.name.endswith(".meta.json")]
    if json_files:
        latest = sorted(json_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
        try:
            return json.loads(latest.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    zip_files = list(result_dir.glob("*.zip"))
    if zip_files:
        latest_zip = sorted(zip_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
        data = _load_from_zip(latest_zip)
        if data:
            return data

    last_result_file = BACKTEST_RESULTS_DIR / ".last_result.json"
    if last_result_file.exists():
        try:
            last_ref = json.loads(last_result_file.read_text())
            latest_name = last_ref.get("latest_backtest", "")
            if latest_name:
                latest_path = BACKTEST_RESULTS_DIR / latest_name
                if latest_path.exists():
                    if latest_path.suffix == ".zip":
                        return _load_from_zip(latest_path)
                    else:
                        return json.loads(latest_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    return None


def _load_from_zip(zip_path: Path) -> Optional[dict]:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".json") and "_config" not in name:
                    data = json.loads(zf.read(name))
                    if "strategy" in data or "trades" in data:
                        return data
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError):
        pass
    return None


def _extract_overview(data: dict) -> dict[str, Any]:
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
        "avg_profit_pct": data.get("avg_profit_pct", 0),
        "avg_duration": data.get("avg_duration", ""),
        "best_pair": data.get("best_pair", {}).get("key", ""),
        "worst_pair": data.get("worst_pair", {}).get("key", ""),
        "trading_volume": data.get("trading_volume", 0),
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


def _calc_win_rate(data: dict) -> float:
    total = data.get("total_trades", 0)
    if total == 0:
        return 0.0
    wins = data.get("wins", 0)
    return round((wins / total) * 100, 2)


def _extract_trades(data: dict) -> list[dict[str, Any]]:
    raw_trades = data.get("trades", [])
    trades = []
    for t in raw_trades:
        profit_ratio = t.get("profit_ratio", None)
        if profit_ratio is not None:
            profit_pct = profit_ratio * 100
        else:
            profit_pct = t.get("profit_percent", 0)

        trades.append({
            "pair": t.get("pair", ""),
            "profit_pct": profit_pct,
            "profit_abs": t.get("profit_abs", 0),
            "open_date": t.get("open_date", ""),
            "close_date": t.get("close_date", ""),
            "duration": t.get("trade_duration", ""),
            "is_open": t.get("is_open", False),
            "open_rate": t.get("open_rate", 0),
            "close_rate": t.get("close_rate", 0),
            "stake_amount": t.get("stake_amount", 0),
            "exit_reason": t.get("exit_reason", t.get("sell_reason", "")),
            "direction": t.get("direction", t.get("trade_direction", "long")),
            "mae": t.get("min_rate", 0),
            "mfe": t.get("max_rate", 0),
        })
    return trades


def _extract_per_pair(data: dict) -> list[dict[str, Any]]:
    results = data.get("results_per_pair", [])
    pairs = []
    for r in results:
        profit_mean_pct = r.get("profit_mean_pct")
        if profit_mean_pct is None:
            profit_mean = r.get("profit_mean", 0)
            profit_mean_pct = (profit_mean * 100) if profit_mean else 0

        profit_sum_pct = r.get("profit_sum_pct")
        if profit_sum_pct is None:
            profit_total_pct = r.get("profit_total_pct")
            if profit_total_pct is not None:
                profit_sum_pct = profit_total_pct
            else:
                profit_total = r.get("profit_total", 0)
                profit_sum_pct = (profit_total * 100) if profit_total else 0

        max_dd = r.get("max_drawdown")
        if max_dd is None:
            max_dd = r.get("max_drawdown_account", 0) or 0

        pairs.append({
            "pair": r.get("key", ""),
            "trades": r.get("trades", 0),
            "profit_mean_pct": profit_mean_pct,
            "profit_sum_pct": profit_sum_pct,
            "profit_total_abs": r.get("profit_total_abs", 0),
            "profit_factor": r.get("profit_factor", 0),
            "max_drawdown": max_dd,
            "wins": r.get("wins", 0),
            "losses": r.get("losses", 0),
            "draws": r.get("draws", 0),
        })
    return pairs


def _extract_equity_curve(data: dict) -> list[dict[str, Any]]:
    daily_stats = data.get("daily_profit", [])
    if not daily_stats:
        return []

    equity = []
    cumulative = 0.0
    for entry in daily_stats:
        if isinstance(entry, dict):
            date = entry.get("date", "")
            profit = entry.get("abs_profit", 0)
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            date = entry[0]
            profit = entry[1]
        else:
            continue
        cumulative += profit
        equity.append({"date": date, "profit": profit, "cumulative": cumulative})
    return equity
