from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.core.config import STRATEGIES_DIR
from app.services.strategies.strategy_param_metadata_service import load_strategy_param_metadata
from app.services.strategies.strategy_restore_service import create_snapshot
from app.services.strategies.strategy_sidecar_service import load_strategy_sidecar_record
from app.services.strategies.strategy_sidecar_service import read_strategy_sidecar_payload
from app.services.strategies.strategy_source_service import atomic_write_text
from app.services.strategies.strategy_source_service import load_strategy_source_record
from app.services.strategies.strategy_validation_service import validate_strategy_name
from app.services.strategies.strategy_validation_service import validate_python_source

_STAGED_VERSION_RE = re.compile(r"^(.+)_evo_g(\d+)$")


def get_strategy_editable_context(strategy_name: str, *, strategies_dir: Path | None = None) -> dict[str, Any]:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    metadata = load_strategy_param_metadata(name, strategies_dir=strategies_dir)
    extracted_params = list(metadata.get("parameters") or [])
    sidecar = load_strategy_sidecar_record(
        name,
        strategies_dir=strategies_dir,
        extracted_params=extracted_params,
    )
    source = load_strategy_source_record(name, strategies_dir=strategies_dir)

    current_values = dict(sidecar.get("current_values") or {})
    metadata_missing = bool(metadata.get("missing_source"))
    sidecar_exists = bool(sidecar.get("exists"))
    extracted_names = {
        item.get("name")
        for item in extracted_params
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    merged_parameters: list[dict[str, Any]] = []
    for item in extracted_params:
        if not isinstance(item, dict):
            continue
        merged = dict(item)
        param_name = merged.get("name")
        if isinstance(param_name, str) and param_name in current_values:
            merged["value"] = current_values[param_name]
        merged_parameters.append(merged)

    validation = {
        "strategy_name_valid": True,
        "source_exists": bool(source.get("exists")),
        "source_syntax_ok": source.get("syntax_ok"),
        "source_class_names": list(source.get("class_names") or []),
        "source_class_name_matches_file": source.get("class_name_matches_file"),
        "metadata_missing_source": metadata_missing,
        "metadata_parse_ok": None if metadata_missing else not bool(metadata.get("parse_error")),
        "sidecar_exists": sidecar_exists,
        "sidecar_valid_json": None if not sidecar_exists else bool(sidecar.get("valid_json")),
        "sidecar_uses_legacy_flat_format": bool(sidecar.get("legacy_flat")),
        "unknown_sidecar_keys": sorted(
            key for key in current_values.keys() if key not in extracted_names
        ),
    }

    return {
        "strategy": name,
        "source_path": source.get("path"),
        "sidecar_path": sidecar.get("path"),
        "extracted_params": extracted_params,
        "current_values": current_values,
        "parameters": merged_parameters,
        "source_code": source.get("source"),
        "sidecar_payload": sidecar.get("normalized_payload") or {},
        "validation": validation,
    }


def _strategies_root(strategies_dir: Path | None = None) -> Path:
    return Path(strategies_dir) if strategies_dir is not None else STRATEGIES_DIR


def _next_generation(strategy_name: str, *, strategies_dir: Path | None = None) -> int:
    root = _strategies_root(strategies_dir)
    max_generation = 0
    for py_file in root.glob(f"{strategy_name}_evo_g*.py"):
        match = _STAGED_VERSION_RE.match(py_file.stem)
        if not match or match.group(1) != strategy_name:
            continue
        try:
            max_generation = max(max_generation, int(match.group(2)))
        except ValueError:
            continue
    return max_generation + 1


def stage_strategy_source_change(
    strategy_name: str,
    source: str,
    *,
    strategies_dir: Path | None = None,
    reason: str = "manual_stage",
    actor: str = "user",
) -> dict[str, Any]:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    root = _strategies_root(strategies_dir)
    base_py = root / f"{name}.py"
    if not base_py.exists():
        raise FileNotFoundError(f"Strategy source not found: {base_py.name}")

    validation = validate_python_source(name, source)
    generation = _next_generation(name, strategies_dir=root)
    version_name = f"{name}_evo_g{generation}"
    staged_py = root / f"{version_name}.py"
    staged_json = root / f"{version_name}.json"

    bytes_written = atomic_write_text(staged_py, source)
    base_payload: dict[str, Any] = read_strategy_sidecar_payload(name, strategies_dir=root)
    base_payload["strategy_name"] = name
    base_payload["params"] = {}
    atomic_write_text(staged_json, json.dumps(base_payload, indent=2))

    return {
        "ok": True,
        "strategy": name,
        "version_name": version_name,
        "generation": generation,
        "staged_file_path": str(staged_py),
        "staged_sidecar_path": str(staged_json),
        "bytes_written": bytes_written,
        "validation": validation,
        "change_contract": {
            "mode": "staged",
            "reason": reason,
            "actor": actor,
            "requires_manual_promotion": True,
        },
    }


def promote_staged_strategy_version(
    *,
    strategy_name: str,
    version_name: str,
    strategies_dir: Path | None = None,
) -> dict[str, Any]:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    version = validate_strategy_name(version_name, strategies_dir=strategies_dir)
    expected_prefix = f"{name}_evo_g"
    if not version.startswith(expected_prefix):
        raise ValueError(f"Version {version} does not belong to strategy {name}")

    root = _strategies_root(strategies_dir)
    src_py = root / f"{version}.py"
    src_json = root / f"{version}.json"
    dst_py = root / f"{name}.py"
    dst_json = root / f"{name}.json"
    if not src_py.exists():
        raise FileNotFoundError(f"Staged strategy source not found: {src_py.name}")

    source = src_py.read_text(encoding="utf-8")
    validation = validate_python_source(name, source)
    py_bytes = atomic_write_text(dst_py, source)
    if src_json.exists():
        json_bytes = atomic_write_text(dst_json, src_json.read_text(encoding="utf-8"))
    else:
        payload: dict[str, Any] = read_strategy_sidecar_payload(name, strategies_dir=root)
        payload["strategy_name"] = name
        payload["params"] = {}
        json_bytes = atomic_write_text(dst_json, json.dumps(payload, indent=2))

    return {
        "ok": True,
        "strategy": name,
        "accepted_version": version,
        "source_path": str(dst_py),
        "sidecar_path": str(dst_json),
        "bytes_written": {"py": py_bytes, "json": json_bytes},
        "validation": validation,
    }


__all__ = [
    "get_strategy_editable_context",
    "promote_staged_strategy_version",
    "stage_strategy_source_change",
]
