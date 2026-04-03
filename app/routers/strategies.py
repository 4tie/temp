from fastapi import APIRouter

from app.services.strategy_scanner import list_strategies, get_strategy_params

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("")
async def get_strategies():
    strategies = list_strategies()
    return {"strategies": strategies}


@router.get("/{strategy_name}/params")
async def get_params(strategy_name: str):
    params = get_strategy_params(strategy_name)
    return {"strategy": strategy_name, "parameters": params}
