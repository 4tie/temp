from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Any

from app.core.config import STRATEGIES_DIR
from app.services.strategies import (
    compare_snapshot_to_current,
    create_snapshot,
    get_strategy_editable_context,
    list_snapshots,
    list_strategies,
    load_snapshot,
    promote_staged_strategy_version,
    read_strategy_source,
    restore_snapshot,
    save_strategy_current_values,
    save_strategy_source,
    stage_strategy_source_change,
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


class VersionAcceptRequest(BaseModel):
    version_name: str


class SnapshotCreateRequest(BaseModel):
    reason: str
    actor: str
    linked_run_id: str | None = None
    metadata: dict[str, Any] | None = None


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


@router.post("/{strategy_name}/source/stage")
async def stage_source(strategy_name: str, body: SourceUpdate):
    strategy = _checked_strategy(strategy_name)
    try:
        result = stage_strategy_source_change(
            strategy_name=strategy,
            source=body.source,
            strategies_dir=STRATEGIES_DIR,
            reason="strategy_editor_stage",
            actor="user",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy source not found")
    except SyntaxError as exc:
        line = exc.lineno or 0
        col = exc.offset or 0
        detail = f"Python syntax error at line {line}, column {col}: {exc.msg}"
        raise HTTPException(status_code=400, detail=detail)
    return result


@router.get("/{strategy_name}/versions")
async def list_strategy_versions(strategy_name: str):
    strategy = _checked_strategy(strategy_name)
    versions = []
    for path in sorted(STRATEGIES_DIR.glob(f"{strategy}_evo_g*.py")):
        versions.append(path.stem)
    return {"strategy": strategy, "versions": versions}


@router.post("/{strategy_name}/versions/accept")
async def accept_strategy_version(strategy_name: str, body: VersionAcceptRequest):
    strategy = _checked_strategy(strategy_name)
    try:
        result = promote_staged_strategy_version(
            strategy_name=strategy,
            version_name=body.version_name,
            strategies_dir=STRATEGIES_DIR,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SyntaxError as exc:
        line = exc.lineno or 0
        col = exc.offset or 0
        detail = f"Python syntax error at line {line}, column {col}: {exc.msg}"
        raise HTTPException(status_code=400, detail=detail)
    return result


# History endpoints
@router.get("/{strategy_name}/history")
async def get_strategy_history(strategy_name: str):
    strategy = _checked_strategy(strategy_name)
    try:
        snapshots = list_snapshots(strategy)
        return {"strategy": strategy, "snapshots": snapshots}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list snapshots: {exc}") from exc


@router.get("/{strategy_name}/history/{snapshot_id}")
async def get_snapshot(strategy_name: str, snapshot_id: str):
    strategy = _checked_strategy(strategy_name)
    try:
        snapshot = load_snapshot(strategy, snapshot_id)
        return snapshot
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load snapshot: {exc}") from exc


@router.post("/{strategy_name}/history/snapshot")
async def create_strategy_snapshot(strategy_name: str, body: SnapshotCreateRequest):
    strategy = _checked_strategy(strategy_name)
    try:
        result = create_snapshot(
            strategy_name=strategy,
            reason=body.reason,
            actor=body.actor,
            linked_run_id=body.linked_run_id,
            metadata=body.metadata,
        )
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {exc}") from exc


@router.post("/{strategy_name}/history/{snapshot_id}/restore")
async def restore_strategy_snapshot(strategy_name: str, snapshot_id: str):
    strategy = _checked_strategy(strategy_name)
    try:
        result = restore_snapshot(strategy, snapshot_id)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to restore snapshot: {exc}") from exc


@router.get("/{strategy_name}/history/{snapshot_id}/compare")
async def compare_strategy_snapshot(strategy_name: str, snapshot_id: str):
    strategy = _checked_strategy(strategy_name)
    try:
        result = compare_snapshot_to_current(strategy, snapshot_id)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compare snapshot: {exc}") from exc


@router.post("/{strategy_name}/versions/{version_name}/accept")
async def accept_strategy_version_path(strategy_name: str, version_name: str):
    strategy = _checked_strategy(strategy_name)
    try:
        result = promote_staged_strategy_version(
            strategy_name=strategy,
            version_name=version_name,
            strategies_dir=STRATEGIES_DIR,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SyntaxError as exc:
        line = exc.lineno or 0
        col = exc.offset or 0
        detail = f"Python syntax error at line {line}, column {col}: {exc.msg}"
        raise HTTPException(status_code=400, detail=detail)
    return result
