import json
import re
import ast
import os
import tempfile
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Any

from app.core.config import STRATEGIES_DIR
from app.services.strategy_scanner import list_strategies, get_strategy_params

router = APIRouter(prefix="/strategies", tags=["strategies"])

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


def _checked_strategy(name: str) -> str:
    if not name or not _SAFE_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid strategy name")
    resolved = (STRATEGIES_DIR / f"{name}.py").resolve()
    if not str(resolved).startswith(str(STRATEGIES_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid strategy name")
    return name


def _read_sidecar(strategy: str) -> dict:
    """Return flat {param: value} dict from the nested params sidecar."""
    path = STRATEGIES_DIR / f"{strategy}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        params = data.get("params", data)  # support legacy flat format
        if "params" in data:
            flat = {}
            for space_vals in params.values():
                if isinstance(space_vals, dict):
                    flat.update(space_vals)
            return flat
        return {k: v for k, v in params.items() if isinstance(v, _JSON_SCALAR_TYPES)}
    except Exception:
        return {}


def _write_sidecar(strategy: str, flat_params: dict[str, Any], all_params: list[dict]) -> None:
    """Write flat params into nested {"strategy_name": ..., "params": {space: {key: val}}} format."""
    space_map: dict[str, dict] = {}
    param_spaces = {p["name"]: p.get("space", "buy") for p in all_params}
    for k, v in flat_params.items():
        space = param_spaces.get(k, "sell" if k.startswith("sell_") else "buy")
        space_map.setdefault(space, {})[k] = v
    path = STRATEGIES_DIR / f"{strategy}.json"
    path.write_text(json.dumps({"strategy_name": strategy, "params": space_map}, indent=2), encoding="utf-8")


class ParamUpdate(BaseModel):
    parameters: dict[str, Any]


class SourceUpdate(BaseModel):
    source: str


def _atomic_write_utf8(path, content: str) -> int:
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


@router.get("")
async def get_strategies():
    strategies = list_strategies()
    return {"strategies": strategies}


@router.get("/{strategy_name}/params")
async def get_params(strategy_name: str):
    _checked_strategy(strategy_name)
    params = get_strategy_params(strategy_name)
    current = _read_sidecar(strategy_name)
    for p in params:
        if p["name"] in current:
            p["value"] = current[p["name"]]
    return {"strategy": strategy_name, "parameters": params}


@router.post("/{strategy_name}/params")
async def save_params(strategy_name: str, body: ParamUpdate):
    _checked_strategy(strategy_name)
    all_params = get_strategy_params(strategy_name)
    _write_sidecar(strategy_name, body.parameters, all_params)
    return {"ok": True}


@router.get("/{strategy_name}/source", response_class=PlainTextResponse)
async def get_source(strategy_name: str):
    _checked_strategy(strategy_name)
    path = STRATEGIES_DIR / f"{strategy_name}.py"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Strategy source not found")
    return path.read_text(encoding="utf-8")


@router.post("/{strategy_name}/source")
async def save_source(strategy_name: str, body: SourceUpdate):
    _checked_strategy(strategy_name)
    path = STRATEGIES_DIR / f"{strategy_name}.py"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Strategy source not found")

    try:
        ast.parse(body.source, filename=f"{strategy_name}.py")
    except SyntaxError as exc:
        line = exc.lineno or 0
        col = exc.offset or 0
        detail = f"Python syntax error at line {line}, column {col}: {exc.msg}"
        raise HTTPException(status_code=400, detail=detail)

    bytes_written = _atomic_write_utf8(path, body.source)
    return {"ok": True, "strategy": strategy_name, "bytes_written": bytes_written}
