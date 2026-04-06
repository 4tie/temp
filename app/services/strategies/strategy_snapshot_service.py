from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.strategies.strategy_param_metadata_service import load_strategy_param_metadata
from app.services.strategies.strategy_sidecar_service import load_strategy_sidecar_record
from app.services.strategies.strategy_source_service import load_strategy_source_record
from app.services.strategies.strategy_validation_service import validate_strategy_name


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


__all__ = ["get_strategy_editable_context"]
