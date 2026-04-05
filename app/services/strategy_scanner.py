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
    module = ast.parse(content, filename=str(file_path))
    class_node = _find_strategy_class(module)
    if class_node is None:
        class_match = re.search(r"class\s+(\w+)\s*\(.*?IStrategy.*?\)", content)
        if not class_match:
            return None
        class_name = class_match.group(1)
        params = []
    else:
        class_name = class_node.name
        params = _extract_parameters(class_node)

    return {
        "name": class_name,
        "file_path": str(file_path),
        "parameters": params,
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

    return {
        "name": name,
        "type": "int",
        "low": low,
        "high": high,
        "default": default,
        "space": kwargs.get("space", "buy"),
        "optimize": bool(kwargs.get("optimize", True)),
    }


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

    return {
        "name": name,
        "type": "decimal",
        "low": low,
        "high": high,
        "default": default,
        "decimals": decimals,
        "space": kwargs.get("space", "buy"),
        "optimize": bool(kwargs.get("optimize", True)),
    }


def _parse_boolean_parameter(name: str, call: ast.Call) -> dict[str, Any]:
    args = [_literal(arg) for arg in call.args]
    kwargs = _call_keywords(call)
    default = kwargs.get("default", args[0] if args else False)
    return {
        "name": name,
        "type": "bool",
        "default": bool(default),
        "space": kwargs.get("space", "buy"),
        "optimize": bool(kwargs.get("optimize", True)),
    }


def _parse_categorical_parameter(name: str, call: ast.Call) -> dict[str, Any]:
    args = [_literal(arg) for arg in call.args]
    kwargs = _call_keywords(call)
    options = kwargs.get("choices", args[0] if args else []) or []
    default = kwargs.get("default")
    if default is None and len(args) > 1 and not isinstance(args[1], (list, tuple, dict)):
        default = args[1]
    if default is None and options:
        default = options[0]
    return {
        "name": name,
        "type": "categorical",
        "options": list(options),
        "default": default,
        "space": kwargs.get("space", "buy"),
        "optimize": bool(kwargs.get("optimize", True)),
    }
