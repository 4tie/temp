import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Any

from app.core.config import STRATEGIES_DIR
from app.services.strategy_scanner import list_strategies, get_strategy_params

router = APIRouter(prefix="/strategies", tags=["strategies"])

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _checked_strategy(name: str) -> str:
    if not name or not _SAFE_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid strategy name")
    resolved = (STRATEGIES_DIR / f"{name}.py").resolve()
    if not str(resolved).startswith(str(STRATEGIES_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid strategy name")
    return name


@router.get("")
async def get_strategies():
    strategies = list_strategies()
    return {"strategies": strategies}


@router.get("/{strategy_name}/params")
async def get_params(strategy_name: str):
    _checked_strategy(strategy_name)
    params = get_strategy_params(strategy_name)
    return {"strategy": strategy_name, "parameters": params}


@router.get("/{strategy_name}/source", response_class=PlainTextResponse)
async def get_source(strategy_name: str):
    _checked_strategy(strategy_name)
    path = STRATEGIES_DIR / f"{strategy_name}.py"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Strategy source not found")
    return path.read_text(encoding="utf-8")
