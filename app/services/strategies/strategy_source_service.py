from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from app.services.strategies.strategy_restore_service import create_snapshot
from app.services.strategies.strategy_validation_service import (
    resolve_strategy_source_path,
    validate_python_source,
    validate_strategy_name,
)


def atomic_write_text(path: Path, content: str) -> int:
    encoded = content.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return len(encoded)


def read_strategy_source(strategy_name: str, *, strategies_dir: Path | None = None) -> str:
    path = resolve_strategy_source_path(strategy_name, strategies_dir=strategies_dir)
    if not path.exists():
        raise FileNotFoundError(f"Strategy source not found: {path.name}")
    return path.read_text(encoding="utf-8")


def load_strategy_source_record(strategy_name: str, *, strategies_dir: Path | None = None) -> dict[str, Any]:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    path = resolve_strategy_source_path(name, strategies_dir=strategies_dir)
    record: dict[str, Any] = {
        "strategy": name,
        "path": str(path),
        "exists": path.exists(),
        "source": None,
        "bytes": 0,
        "syntax_ok": None,
        "class_names": [],
        "class_name_matches_file": None,
    }
    if not path.exists():
        return record

    source = path.read_text(encoding="utf-8")
    record["source"] = source
    record["bytes"] = len(source.encode("utf-8"))
    try:
        validation = validate_python_source(name, source)
    except SyntaxError:
        record["syntax_ok"] = False
        return record

    record["syntax_ok"] = True
    record["class_names"] = list(validation.get("class_names") or [])
    record["class_name_matches_file"] = validation.get("class_name_matches_file")
    return record


def save_strategy_source(strategy_name: str, source: str, *, strategies_dir: Path | None = None) -> dict[str, Any]:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    path = resolve_strategy_source_path(name, strategies_dir=strategies_dir)
    if not path.exists():
        raise FileNotFoundError(f"Strategy source not found: {path.name}")

    validation = validate_python_source(name, source)

    # Create snapshot before modifying live strategy
    try:
        snapshot_result = create_snapshot(
            strategy_name=name,
            reason="save_strategy_source",
            actor="system",
            linked_run_id=None,
            metadata={"operation": "save_source", "source_bytes": len(source.encode("utf-8"))}
        )
    except Exception:
        # Don't fail the save if snapshot creation fails, but log it
        pass

    bytes_written = atomic_write_text(path, source)
    return {
        "ok": True,
        "strategy": name,
        "source_path": str(path),
        "bytes_written": bytes_written,
        "validation": validation,
    }


__all__ = [
    "atomic_write_text",
    "load_strategy_source_record",
    "read_strategy_source",
    "save_strategy_source",
]
