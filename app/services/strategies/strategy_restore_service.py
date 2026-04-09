from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import BACKTEST_RESULTS_DIR, STRATEGY_HISTORY_DIR
from app.services.strategies.strategy_validation_service import (
    resolve_strategy_sidecar_path,
    resolve_strategy_source_path,
    validate_strategy_name,
)


def _generate_snapshot_id() -> str:
    """Generate a unique snapshot ID."""
    return str(uuid.uuid4())


def _calculate_hash(content: str) -> str:
    """Calculate SHA256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _resolve_snapshot_dir(strategy_name: str, snapshot_id: str) -> Path:
    """Resolve the directory for a specific snapshot."""
    name = validate_strategy_name(strategy_name)
    return STRATEGY_HISTORY_DIR / name / snapshot_id


def _ensure_snapshot_dir(strategy_name: str, snapshot_id: str) -> Path:
    """Ensure the snapshot directory exists and return its path."""
    path = _resolve_snapshot_dir(strategy_name, snapshot_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_snapshot(
    strategy_name: str,
    reason: str,
    actor: str,
    linked_run_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a snapshot of the current strategy state.

    Args:
        strategy_name: Name of the strategy to snapshot
        reason: Reason for creating the snapshot
        actor: Who/what created the snapshot (user, ai, system)
        linked_run_id: Optional backtest run ID this snapshot relates to
        metadata: Additional metadata to store

    Returns:
        Snapshot metadata including ID and paths
    """
    name = validate_strategy_name(strategy_name)
    snapshot_id = _generate_snapshot_id()
    snapshot_dir = _ensure_snapshot_dir(name, snapshot_id)

    # Read current source and sidecar
    source_path = resolve_strategy_source_path(name)
    sidecar_path = resolve_strategy_sidecar_path(name)

    if not source_path.exists():
        raise FileNotFoundError(f"Strategy source not found: {source_path}")

    source_content = source_path.read_text(encoding="utf-8")
    sidecar_content = "{}"
    if sidecar_path.exists():
        sidecar_content = sidecar_path.read_text(encoding="utf-8")

    # Calculate hashes and sizes
    source_hash = _calculate_hash(source_content)
    sidecar_hash = _calculate_hash(sidecar_content)
    source_bytes = len(source_content.encode("utf-8"))
    sidecar_bytes = len(sidecar_content.encode("utf-8"))

    # Create metadata
    meta = {
        "snapshot_id": snapshot_id,
        "strategy_name": name,
        "created_at": datetime.now().isoformat(),
        "reason": reason,
        "actor": actor,
        "linked_run_id": linked_run_id,
        "source_path": str(source_path),
        "sidecar_path": str(sidecar_path),
        "source_hash": source_hash,
        "sidecar_hash": sidecar_hash,
        "source_bytes": source_bytes,
        "sidecar_bytes": sidecar_bytes,
        "base_version_name": None,  # Will be set by caller if applicable
    }

    # Add custom metadata
    if metadata:
        meta.update(metadata)

    # Write files atomically
    snapshot_source_path = snapshot_dir / "source.py"
    snapshot_sidecar_path = snapshot_dir / "sidecar.json"
    snapshot_meta_path = snapshot_dir / "meta.json"

    # Use atomic writes
    _atomic_write_text(snapshot_source_path, source_content)
    _atomic_write_text(snapshot_sidecar_path, sidecar_content)
    _atomic_write_text(snapshot_meta_path, json.dumps(meta, indent=2))

    return {
        "snapshot_id": snapshot_id,
        "strategy_name": name,
        "snapshot_dir": str(snapshot_dir),
        "source_path": str(snapshot_source_path),
        "sidecar_path": str(snapshot_sidecar_path),
        "meta_path": str(snapshot_meta_path),
        "meta": meta,
    }


def list_snapshots(strategy_name: str) -> list[dict[str, Any]]:
    """
    List all snapshots for a strategy, enriched with result summaries.

    Args:
        strategy_name: Name of the strategy

    Returns:
        List of snapshot metadata, sorted by creation time (newest first)
    """
    name = validate_strategy_name(strategy_name)
    strategy_history_dir = STRATEGY_HISTORY_DIR / name

    if not strategy_history_dir.exists():
        return []

    snapshots = []
    for snapshot_dir in strategy_history_dir.iterdir():
        if not snapshot_dir.is_dir():
            continue

        meta_path = snapshot_dir / "meta.json"
        if not meta_path.exists():
            continue

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            # Enrich with result summary if linked
            enriched = enrich_snapshot_with_result_summary(meta)
            snapshots.append(enriched)
        except (json.JSONDecodeError, KeyError):
            continue

    # Sort by creation time, newest first
    snapshots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return snapshots


def load_snapshot(strategy_name: str, snapshot_id: str) -> dict[str, Any]:
    """
    Load a specific snapshot's data.

    Args:
        strategy_name: Name of the strategy
        snapshot_id: ID of the snapshot

    Returns:
        Snapshot data including source, sidecar, and metadata
    """
    name = validate_strategy_name(strategy_name)
    snapshot_dir = _resolve_snapshot_dir(name, snapshot_id)

    if not snapshot_dir.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_dir}")

    source_path = snapshot_dir / "source.py"
    sidecar_path = snapshot_dir / "sidecar.json"
    meta_path = snapshot_dir / "meta.json"

    if not all(p.exists() for p in [source_path, sidecar_path, meta_path]):
        raise FileNotFoundError(f"Incomplete snapshot: {snapshot_dir}")

    source = source_path.read_text(encoding="utf-8")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    return {
        "snapshot_id": snapshot_id,
        "strategy_name": name,
        "source": source,
        "sidecar": sidecar,
        "meta": meta,
        "snapshot_dir": str(snapshot_dir),
    }


def restore_snapshot(strategy_name: str, snapshot_id: str) -> dict[str, Any]:
    """
    Restore a snapshot to become the current live strategy.

    Args:
        strategy_name: Name of the strategy
        snapshot_id: ID of the snapshot to restore

    Returns:
        Restore operation result
    """
    # Create snapshot of current state before restoring
    try:
        pre_restore_snapshot = create_snapshot(
            strategy_name=strategy_name,
            reason="pre_restore_snapshot",
            actor="system",
            linked_run_id=None,
            metadata={"operation": "pre_restore", "target_snapshot_id": snapshot_id}
        )
    except Exception:
        # Don't fail the restore if pre-snapshot creation fails
        pass

    # Load the snapshot
    snapshot = load_snapshot(strategy_name, snapshot_id)

    # Get current live paths
    source_path = resolve_strategy_source_path(strategy_name)
    sidecar_path = resolve_strategy_sidecar_path(strategy_name)

    # Write to live locations atomically
    _atomic_write_text(source_path, snapshot["source"])
    _atomic_write_text(sidecar_path, json.dumps(snapshot["sidecar"], indent=2))

    # Update metadata to mark as restored
    meta_path = Path(snapshot["snapshot_dir"]) / "meta.json"
    meta = snapshot["meta"]
    meta["restored_at"] = datetime.now().isoformat()
    meta["restored_to_live"] = True
    _atomic_write_text(meta_path, json.dumps(meta, indent=2))

    return {
        "ok": True,
        "strategy_name": strategy_name,
        "snapshot_id": snapshot_id,
        "source_path": str(source_path),
        "sidecar_path": str(sidecar_path),
        "source_bytes": len(snapshot["source"].encode("utf-8")),
        "sidecar_bytes": len(json.dumps(snapshot["sidecar"], indent=2).encode("utf-8")),
    }


def compare_snapshot_to_current(strategy_name: str, snapshot_id: str) -> dict[str, Any]:
    """
    Compare a snapshot to the current live strategy state.

    Args:
        strategy_name: Name of the strategy
        snapshot_id: ID of the snapshot

    Returns:
        Comparison result with diffs
    """
    # Load snapshot
    snapshot = load_snapshot(strategy_name, snapshot_id)

    # Load current
    current_source_path = resolve_strategy_source_path(strategy_name)
    current_sidecar_path = resolve_strategy_sidecar_path(strategy_name)

    current_source = ""
    if current_source_path.exists():
        current_source = current_source_path.read_text(encoding="utf-8")

    current_sidecar = {}
    if current_sidecar_path.exists():
        try:
            current_sidecar = json.loads(current_sidecar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    # Simple diff (could be enhanced with proper diff library)
    source_diff = {
        "has_changes": snapshot["source"] != current_source,
        "snapshot_lines": len(snapshot["source"].splitlines()),
        "current_lines": len(current_source.splitlines()),
        "snapshot_bytes": len(snapshot["source"].encode("utf-8")),
        "current_bytes": len(current_source.encode("utf-8")),
    }

    sidecar_diff = {
        "has_changes": snapshot["sidecar"] != current_sidecar,
        "snapshot_keys": list(snapshot["sidecar"].keys()),
        "current_keys": list(current_sidecar.keys()),
    }

    return {
        "strategy_name": strategy_name,
        "snapshot_id": snapshot_id,
        "source_diff": source_diff,
        "sidecar_diff": sidecar_diff,
        "snapshot_meta": snapshot["meta"],
    }


def enrich_snapshot_with_result_summary(snapshot_meta: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich snapshot metadata with backtest result summary if linked.

    Args:
        snapshot_meta: Snapshot metadata

    Returns:
        Enriched metadata with result summary
    """
    enriched = snapshot_meta.copy()

    # Try to find linked results
    linked_run_id = snapshot_meta.get("linked_run_id")
    if linked_run_id:
        result_dir = BACKTEST_RESULTS_DIR / linked_run_id
        meta_path = result_dir / "meta.json"
        parsed_path = result_dir / "parsed_results.json"

        if meta_path.exists() and parsed_path.exists():
            try:
                run_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                parsed_results = json.loads(parsed_path.read_text(encoding="utf-8"))

                # Extract summary metrics
                summary = {
                    "run_id": linked_run_id,
                    "starting_balance": run_meta.get("dry_run_wallet", {}).get("starting_balance"),
                    "final_balance": parsed_results.get("final_balance"),
                    "profit_percent": parsed_results.get("profit_percent"),
                    "total_trades": parsed_results.get("total_trades"),
                    "win_rate": parsed_results.get("win_rate"),
                    "max_drawdown": parsed_results.get("max_drawdown"),
                    "timeframe": run_meta.get("timeframe"),
                    "pairs": run_meta.get("pairs", []),
                    "exchange": run_meta.get("exchange"),
                }
                enriched["result_summary"] = summary
            except (json.JSONDecodeError, KeyError):
                pass

    return enriched


def _atomic_write_text(path: Path, content: str) -> int:
    """Atomically write text content to a file."""
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


__all__ = [
    "create_snapshot",
    "list_snapshots",
    "load_snapshot",
    "restore_snapshot",
    "compare_snapshot_to_current",
    "enrich_snapshot_with_result_summary",
]