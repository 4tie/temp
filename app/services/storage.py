"""
Domain storage for backtest runs and presets.

This module is the source of truth for backtest result persistence and retrieval.
Generic JSON read/write helpers live in app.core.json_io.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import threading
from pathlib import Path
from typing import Any, Optional

from app.core.config import (
    APP_EVENT_LOG_FILE,
    BACKTEST_RESULTS_DIR,
    LAST_CONFIG_FILE,
    PRESETS_FILE,
    RAW_ARTIFACT_META_SUFFIX,
    RUN_META_FILENAME,
)
from app.services.results.raw_loader import load_backtest_result_payload
from app.services.results.result_service import (
    build_compact_backtest_result,
    load_stored_backtest_results,
    normalize_backtest_result,
)
from app.services.runs.base_run_service import run_logs_path, run_meta_path, run_results_path
from app.services.runs.run_metadata_service import utcnow_iso

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_SAFE_FOLDER_RE = re.compile(r"[^A-Za-z0-9_\-]+")
_VERSION_RE = re.compile(r"^v(\d+)$")
_VERSION_ALLOC_LOCK = threading.Lock()
_APP_EVENT_LOG_LOCK = threading.Lock()

logger = logging.getLogger(__name__)


def _validate_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise ValueError(f"Invalid ID: {value!r}")
    resolved = (BACKTEST_RESULTS_DIR / value).resolve()
    if not str(resolved).startswith(str(BACKTEST_RESULTS_DIR.resolve())):
        raise ValueError(f"Path traversal detected: {value!r}")
    return value


def _run_dir(run_id: str, *, create: bool = False) -> Path:
    _validate_id(run_id)
    run_dir = BACKTEST_RESULTS_DIR / run_id
    if create:
        run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _read_json_file(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except (TypeError, ValueError) as e:
        raise ValueError(f"Failed to serialize JSON: {e}") from e


def _persist_normalized_run_results(run_dir: Path, normalized: dict[str, Any]) -> None:
    _write_json_file(run_results_path(run_dir), normalized)


def save_run_meta(run_id: str, meta: dict[str, Any]):
    _write_json_file(run_meta_path(_run_dir(run_id, create=True)), meta)


def load_run_meta(run_id: str) -> Optional[dict[str, Any]]:
    return _read_json_file(run_meta_path(_run_dir(run_id)))


def save_run_results(run_id: str, results: dict[str, Any]):
    run_dir = _run_dir(run_id, create=True)
    normalized = normalize_backtest_result(results)
    _persist_normalized_run_results(run_dir, normalized)


def load_run_results(run_id: str) -> Optional[dict[str, Any]]:
    run_dir = _run_dir(run_id)
    return load_stored_backtest_results(
        run_dir,
        persist_normalized=lambda normalized: _persist_normalized_run_results(run_dir, normalized),
    )


def save_run_logs(run_id: str, logs: list[str]):
    log_path = run_logs_path(_run_dir(run_id, create=True))
    log_path.write_text("\n".join(logs))


def append_app_event(
    *,
    category: str,
    source: str,
    action: str,
    status: str = "info",
    message: str | None = None,
    timestamp: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "timestamp": timestamp or utcnow_iso(),
        "category": str(category or "event"),
        "source": str(source or "app"),
        "action": str(action or "unknown"),
        "status": str(status or "info"),
    }
    if message:
        payload["message"] = str(message)
    for key, value in fields.items():
        if value is not None:
            payload[key] = value

    APP_EVENT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, default=str)
    try:
        with _APP_EVENT_LOG_LOCK:
            with APP_EVENT_LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")
    except OSError as exc:
        logger.warning("Failed to append app event log entry: %s", exc)
    return payload


def load_app_events(*, limit: int = 200) -> list[dict[str, Any]]:
    if limit <= 0 or not APP_EVENT_LOG_FILE.exists():
        return []
    try:
        lines = APP_EVENT_LOG_FILE.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed to read app event log: %s", exc)
        return []

    events: list[dict[str, Any]] = []
    for line in reversed(lines):
        if len(events) >= limit:
            break
        raw = (line or "").strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _load_compact_results(run_id: str) -> Optional[dict[str, Any]]:
    return build_compact_backtest_result(load_run_results(run_id))


def load_run_raw_payload(run_id: str) -> Optional[dict[str, Any]]:
    run_dir = _run_dir(run_id)
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

    for run_dir in sorted(BACKTEST_RESULTS_DIR.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        if not run_meta_path(run_dir).exists():
            continue

        meta = load_run_meta(run_dir.name)
        if not meta:
            continue

        meta = dict(meta)
        meta["run_id"] = run_dir.name
        meta.setdefault("display_strategy", meta.get("strategy"))
        meta.setdefault("display_version", meta.get("strategy_version"))

        has_results_file = run_results_path(run_dir).exists()
        has_local_artifact = _run_dir_has_local_artifact(run_dir)
        compact_results = None
        if has_results_file or has_local_artifact:
            compact_results = _load_compact_results(run_dir.name)
            if compact_results:
                meta.update(compact_results)

        meta["has_results"] = bool(compact_results) or has_results_file or has_local_artifact
        runs.append(meta)
    return runs


def delete_run(run_id: str) -> bool:
    run_dir = _run_dir(run_id)
    if run_dir.exists():
        shutil.rmtree(run_dir)
        return True
    return False


def get_run_dir(run_id: str) -> Path:
    return _run_dir(run_id, create=True)


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
    return _read_json_file(PRESETS_FILE) or {}


def save_presets(presets: dict[str, Any]):
    _write_json_file(PRESETS_FILE, presets)


def save_preset(name: str, config: dict[str, Any]):
    presets = load_presets()
    presets[name] = {
        "config": config,
        "saved_at": utcnow_iso(),
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
    _write_json_file(LAST_CONFIG_FILE, config)


def load_last_config() -> Optional[dict[str, Any]]:
    return _read_json_file(LAST_CONFIG_FILE)


def _run_dir_has_local_artifact(run_dir: Path) -> bool:
    if not run_dir.exists():
        return False
    for path in run_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix == ".zip":
            return True
        if path.suffix == ".json" and not path.name.endswith(RAW_ARTIFACT_META_SUFFIX) and path.name != RUN_META_FILENAME:
            if path != run_results_path(run_dir):
                return True
    return False


def _safe_strategy_folder(strategy_base: str) -> str:
    value = _SAFE_FOLDER_RE.sub("_", str(strategy_base or "").strip())
    value = value.strip("._")
    return value or "strategy"
