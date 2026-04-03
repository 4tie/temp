import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import BACKTEST_RESULTS_DIR, PRESETS_FILE, LAST_CONFIG_FILE

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _validate_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise ValueError(f"Invalid ID: {value!r}")
    resolved = (BACKTEST_RESULTS_DIR / value).resolve()
    if not str(resolved).startswith(str(BACKTEST_RESULTS_DIR.resolve())):
        raise ValueError(f"Path traversal detected: {value!r}")
    return value


def save_run_meta(run_id: str, meta: dict[str, Any]):
    _validate_id(run_id)
    run_dir = BACKTEST_RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta_file = run_dir / "meta.json"
    meta_file.write_text(json.dumps(meta, indent=2, default=str))


def load_run_meta(run_id: str) -> Optional[dict[str, Any]]:
    _validate_id(run_id)
    meta_file = BACKTEST_RESULTS_DIR / run_id / "meta.json"
    if not meta_file.exists():
        return None
    try:
        return json.loads(meta_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_run_results(run_id: str, results: dict[str, Any]):
    _validate_id(run_id)
    run_dir = BACKTEST_RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_file = run_dir / "parsed_results.json"
    results_file.write_text(json.dumps(results, indent=2, default=str))


def load_run_results(run_id: str) -> Optional[dict[str, Any]]:
    _validate_id(run_id)
    results_file = BACKTEST_RESULTS_DIR / run_id / "parsed_results.json"
    if not results_file.exists():
        return None
    try:
        return json.loads(results_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_run_logs(run_id: str, logs: list[str]):
    _validate_id(run_id)
    run_dir = BACKTEST_RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_file = run_dir / "logs.txt"
    log_file.write_text("\n".join(logs))


def list_runs() -> list[dict[str, Any]]:
    runs = []
    if not BACKTEST_RESULTS_DIR.exists():
        return runs

    for d in sorted(BACKTEST_RESULTS_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        meta = load_run_meta(d.name)
        if meta:
            meta["run_id"] = d.name
            has_results = (d / "parsed_results.json").exists()
            meta["has_results"] = has_results
            runs.append(meta)
        else:
            runs.append({
                "run_id": d.name,
                "status": "unknown",
                "has_results": (d / "parsed_results.json").exists(),
            })
    return runs


def delete_run(run_id: str) -> bool:
    _validate_id(run_id)
    run_dir = BACKTEST_RESULTS_DIR / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
        return True
    return False


def get_run_dir(run_id: str) -> Path:
    _validate_id(run_id)
    d = BACKTEST_RESULTS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_presets() -> dict[str, Any]:
    if not PRESETS_FILE.exists():
        return {}
    try:
        return json.loads(PRESETS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_presets(presets: dict[str, Any]):
    PRESETS_FILE.write_text(json.dumps(presets, indent=2, default=str))


def save_preset(name: str, config: dict[str, Any]):
    presets = load_presets()
    presets[name] = {
        "config": config,
        "saved_at": datetime.utcnow().isoformat(),
    }
    save_presets(presets)


def delete_preset(name: str) -> bool:
    presets = load_presets()
    if name in presets:
        del presets[name]
        save_presets(presets)
        return True
    return False


def save_last_config(config: dict[str, Any]):
    LAST_CONFIG_FILE.write_text(json.dumps(config, indent=2, default=str))


def load_last_config() -> Optional[dict[str, Any]]:
    if not LAST_CONFIG_FILE.exists():
        return None
    try:
        return json.loads(LAST_CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None
