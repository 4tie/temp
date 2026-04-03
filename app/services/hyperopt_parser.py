import json
import re
from pathlib import Path
from typing import Any, Optional

from app.core.config import HYPEROPT_RESULTS_DIR


def parse_hyperopt_results(run_dir: Path, strategy: str) -> dict[str, Any]:
    epochs = _load_epochs(run_dir, strategy)
    if not epochs:
        return {"error": "No hyperopt results found", "epochs": [], "best": None, "total_epochs": 0}

    best = _find_best(epochs)

    return {
        "epochs": epochs,
        "best": best,
        "total_epochs": len(epochs),
    }


def _load_epochs(run_dir: Path, strategy: str) -> list[dict[str, Any]]:
    fthypt_files = list(run_dir.glob("*.fthypt"))

    if not fthypt_files:
        global_dir = HYPEROPT_RESULTS_DIR
        if global_dir.exists():
            fthypt_files = list(global_dir.glob(f"strategy_{strategy}_*.fthypt"))

    if not fthypt_files:
        if HYPEROPT_RESULTS_DIR.exists():
            fthypt_files = list(HYPEROPT_RESULTS_DIR.glob("*.fthypt"))

    if not fthypt_files:
        return []

    latest = sorted(fthypt_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    return _parse_fthypt(latest)


def _parse_fthypt(fthypt_path: Path) -> list[dict[str, Any]]:
    epochs = []
    try:
        with open(fthypt_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    epoch = _normalize_epoch(raw, line_num)
                    if epoch:
                        epochs.append(epoch)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return epochs


def _normalize_epoch(raw: dict, epoch_num: int) -> Optional[dict[str, Any]]:
    params_details = raw.get("params_details", {})
    params_not_default = raw.get("params_not_default", {})

    all_params = {}
    for space_params in params_details.values():
        if isinstance(space_params, dict):
            all_params.update(space_params)

    results = raw.get("results_metrics", raw.get("results", {}))
    if not results:
        return None

    profit = results.get("profit_total", 0) or 0
    profit_pct = profit * 100

    trades = results.get("total_trades", results.get("trade_count", 0)) or 0
    drawdown = results.get("max_drawdown", 0) or results.get("max_drawdown_account", 0) or 0
    drawdown_pct = drawdown * 100
    avg_profit = results.get("profit_mean", 0) or 0
    avg_profit_pct = avg_profit * 100
    duration = results.get("holding_avg", results.get("duration_avg", ""))
    loss = raw.get("loss", 0)

    is_best = raw.get("is_best", False)
    current_epoch = raw.get("current_epoch", epoch_num)

    return {
        "epoch": current_epoch,
        "trades": trades,
        "profit_pct": round(profit_pct, 4),
        "profit_abs": results.get("profit_total_abs", 0) or 0,
        "avg_profit_pct": round(avg_profit_pct, 4),
        "drawdown_pct": round(drawdown_pct, 4),
        "avg_duration": str(duration) if duration else "",
        "loss": round(loss, 6) if loss else 0,
        "is_best": is_best,
        "params": all_params,
        "params_not_default": params_not_default,
    }


def _find_best(epochs: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    best_epochs = [e for e in epochs if e.get("is_best")]
    if best_epochs:
        return best_epochs[-1]

    valid = [e for e in epochs if e.get("trades", 0) > 0]
    if not valid:
        return None
    return min(valid, key=lambda e: e.get("loss", float("inf")))


def load_params_file(strategy: str) -> Optional[dict[str, Any]]:
    from app.core.config import STRATEGIES_DIR
    _validate_strategy_name(strategy)
    params_file = STRATEGIES_DIR / f"{strategy}.params"
    if not params_file.exists():
        return None
    try:
        return json.loads(params_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


_SAFE_STRATEGY_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _validate_strategy_name(strategy: str) -> str:
    if not strategy or not _SAFE_STRATEGY_RE.match(strategy):
        raise ValueError(f"Invalid strategy name: {strategy}")
    return strategy


_SPACE_PREFIXES = {
    "buy_": "buy",
    "sell_": "sell",
    "roi_": "roi",
    "stoploss_": "stoploss",
    "trailing_": "trailing",
    "protection_": "protection",
    "protect_": "protection",
}


def save_params_file(strategy: str, params: dict[str, Any], spaces: list[str] | None = None):
    from app.core.config import STRATEGIES_DIR
    _validate_strategy_name(strategy)
    params_file = STRATEGIES_DIR / f"{strategy}.params"

    resolved = params_file.resolve()
    if not str(resolved).startswith(str(STRATEGIES_DIR.resolve())):
        raise ValueError("Path traversal detected")

    existing = {}
    if params_file.exists():
        try:
            existing = json.loads(params_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    _VALID_SPACES = {"buy", "sell", "roi", "stoploss", "trailing", "protection", "other"}
    allowed_spaces: set[str] | None = None
    if spaces is not None:
        allowed_spaces = {s.lower() for s in spaces if s.lower() in _VALID_SPACES}

    categorized: dict[str, dict[str, Any]] = {}
    uncategorized: dict[str, Any] = {}

    for key, value in params.items():
        space = None
        for prefix, space_name in _SPACE_PREFIXES.items():
            if key.startswith(prefix):
                space = space_name
                break
        if space:
            if allowed_spaces is not None and space not in allowed_spaces:
                continue
            categorized.setdefault(f"params_{space}", {})[key] = value
        else:
            if allowed_spaces is not None and "other" not in allowed_spaces:
                continue
            uncategorized[key] = value

    for section, section_params in categorized.items():
        if section not in existing:
            existing[section] = {}
        existing[section].update(section_params)

    if uncategorized:
        if "params" not in existing:
            existing["params"] = {}
        existing["params"].update(uncategorized)

    params_file.write_text(json.dumps(existing, indent=2, default=str))
