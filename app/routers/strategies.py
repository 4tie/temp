from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Any

from app.core.config import STRATEGIES_DIR
from app.services.strategies import (
    get_strategy_editable_context,
    list_strategies,
    read_strategy_source,
    save_strategy_current_values,
    save_strategy_source,
    validate_strategy_name,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _checked_strategy(name: str) -> str:
    try:
        return validate_strategy_name(name, strategies_dir=STRATEGIES_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ParamUpdate(BaseModel):
    parameters: dict[str, Any]


class SourceUpdate(BaseModel):
    source: str


@router.get("")
async def get_strategies():
    strategies = list_strategies(strategies_dir=STRATEGIES_DIR)
    return {"strategies": strategies}


@router.get("/{strategy_name}/params")
async def get_params(strategy_name: str):
    strategy = _checked_strategy(strategy_name)
    context = get_strategy_editable_context(strategy, strategies_dir=STRATEGIES_DIR)
    return {
        "strategy": strategy,
        "parameters": context.get("parameters") or [],
        "current_values": context.get("current_values") or {},
        "validation": context.get("validation") or {},
        "source_path": context.get("source_path"),
        "sidecar_path": context.get("sidecar_path"),
    }


@router.post("/{strategy_name}/params")
async def save_params(strategy_name: str, body: ParamUpdate):
    strategy = _checked_strategy(strategy_name)
    context = get_strategy_editable_context(strategy, strategies_dir=STRATEGIES_DIR)
    result = save_strategy_current_values(
        strategy,
        body.parameters,
        strategies_dir=STRATEGIES_DIR,
        extracted_params=context.get("extracted_params") or [],
    )
    return {"ok": True, "strategy": strategy, "sidecar_path": result.get("sidecar_path")}


@router.get("/{strategy_name}/source", response_class=PlainTextResponse)
async def get_source(strategy_name: str):
    strategy = _checked_strategy(strategy_name)
    try:
        return read_strategy_source(strategy, strategies_dir=STRATEGIES_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy source not found")


@router.post("/{strategy_name}/source")
async def save_source(strategy_name: str, body: SourceUpdate):
    strategy = _checked_strategy(strategy_name)
    try:
        result = save_strategy_source(strategy, body.source, strategies_dir=STRATEGIES_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy source not found")
    except SyntaxError as exc:
        line = exc.lineno or 0
        col = exc.offset or 0
        detail = f"Python syntax error at line {line}, column {col}: {exc.msg}"
        raise HTTPException(status_code=400, detail=detail)
    return {"ok": True, "strategy": strategy, "bytes_written": result.get("bytes_written", 0)}
