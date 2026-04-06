"""
Version manager — creates, lists, and manages evolved strategy versions.

Naming convention: {base_strategy}_evo_g{generation}.py
"""
from __future__ import annotations

import re
import shutil
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import AI_EVOLUTION_DIR, STRATEGIES_DIR
from app.core.json_io import read_json

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


def _atomic_copy(src: Path, dst: Path) -> None:
    tmp_fd, tmp_name = tempfile.mkstemp(dir=dst.parent, suffix=".tmp")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        shutil.copy2(src, tmp_path)
        os.replace(tmp_path, dst)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _effective_params_payload(strategy_name: str) -> dict:
    src_json = STRATEGIES_DIR / f"{strategy_name}.json"
    payload: dict = {}
    if src_json.exists():
        try:
            raw = json.loads(src_json.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload = dict(raw)
        except Exception:
            payload = {}
    payload["strategy_name"] = strategy_name
    payload["params"] = {}
    return payload


def create_version(strategy_name: str, source: str, generation: int) -> str:
    """Write source to a new versioned .py file and a neutral JSON sidecar."""
    vname = version_name_for(strategy_name, generation)
    dest_py = STRATEGIES_DIR / f"{vname}.py"
    dest_py.write_text(source, encoding="utf-8")

    dst_json = STRATEGIES_DIR / f"{vname}.json"
    dst_json.write_text(
        json.dumps(_effective_params_payload(strategy_name), indent=2),
        encoding="utf-8",
    )

    return vname


def create_backtest_workspace(
    base_strategy_name: str,
    version_name: str,
    source: str,
    loop_id: str,
    generation: int,
) -> Path:
    workspace = AI_EVOLUTION_DIR / loop_id / f"generation_{generation}" / "strategy"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / f"{base_strategy_name}.py").write_text(source, encoding="utf-8")
    (workspace / f"{base_strategy_name}.json").write_text(
        json.dumps(_effective_params_payload(base_strategy_name), indent=2),
        encoding="utf-8",
    )
    (workspace / "version_name.txt").write_text(version_name, encoding="utf-8")
    return workspace


def _version_enrichment() -> dict[str, dict]:
    enrichment: dict[str, dict] = {}
    if not AI_EVOLUTION_DIR.exists():
        return enrichment

    for log_path in AI_EVOLUTION_DIR.glob("*.json"):
        if log_path.stem.endswith("_feedback"):
            continue
        data = read_json(log_path, {})
        for generation in data.get("generations", []):
            version_name = generation.get("version_name")
            if not version_name:
                continue
            enrichment[version_name] = {
                "fitness": generation.get("fitness_after"),
                "run_id": generation.get("new_run_id"),
            }
    return enrichment


def list_versions(strategy_name: str) -> list[VersionInfo]:
    if not _safe(strategy_name):
        return []
    enrichment = _version_enrichment()
    versions: list[VersionInfo] = []
    for py in STRATEGIES_DIR.glob(f"{strategy_name}_evo_g*.py"):
        m = _EVO_RE.match(py.stem)
        if not m or m.group(1) != strategy_name:
            continue
        gen = int(m.group(2))
        stat = py.stat()
        created = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        extra = enrichment.get(py.stem, {})
        versions.append(VersionInfo(
            version_name=py.stem,
            base_strategy=strategy_name,
            generation=gen,
            created_at=created,
            fitness=extra.get("fitness"),
            run_id=extra.get("run_id"),
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
    """Atomically promote an evolved version over the base strategy files."""
    if not _safe(version_name) or not _safe(base_strategy_name):
        return False
    src_py = STRATEGIES_DIR / f"{version_name}.py"
    src_json = STRATEGIES_DIR / f"{version_name}.json"
    dst_py = STRATEGIES_DIR / f"{base_strategy_name}.py"
    dst_json = STRATEGIES_DIR / f"{base_strategy_name}.json"
    if not src_py.exists():
        return False
    _atomic_copy(src_py, dst_py)
    if src_json.exists():
        _atomic_copy(src_json, dst_json)
    else:
        dst_json.write_text(
            json.dumps(_effective_params_payload(base_strategy_name), indent=2),
            encoding="utf-8",
        )
    return True
