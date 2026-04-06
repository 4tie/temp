from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Optional

from app.core.config import HYPEROPT_RESULTS_DIR
from app.services.runs.run_metadata_service import utcnow_iso


def build_hyperopt_meta(
    *,
    run_id: str,
    strategy: str,
    pairs: list[str],
    timeframe: str,
    timerange: Optional[str],
    epochs: int,
    spaces: list[str],
    loss_function: str,
    jobs: int,
    min_trades: int,
    early_stop: Optional[int],
    dry_run_wallet: float,
    max_open_trades: int,
    stake_amount: str,
    exchange: str,
    command: list[str],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "type": "hyperopt",
        "strategy": strategy,
        "pairs": pairs,
        "timeframe": timeframe,
        "timerange": timerange,
        "epochs": epochs,
        "spaces": spaces,
        "loss_function": loss_function,
        "jobs": jobs,
        "min_trades": min_trades,
        "early_stop": early_stop,
        "dry_run_wallet": dry_run_wallet,
        "max_open_trades": max_open_trades,
        "stake_amount": stake_amount,
        "exchange": exchange,
        "command": command,
        "status": "running",
        "started_at": utcnow_iso(),
        "completed_at": None,
    }


def copy_hyperopt_results(run_dir: Path, strategy: str) -> None:
    last_file = HYPEROPT_RESULTS_DIR / ".last_hyperopt.json"
    if last_file.exists():
        try:
            ref = json.loads(last_file.read_text())
            latest_name = ref.get("latest_hyperopt", "")
            if latest_name:
                src = HYPEROPT_RESULTS_DIR / latest_name
                if src.exists():
                    shutil.copy2(src, run_dir / src.name)
                    return
        except (json.JSONDecodeError, OSError):
            pass

    if HYPEROPT_RESULTS_DIR.exists():
        fthypt_files = list(HYPEROPT_RESULTS_DIR.glob(f"strategy_{strategy}_*.fthypt"))
        if not fthypt_files:
            fthypt_files = list(HYPEROPT_RESULTS_DIR.glob("*.fthypt"))
        if fthypt_files:
            latest = sorted(fthypt_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            shutil.copy2(latest, run_dir / latest.name)


def load_hyperopt_run_results(run_dir: Path, strategy: str) -> dict[str, Any]:
    copy_hyperopt_results(run_dir, strategy)

    from app.services.hyperopt_parser import load_params_file, parse_hyperopt_results

    results = parse_hyperopt_results(run_dir, strategy)
    exported_params = load_params_file(strategy)
    if exported_params:
        results["exported_params"] = exported_params
    return results
