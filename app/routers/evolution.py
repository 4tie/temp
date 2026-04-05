"""
Evolution API router — 7 endpoints for the strategy evolution engine.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.ai.goals import normalize_goal_id
from app.services.storage import load_run_meta
from app.ai.evolution.evolver import (
    start_evolution,
    get_evolution_status,
    list_evolution_runs,
    drain_events,
    get_run_detail,
)
from app.ai.evolution.version_manager import list_versions, accept_version, delete_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evolution", tags=["evolution"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class EvolutionStartRequest(BaseModel):
    run_id: str
    goal_id: Optional[str] = None
    max_generations: int = Field(default=3, ge=1, le=10)
    provider: str = "openrouter"
    model: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start")
async def evolution_start(req: EvolutionStartRequest):
    meta = load_run_meta(req.run_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Run '{req.run_id}' not found.")
    if meta.get("status") not in ("completed",):
        raise HTTPException(status_code=400, detail="Run must be completed before evolving.")

    loop_id = str(uuid.uuid4())
    goal_id = normalize_goal_id(req.goal_id)
    start_evolution(
        run_id=req.run_id,
        goal_id=goal_id,
        max_generations=req.max_generations,
        provider=req.provider,
        model=req.model,
        loop_id=loop_id,
    )
    return {"loop_id": loop_id}


@router.get("/stream/{loop_id}")
async def evolution_stream(loop_id: str):
    async def event_generator():
        timeout = 700  # seconds — slightly over max backtest wait
        elapsed = 0
        poll_interval = 1.0

        while elapsed < timeout:
            events = drain_events(loop_id)
            for evt in events:
                yield _sse(evt)
                if evt.get("done"):
                    return

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        yield _sse({"step": "error", "message": "Stream timed out.", "done": True})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs")
async def evolution_runs():
    return list_evolution_runs()


@router.get("/run/{loop_id}")
async def evolution_run_detail(loop_id: str):
    detail = get_run_detail(loop_id)
    if not detail:
        # Fall back to in-memory session
        session = get_evolution_status(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Evolution run not found.")
        return {"loop_id": loop_id, "session": session, "generations": []}
    return detail


@router.get("/versions/{strategy}")
async def evolution_versions(strategy: str):
    versions = list_versions(strategy)
    return [
        {
            "version_name": v.version_name,
            "base_strategy": v.base_strategy,
            "generation": v.generation,
            "created_at": v.created_at,
            "fitness": v.fitness,
            "run_id": v.run_id,
        }
        for v in versions
    ]


@router.post("/accept/{loop_id}/{generation}")
async def evolution_accept(loop_id: str, generation: int):
    detail = get_run_detail(loop_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Evolution run not found.")

    session = detail.get("session", {})
    strategy_name = ""

    # Find the version for this generation
    version_name: str | None = None
    for gen in detail.get("generations", []):
        if gen.get("generation") == generation and gen.get("version_name"):
            version_name = gen["version_name"]
            break

    if not version_name:
        raise HTTPException(status_code=404, detail=f"No version found for generation {generation}.")

    # Derive base strategy name from version name (strip _evo_g{N})
    import re
    m = re.match(r"^(.+)_evo_g\d+$", version_name)
    if not m:
        raise HTTPException(status_code=400, detail="Cannot determine base strategy name.")
    base_strategy = m.group(1)

    ok = accept_version(version_name, base_strategy)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to apply version.")

    return {"accepted": version_name, "applied_to": base_strategy}


@router.delete("/version/{version_name}")
async def evolution_delete_version(version_name: str):
    deleted = delete_version(version_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Version not found.")
    return {"deleted": version_name}
