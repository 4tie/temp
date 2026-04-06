import json
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from app.core.config import HYPEROPT_RUNS_DIR
from app.services.runs.base_run_service import run_logs_path, run_meta_path, run_results_path

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_HYPEROPT_RUNS_DIR = HYPEROPT_RUNS_DIR


def _validate_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise ValueError(f"Invalid ID: {value!r}")
    resolved = (_HYPEROPT_RUNS_DIR / value).resolve()
    if not str(resolved).startswith(str(_HYPEROPT_RUNS_DIR.resolve())):
        raise ValueError(f"Path traversal detected: {value!r}")
    return value


def _run_dir(run_id: str, *, create: bool = False) -> Path:
    _validate_id(run_id)
    run_dir = _HYPEROPT_RUNS_DIR / run_id
    if create:
        run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _read_json_file(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))


def get_hyperopt_run_dir(run_id: str) -> Path:
    return _run_dir(run_id, create=True)


def save_hyperopt_meta(run_id: str, meta: dict[str, Any]):
    _write_json_file(run_meta_path(_run_dir(run_id, create=True)), meta)


def load_hyperopt_meta(run_id: str) -> Optional[dict[str, Any]]:
    return _read_json_file(run_meta_path(_run_dir(run_id)))


def save_hyperopt_results(run_id: str, results: dict[str, Any]):
    _write_json_file(run_results_path(_run_dir(run_id, create=True)), results)


def load_hyperopt_results(run_id: str) -> Optional[dict[str, Any]]:
    return _read_json_file(run_results_path(_run_dir(run_id)))


def save_hyperopt_logs(run_id: str, logs: list[str]):
    run_logs_path(_run_dir(run_id, create=True)).write_text("\n".join(logs))


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
            meta["has_results"] = run_results_path(d).exists()
            runs.append(meta)
        else:
            runs.append({
                "run_id": d.name,
                "status": "unknown",
                "has_results": run_results_path(d).exists(),
            })
    return runs


def delete_hyperopt_run(run_id: str) -> bool:
    run_dir = _run_dir(run_id)
    if run_dir.exists():
        shutil.rmtree(run_dir)
        return True
    return False
