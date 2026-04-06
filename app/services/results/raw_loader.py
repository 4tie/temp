from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from app.core.config import PARSED_RESULTS_FILENAME, RAW_ARTIFACT_META_SUFFIX, RUN_META_FILENAME
from app.services.results.payload_detector import resolve_strategy_payload


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

    strategy_name, strategy_data = resolve_strategy_payload(raw_payload)
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

    meta_file = result_dir / RUN_META_FILENAME
    parsed_file = result_dir / PARSED_RESULTS_FILENAME
    json_files = [
        path
        for path in result_dir.glob("*.json")
        if path not in (meta_file, parsed_file) and not path.name.endswith(RAW_ARTIFACT_META_SUFFIX)
    ]
    if json_files:
        return sorted(json_files, key=lambda path: path.stat().st_mtime, reverse=True)[0]

    zip_files = list(result_dir.glob("*.zip"))
    if zip_files:
        return sorted(zip_files, key=lambda path: path.stat().st_mtime, reverse=True)[0]

    return None


def _load_from_zip(zip_path: Path) -> tuple[dict[str, Any], str | None] | None:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            for name in archive.namelist():
                if not name.endswith(".json") or "_config" in name:
                    continue
                data = json.loads(archive.read(name))
                strategy_name, strategy_data = resolve_strategy_payload(data)
                if strategy_data is not None:
                    return data, name
                if strategy_name is not None:
                    return data, name
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError):
        return None
    return None


__all__ = [
    "find_run_local_result_artifact",
    "load_backtest_result_payload",
]
