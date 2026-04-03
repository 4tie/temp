import re
import ast
from pathlib import Path
from typing import Any

from app.core.config import STRATEGIES_DIR


def list_strategies() -> list[dict[str, Any]]:
    strategies = []
    if not STRATEGIES_DIR.exists():
        return strategies

    for f in sorted(STRATEGIES_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            info = _parse_strategy_file(f)
            if info:
                strategies.append(info)
        except Exception:
            strategies.append({
                "name": f.stem,
                "file_path": str(f),
                "parameters": [],
                "parse_error": True,
            })
    return strategies


def get_strategy_params(strategy_name: str) -> list[dict[str, Any]]:
    for f in STRATEGIES_DIR.glob("*.py"):
        if f.stem == strategy_name:
            info = _parse_strategy_file(f)
            if info:
                return info.get("parameters", [])
    return []


def _parse_strategy_file(file_path: Path) -> dict[str, Any] | None:
    content = file_path.read_text(errors="replace")

    class_match = re.search(r"class\s+(\w+)\s*\(.*?IStrategy.*?\)", content)
    if not class_match:
        return None

    class_name = class_match.group(1)
    params = _extract_parameters(content)

    return {
        "name": class_name,
        "file_path": str(file_path),
        "parameters": params,
    }


def _extract_parameters(content: str) -> list[dict[str, Any]]:
    params = []

    int_pattern = re.compile(
        r"(\w+)\s*=\s*IntParameter\s*\(\s*"
        r"(?:low\s*=\s*)?(-?\d+)\s*,\s*"
        r"(?:high\s*=\s*)?(-?\d+)\s*"
        r"(?:,\s*default\s*=\s*(-?\d+))?"
        r"(?:,\s*space\s*=\s*['\"](\w+)['\"])?"
        r"(?:,\s*optimize\s*=\s*(True|False))?"
    )

    dec_pattern = re.compile(
        r"(\w+)\s*=\s*DecimalParameter\s*\(\s*"
        r"(?:low\s*=\s*)?(-?[\d.]+)\s*,\s*"
        r"(?:high\s*=\s*)?(-?[\d.]+)\s*"
        r"(?:,\s*default\s*=\s*(-?[\d.]+))?"
        r"(?:,\s*decimals\s*=\s*(\d+))?"
        r"(?:,\s*space\s*=\s*['\"](\w+)['\"])?"
        r"(?:,\s*optimize\s*=\s*(True|False))?"
    )

    bool_pattern = re.compile(
        r"(\w+)\s*=\s*BooleanParameter\s*\(\s*"
        r"(?:default\s*=\s*)?(True|False)"
        r"(?:,\s*space\s*=\s*['\"](\w+)['\"])?"
        r"(?:,\s*optimize\s*=\s*(True|False))?"
    )

    cat_pattern = re.compile(
        r"(\w+)\s*=\s*CategoricalParameter\s*\(\s*"
        r"\[(.*?)\]"
        r"(?:,\s*default\s*=\s*['\"]?([\w.]+)['\"]?)?"
        r"(?:,\s*space\s*=\s*['\"](\w+)['\"])?"
        r"(?:,\s*optimize\s*=\s*(True|False))?"
    )

    for m in int_pattern.finditer(content):
        params.append({
            "name": m.group(1),
            "type": "int",
            "low": int(m.group(2)),
            "high": int(m.group(3)),
            "default": int(m.group(4)) if m.group(4) else int(m.group(2)),
            "space": m.group(5) or "buy",
            "optimize": m.group(6) != "False" if m.group(6) else True,
        })

    for m in dec_pattern.finditer(content):
        params.append({
            "name": m.group(1),
            "type": "decimal",
            "low": float(m.group(2)),
            "high": float(m.group(3)),
            "default": float(m.group(4)) if m.group(4) else float(m.group(2)),
            "decimals": int(m.group(5)) if m.group(5) else 3,
            "space": m.group(6) or "buy",
            "optimize": m.group(7) != "False" if m.group(7) else True,
        })

    for m in bool_pattern.finditer(content):
        params.append({
            "name": m.group(1),
            "type": "bool",
            "default": m.group(2) == "True",
            "space": m.group(3) or "buy",
            "optimize": m.group(4) != "False" if m.group(4) else True,
        })

    for m in cat_pattern.finditer(content):
        raw_options = m.group(2)
        options = [o.strip().strip("'\"") for o in raw_options.split(",")]
        params.append({
            "name": m.group(1),
            "type": "categorical",
            "options": options,
            "default": m.group(3) if m.group(3) else options[0] if options else None,
            "space": m.group(4) or "buy",
            "optimize": m.group(5) != "False" if m.group(5) else True,
        })

    return params
