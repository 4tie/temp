from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from app.core.config import STRATEGIES_DIR

_SAFE_STRATEGY_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def strategies_root(strategies_dir: Path | None = None) -> Path:
    return Path(strategies_dir or STRATEGIES_DIR)


def normalize_strategy_name(name: str) -> str:
    value = str(name or "").strip()
    if value.lower().endswith(".py"):
        value = value[:-3]
    return value


def validate_strategy_name(name: str, *, strategies_dir: Path | None = None) -> str:
    value = normalize_strategy_name(name)
    if not value or not _SAFE_STRATEGY_RE.match(value):
        raise ValueError("Invalid strategy name")

    root = strategies_root(strategies_dir).resolve()
    resolved = (root / f"{value}.py").resolve()
    if not str(resolved).startswith(str(root)):
        raise ValueError("Invalid strategy name")
    return value


def resolve_strategy_source_path(strategy_name: str, *, strategies_dir: Path | None = None) -> Path:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    return strategies_root(strategies_dir) / f"{name}.py"


def resolve_strategy_sidecar_path(strategy_name: str, *, strategies_dir: Path | None = None) -> Path:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    return strategies_root(strategies_dir) / f"{name}.json"


def validate_python_source(strategy_name: str, source: str) -> dict[str, Any]:
    name = normalize_strategy_name(strategy_name)
    module = ast.parse(str(source or ""), filename=f"{name}.py")
    class_names = [node.name for node in module.body if isinstance(node, ast.ClassDef)]
    return {
        "syntax_ok": True,
        "class_names": class_names,
        "class_name_matches_file": name in class_names if class_names else None,
    }


__all__ = [
    "normalize_strategy_name",
    "resolve_strategy_sidecar_path",
    "resolve_strategy_source_path",
    "strategies_root",
    "validate_python_source",
    "validate_strategy_name",
]
