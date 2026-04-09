from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.services.strategies.strategy_param_metadata_service import get_strategy_param_metadata
from app.services.strategies.strategy_restore_service import create_snapshot
from app.services.strategies.strategy_validation_service import resolve_strategy_sidecar_path, validate_strategy_name

_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, indent=2).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _param_space_index(extracted_params: list[dict[str, Any]] | None) -> dict[str, str]:
    index: dict[str, str] = {}
    for item in extracted_params or []:
        name = item.get("name")
        if isinstance(name, str):
            index[name] = str(item.get("space") or "buy")
    return index


def _resolved_params(
    strategy_name: str,
    *,
    strategies_dir: Path | None = None,
    extracted_params: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if extracted_params is not None:
        return list(extracted_params)
    try:
        return get_strategy_param_metadata(strategy_name, strategies_dir=strategies_dir)
    except Exception:
        return []


def build_strategy_sidecar_payload(
    strategy_name: str,
    flat_params: dict[str, Any] | None,
    *,
    extracted_params: list[dict[str, Any]] | None = None,
    base_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = validate_strategy_name(strategy_name)
    payload = dict(base_payload or {})
    payload["strategy_name"] = name

    param_spaces = _param_space_index(extracted_params)
    space_map: dict[str, dict[str, Any]] = {}
    for key, value in (flat_params or {}).items():
        if not isinstance(key, str) or not isinstance(value, _JSON_SCALAR_TYPES):
            continue
        space = param_spaces.get(key, "sell" if key.startswith("sell_") else "buy")
        space_map.setdefault(space, {})[key] = value
    payload["params"] = space_map
    return payload


def _flatten_sidecar_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    params = payload.get("params", payload)
    if "params" in payload:
        flat: dict[str, Any] = {}
        if isinstance(params, dict):
            for values in params.values():
                if isinstance(values, dict):
                    flat.update({key: value for key, value in values.items() if isinstance(value, _JSON_SCALAR_TYPES)})
        return flat, False

    if not isinstance(params, dict):
        return {}, True
    return {key: value for key, value in params.items() if isinstance(value, _JSON_SCALAR_TYPES)}, True


def load_strategy_sidecar_record(
    strategy_name: str,
    *,
    strategies_dir: Path | None = None,
    extracted_params: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    resolved_params = _resolved_params(
        name,
        strategies_dir=strategies_dir,
        extracted_params=extracted_params,
    )
    path = resolve_strategy_sidecar_path(name, strategies_dir=strategies_dir)
    record: dict[str, Any] = {
        "strategy": name,
        "path": str(path),
        "exists": path.exists(),
        "valid_json": True,
        "legacy_flat": False,
        "raw_payload": {},
        "normalized_payload": build_strategy_sidecar_payload(name, {}, extracted_params=resolved_params),
        "current_values": {},
    }
    if not path.exists():
        return record

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        record["valid_json"] = False
        return record

    if not isinstance(raw, dict):
        record["valid_json"] = False
        return record

    current_values, legacy_flat = _flatten_sidecar_payload(raw)
    record["legacy_flat"] = legacy_flat
    record["raw_payload"] = raw
    record["current_values"] = current_values
    record["normalized_payload"] = build_strategy_sidecar_payload(
        name,
        current_values,
        extracted_params=resolved_params,
        base_payload=raw,
    )
    return record


def read_strategy_current_values(
    strategy_name: str,
    *,
    strategies_dir: Path | None = None,
    extracted_params: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record = load_strategy_sidecar_record(
        strategy_name,
        strategies_dir=strategies_dir,
        extracted_params=extracted_params,
    )
    return dict(record.get("current_values") or {})


def read_strategy_sidecar_payload(
    strategy_name: str,
    *,
    strategies_dir: Path | None = None,
    extracted_params: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record = load_strategy_sidecar_record(
        strategy_name,
        strategies_dir=strategies_dir,
        extracted_params=extracted_params,
    )
    return dict(record.get("normalized_payload") or {})


def save_strategy_current_values(
    strategy_name: str,
    flat_params: dict[str, Any],
    *,
    strategies_dir: Path | None = None,
    extracted_params: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    resolved_params = _resolved_params(
        name,
        strategies_dir=strategies_dir,
        extracted_params=extracted_params,
    )
    path = resolve_strategy_sidecar_path(name, strategies_dir=strategies_dir)
    payload = build_strategy_sidecar_payload(name, flat_params, extracted_params=resolved_params)

    # Create snapshot before modifying live strategy
    try:
        snapshot_result = create_snapshot(
            strategy_name=name,
            reason="save_strategy_current_values",
            actor="system",
            linked_run_id=None,
            metadata={"operation": "save_params", "param_count": len(flat_params)}
        )
    except Exception:
        # Don't fail the save if snapshot creation fails, but log it
        pass

    _atomic_write_json(path, payload)
    return {
        "ok": True,
        "strategy": name,
        "sidecar_path": str(path),
        "current_values": dict(flat_params or {}),
        "payload": payload,
    }


__all__ = [
    "build_strategy_sidecar_payload",
    "load_strategy_sidecar_record",
    "read_strategy_current_values",
    "read_strategy_sidecar_payload",
    "save_strategy_current_values",
]
