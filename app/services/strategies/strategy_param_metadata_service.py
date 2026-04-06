from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from app.services.strategies.strategy_validation_service import resolve_strategy_source_path, strategies_root, validate_strategy_name


def list_strategies(*, strategies_dir: Path | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    root = strategies_root(strategies_dir)
    if not root.exists():
        return items

    for file_path in sorted(root.glob("*.py")):
        if file_path.name.startswith("_"):
            continue
        try:
            info = _parse_strategy_file(file_path)
            if info:
                items.append(info)
        except Exception:
            items.append(
                {
                    "strategy": file_path.stem,
                    "name": file_path.stem,
                    "class_name": None,
                    "file_path": str(file_path),
                    "parameters": [],
                    "parse_error": True,
                }
            )
    return items


def get_strategy_param_metadata(strategy_name: str, *, strategies_dir: Path | None = None) -> list[dict[str, Any]]:
    info = load_strategy_param_metadata(strategy_name, strategies_dir=strategies_dir)
    return list(info.get("parameters") or [])


def load_strategy_param_metadata(strategy_name: str, *, strategies_dir: Path | None = None) -> dict[str, Any]:
    name = validate_strategy_name(strategy_name, strategies_dir=strategies_dir)
    path = resolve_strategy_source_path(name, strategies_dir=strategies_dir)
    if not path.exists():
        return {
            "strategy": name,
            "name": name,
            "class_name": None,
            "file_path": str(path),
            "parameters": [],
            "parse_error": False,
            "missing_source": True,
        }

    try:
        info = _parse_strategy_file(path)
    except Exception as exc:
        return {
            "strategy": name,
            "name": name,
            "class_name": None,
            "file_path": str(path),
            "parameters": [],
            "parse_error": True,
            "error": str(exc),
        }

    if info is None:
        return {
            "strategy": name,
            "name": name,
            "class_name": None,
            "file_path": str(path),
            "parameters": [],
            "parse_error": False,
        }
    return info


def _parse_strategy_file(file_path: Path) -> dict[str, Any] | None:
    content = file_path.read_text(encoding="utf-8", errors="replace")
    module = ast.parse(content, filename=str(file_path))
    class_node = _find_strategy_class(module)
    if class_node is None:
        class_match = re.search(r"class\s+(\w+)\s*\(.*?IStrategy.*?\)", content)
        if not class_match:
            return None
        class_name = class_match.group(1)
        params: list[dict[str, Any]] = []
    else:
        class_name = class_node.name
        params = _extract_parameters(class_node)

    return {
        "strategy": file_path.stem,
        "name": class_name,
        "class_name": class_name,
        "file_path": str(file_path),
        "parameters": params,
        "parse_error": False,
    }


def _find_strategy_class(module: ast.Module) -> ast.ClassDef | None:
    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "IStrategy":
                return node
            if isinstance(base, ast.Attribute) and base.attr == "IStrategy":
                return node
    return None


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _assign_name(node: ast.stmt) -> str | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _call_value(node: ast.stmt) -> ast.Call | None:
    value = getattr(node, "value", None)
    if isinstance(value, ast.Call):
        return value
    return None


def _call_keywords(call: ast.Call) -> dict[str, Any]:
    return {kw.arg: _literal(kw.value) for kw in call.keywords if kw.arg}


def _to_int(value: Any, fallback: int) -> int:
    try:
        if value is None:
            return fallback
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _to_float(value: Any, fallback: float) -> float:
    try:
        if value is None:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _base_parameter(name: str, *, param_type: str, default: Any, space: Any, optimize: Any) -> dict[str, Any]:
    return {
        "name": name,
        "type": param_type,
        "space": space or "buy",
        "optimize": bool(optimize if optimize is not None else True),
        "default": default,
        "low": None,
        "high": None,
        "decimals": None,
        "options": [],
    }


def _extract_parameters(class_node: ast.ClassDef) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []
    for stmt in class_node.body:
        name = _assign_name(stmt)
        call = _call_value(stmt)
        if not name or call is None:
            continue

        call_name = _call_name(call.func)
        if call_name == "IntParameter":
            params.append(_parse_int_parameter(name, call))
        elif call_name == "DecimalParameter":
            params.append(_parse_decimal_parameter(name, call))
        elif call_name == "BooleanParameter":
            params.append(_parse_boolean_parameter(name, call))
        elif call_name == "CategoricalParameter":
            params.append(_parse_categorical_parameter(name, call))
    return params


def _parse_int_parameter(name: str, call: ast.Call) -> dict[str, Any]:
    args = [_literal(arg) for arg in call.args]
    kwargs = _call_keywords(call)
    low_raw = kwargs.get("low", args[0] if len(args) > 0 else 0)
    high_raw = kwargs.get("high", args[1] if len(args) > 1 else low_raw)
    default_raw = kwargs.get("default", args[2] if len(args) > 2 else low_raw)

    low = _to_int(low_raw, 0)
    high = _to_int(high_raw, low)
    default = _to_int(default_raw, low)

    if high < low:
        high = low
    if default < low:
        default = low
    if default > high:
        default = high

    payload = _base_parameter(
        name,
        param_type="int",
        default=default,
        space=kwargs.get("space", "buy"),
        optimize=kwargs.get("optimize", True),
    )
    payload["low"] = low
    payload["high"] = high
    return payload


def _parse_decimal_parameter(name: str, call: ast.Call) -> dict[str, Any]:
    args = [_literal(arg) for arg in call.args]
    kwargs = _call_keywords(call)
    low_raw = kwargs.get("low", args[0] if len(args) > 0 else 0.0)
    high_raw = kwargs.get("high", args[1] if len(args) > 1 else low_raw)
    default_raw = kwargs.get("default", args[2] if len(args) > 2 else low_raw)
    decimals_raw = kwargs.get("decimals", 3)

    low = _to_float(low_raw, 0.0)
    high = _to_float(high_raw, low)
    default = _to_float(default_raw, low)
    decimals = _to_int(decimals_raw, 3)

    if high < low:
        high = low
    if default < low:
        default = low
    if default > high:
        default = high

    payload = _base_parameter(
        name,
        param_type="decimal",
        default=default,
        space=kwargs.get("space", "buy"),
        optimize=kwargs.get("optimize", True),
    )
    payload["low"] = low
    payload["high"] = high
    payload["decimals"] = decimals
    return payload


def _parse_boolean_parameter(name: str, call: ast.Call) -> dict[str, Any]:
    args = [_literal(arg) for arg in call.args]
    kwargs = _call_keywords(call)
    default = kwargs.get("default", args[0] if args else False)
    return _base_parameter(
        name,
        param_type="bool",
        default=bool(default),
        space=kwargs.get("space", "buy"),
        optimize=kwargs.get("optimize", True),
    )


def _parse_categorical_parameter(name: str, call: ast.Call) -> dict[str, Any]:
    args = [_literal(arg) for arg in call.args]
    kwargs = _call_keywords(call)
    options = kwargs.get("choices", args[0] if args else []) or []
    default = kwargs.get("default")
    if default is None and len(args) > 1 and not isinstance(args[1], (list, tuple, dict)):
        default = args[1]
    if default is None and options:
        default = options[0]

    payload = _base_parameter(
        name,
        param_type="categorical",
        default=default,
        space=kwargs.get("space", "buy"),
        optimize=kwargs.get("optimize", True),
    )
    payload["options"] = list(options)
    return payload


__all__ = [
    "get_strategy_param_metadata",
    "list_strategies",
    "load_strategy_param_metadata",
]
