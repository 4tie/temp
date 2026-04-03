"""
Version manager — creates, lists, and manages evolved strategy versions.

Naming convention: {base_strategy}_evo_g{generation}.py
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import STRATEGIES_DIR

_EVO_RE = re.compile(r"^(.+)_evo_g(\d+)$")
_SAFE_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


@dataclass
class VersionInfo:
    version_name: str
    base_strategy: str
    generation: int
    created_at: str
    fitness: float | None = None
    run_id: str | None = None


def _safe(name: str) -> bool:
    return bool(_SAFE_RE.match(name))


def version_name_for(strategy_name: str, generation: int) -> str:
    return f"{strategy_name}_evo_g{generation}"


def create_version(strategy_name: str, source: str, generation: int) -> str:
    """Write source to a new versioned .py file and copy the JSON sidecar."""
    vname = version_name_for(strategy_name, generation)
    dest_py = STRATEGIES_DIR / f"{vname}.py"
    dest_py.write_text(source, encoding="utf-8")

    # Copy JSON sidecar so FreqTrade finds valid params
    src_json = STRATEGIES_DIR / f"{strategy_name}.json"
    dst_json = STRATEGIES_DIR / f"{vname}.json"
    if src_json.exists() and not dst_json.exists():
        shutil.copy2(src_json, dst_json)
    elif not dst_json.exists():
        dst_json.write_text("{}", encoding="utf-8")

    return vname


def list_versions(strategy_name: str) -> list[VersionInfo]:
    if not _safe(strategy_name):
        return []
    versions: list[VersionInfo] = []
    for py in STRATEGIES_DIR.glob(f"{strategy_name}_evo_g*.py"):
        m = _EVO_RE.match(py.stem)
        if not m or m.group(1) != strategy_name:
            continue
        gen = int(m.group(2))
        stat = py.stat()
        created = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        versions.append(VersionInfo(
            version_name=py.stem,
            base_strategy=strategy_name,
            generation=gen,
            created_at=created,
        ))
    versions.sort(key=lambda v: v.generation)
    return versions


def get_version_source(version_name: str) -> str | None:
    if not _safe(version_name):
        return None
    p = STRATEGIES_DIR / f"{version_name}.py"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None


def delete_version(version_name: str) -> bool:
    if not _safe(version_name):
        return False
    deleted = False
    for ext in (".py", ".json"):
        p = STRATEGIES_DIR / f"{version_name}{ext}"
        if p.exists():
            p.unlink()
            deleted = True
    return deleted


def accept_version(version_name: str, base_strategy_name: str) -> bool:
    """Overwrite base strategy .py with the accepted version."""
    if not _safe(version_name) or not _safe(base_strategy_name):
        return False
    src = STRATEGIES_DIR / f"{version_name}.py"
    dst = STRATEGIES_DIR / f"{base_strategy_name}.py"
    if not src.exists():
        return False
    shutil.copy2(src, dst)
    return True
