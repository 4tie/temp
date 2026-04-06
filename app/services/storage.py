"""
Domain storage for backtest runs and presets.

This module is the source of truth for backtest result persistence and retrieval.
Generic JSON read/write helpers live in app.core.json_io.
"""

import json
import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import (
    BACKTEST_RESULTS_DIR,
    LAST_CONFIG_FILE,
    PARSED_RESULTS_FILENAME,
    PRESETS_FILE,
    RAW_ARTIFACT_META_SUFFIX,
    RUN_LOGS_FILENAME,
    RUN_META_FILENAME,
)
from app.services.results.raw_loader import load_backtest_result_payload
from app.services.results.result_service import normalize_backtest_result, parse_backtest_results
from app.services.results.metric_registry import build_metric_snapshot

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_SAFE_FOLDER_RE = re.compile(r"[^A-Za-z0-9_\-]+")
_VERSION_RE = re.compile(r"^v(\d+)$")
_VERSION_ALLOC_LOCK = threading.Lock()


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
    meta_file = run_dir / RUN_META_FILENAME
    meta_file.write_text(json.dumps(meta, indent=2, default=str))


def load_run_meta(run_id: str) -> Optional[dict[str, Any]]:
    _validate_id(run_id)
    meta_file = BACKTEST_RESULTS_DIR / run_id / RUN_META_FILENAME
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
    results_file = run_dir / PARSED_RESULTS_FILENAME
    normalized = normalize_backtest_result(results)
    results_file.write_text(json.dumps(normalized, indent=2, default=str))


def load_run_results(run_id: str) -> Optional[dict[str, Any]]:
    _validate_id(run_id)
    run_dir = BACKTEST_RESULTS_DIR / run_id
    results_file = run_dir / PARSED_RESULTS_FILENAME
    normalized: Optional[dict[str, Any]] = None
    if not results_file.exists():
        normalized = None
    else:
        try:
            raw = json.loads(results_file.read_text())
            normalized = normalize_backtest_result(raw)
        except (json.JSONDecodeError, OSError):
            normalized = None

    has_local_artifact = _run_dir_has_local_artifact(run_dir)
    if normalized and (not has_local_artifact or not _results_need_rehydrate(normalized)):
        return normalized

    if has_local_artifact:
        try:
            reparsed = parse_backtest_results(run_dir)
            if not reparsed.get("error"):
                save_run_results(run_id, reparsed)
                return normalize_backtest_result(reparsed)
        except Exception:
            pass

    return normalized


def save_run_logs(run_id: str, logs: list[str]):
    _validate_id(run_id)
    run_dir = BACKTEST_RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_file = run_dir / RUN_LOGS_FILENAME
    log_file.write_text("\n".join(logs))


def _load_compact_results(run_id: str) -> Optional[dict[str, Any]]:
    results = load_run_results(run_id)
    if not results:
        return None
    return {
        "overview": results.get("overview", {}),
        "summary": results.get("summary", {}),
        "result_metrics": results.get("result_metrics") or build_metric_snapshot(results),
        "warnings": results.get("warnings", []),
    }


def load_run_raw_payload(run_id: str) -> Optional[dict[str, Any]]:
    _validate_id(run_id)
    run_dir = BACKTEST_RESULTS_DIR / run_id
    bundle = load_backtest_result_payload(run_dir)
    if bundle is not None:
        return {
            "run_id": run_id,
            "raw_artifact_missing": False,
            "artifact": bundle["artifact"],
            "payload": bundle["raw_payload"],
            "data_source": "raw_artifact",
            "strategy_name": bundle.get("strategy_name"),
        }

    parsed = load_run_results(run_id)
    if not parsed:
        return None

    return {
        "run_id": run_id,
        "raw_artifact_missing": True,
        "artifact": parsed.get("raw_artifact") or {"available": False},
        "payload": parsed,
        "data_source": "parsed_results",
        "strategy_name": parsed.get("strategy_name") or parsed.get("strategy"),
    }


def list_runs() -> list[dict[str, Any]]:
    runs = []
    if not BACKTEST_RESULTS_DIR.exists():
        return runs

    for d in sorted(BACKTEST_RESULTS_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        if not (d / RUN_META_FILENAME).exists():
            continue
        meta = load_run_meta(d.name)
        if meta:
            meta = dict(meta)
            meta["run_id"] = d.name
            meta.setdefault("display_strategy", meta.get("strategy"))
            meta.setdefault("display_version", meta.get("strategy_version"))
            has_results_file = (d / PARSED_RESULTS_FILENAME).exists()
            has_local_artifact = _run_dir_has_local_artifact(d)

            compact_results = None
            if has_results_file or has_local_artifact:
                compact_results = _load_compact_results(d.name)
                if compact_results:
                    meta.update(compact_results)

            meta["has_results"] = bool(compact_results) or has_results_file or has_local_artifact
            runs.append(meta)
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


def allocate_strategy_version_dir(strategy_base: str) -> tuple[str, Path]:
    strategy_folder = _safe_strategy_folder(strategy_base)
    strategy_dir = BACKTEST_RESULTS_DIR / strategy_folder
    strategy_dir.mkdir(parents=True, exist_ok=True)

    with _VERSION_ALLOC_LOCK:
        latest = 0
        for child in strategy_dir.iterdir():
            if not child.is_dir():
                continue
            match = _VERSION_RE.match(child.name)
            if not match:
                continue
            latest = max(latest, int(match.group(1)))

        next_version = latest + 1
        while True:
            label = f"v{next_version}"
            version_dir = strategy_dir / label
            try:
                version_dir.mkdir(parents=False, exist_ok=False)
                return label, version_dir
            except FileExistsError:
                next_version += 1


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


def _run_dir_has_local_artifact(run_dir: Path) -> bool:
    if not run_dir.exists():
        return False
    for path in run_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix == ".zip":
            return True
        if path.suffix == ".json" and path.name not in {RUN_META_FILENAME, PARSED_RESULTS_FILENAME} and not path.name.endswith(RAW_ARTIFACT_META_SUFFIX):
            return True
    return False


def _results_need_rehydrate(results: dict[str, Any]) -> bool:
    summary_metrics = results.get("summary_metrics")
    risk_metrics = results.get("risk_metrics")
    periodic_breakdown = results.get("periodic_breakdown")
    raw_artifact = results.get("raw_artifact")
    diagnostics = results.get("diagnostics")

    if not isinstance(summary_metrics, dict) or not isinstance(risk_metrics, dict):
        return True
    if not isinstance(periodic_breakdown, dict):
        return True
    if not isinstance(raw_artifact, dict):
        return True
    if not isinstance(diagnostics, dict):
        return True
    if not summary_metrics:
        return True
    if not periodic_breakdown:
        return True
    if not raw_artifact.get("available"):
        return True
    return False


def _safe_strategy_folder(strategy_base: str) -> str:
    value = _SAFE_FOLDER_RE.sub("_", str(strategy_base or "").strip())
    value = value.strip("._")
    return value or "strategy"
