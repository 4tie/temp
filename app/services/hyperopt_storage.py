import json
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from app.core.config import HYPEROPT_RESULTS_DIR

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

_HYPEROPT_RUNS_DIR = HYPEROPT_RESULTS_DIR / "runs"
_HYPEROPT_RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _validate_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise ValueError(f"Invalid ID: {value!r}")
    resolved = (_HYPEROPT_RUNS_DIR / value).resolve()
    if not str(resolved).startswith(str(_HYPEROPT_RUNS_DIR.resolve())):
        raise ValueError(f"Path traversal detected: {value!r}")
    return value


def get_hyperopt_run_dir(run_id: str) -> Path:
    _validate_id(run_id)
    d = _HYPEROPT_RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_hyperopt_meta(run_id: str, meta: dict[str, Any]):
    _validate_id(run_id)
    run_dir = _HYPEROPT_RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))


def load_hyperopt_meta(run_id: str) -> Optional[dict[str, Any]]:
    _validate_id(run_id)
    meta_file = _HYPEROPT_RUNS_DIR / run_id / "meta.json"
    if not meta_file.exists():
        return None
    try:
        return json.loads(meta_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_hyperopt_results(run_id: str, results: dict[str, Any]):
    _validate_id(run_id)
    run_dir = _HYPEROPT_RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "parsed_results.json").write_text(json.dumps(results, indent=2, default=str))


def load_hyperopt_results(run_id: str) -> Optional[dict[str, Any]]:
    _validate_id(run_id)
    results_file = _HYPEROPT_RUNS_DIR / run_id / "parsed_results.json"
    if not results_file.exists():
        return None
    try:
        return json.loads(results_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_hyperopt_logs(run_id: str, logs: list[str]):
    _validate_id(run_id)
    run_dir = _HYPEROPT_RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs.txt").write_text("\n".join(logs))


def list_hyperopt_runs() -> list[dict[str, Any]]:
    runs = []
    if not _HYPEROPT_RUNS_DIR.exists():
        return runs

    for d in sorted(_HYPEROPT_RUNS_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        meta = load_hyperopt_meta(d.name)
        if meta:
            meta["run_id"] = d.name
            meta["has_results"] = (d / "parsed_results.json").exists()
            runs.append(meta)
        else:
            runs.append({
                "run_id": d.name,
                "status": "unknown",
                "has_results": (d / "parsed_results.json").exists(),
            })
    return runs


def delete_hyperopt_run(run_id: str) -> bool:
    _validate_id(run_id)
    run_dir = _HYPEROPT_RUNS_DIR / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
        return True
    return False
