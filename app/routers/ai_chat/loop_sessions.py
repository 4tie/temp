from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.ai_chat import LoopStartRequest, LoopConfirmRequest
from app.services.ai_chat.loop_service import (
    confirm_rerun,
    loop_drain,
    loop_metrics_payload,
    list_loop_sessions_payload,
    start_loop_session,
    stop_loop,
)
from app.services.ai_chat.stream_event_service import sse_line

router = APIRouter()


@router.post("/loop/start")
async def loop_start(req: LoopStartRequest):
    return start_loop_session(req)


@router.post("/loop/{loop_id}/confirm-rerun")
async def loop_confirm_rerun(loop_id: str, req: LoopConfirmRequest):
    return confirm_rerun(loop_id, req)


@router.post("/loop/{loop_id}/stop")
async def loop_stop(loop_id: str, req: LoopConfirmRequest | None = None):
    return stop_loop(loop_id, req)


@router.get("/loop/{loop_id}/stream")
async def loop_stream(loop_id: str):
    async def event_stream() -> AsyncGenerator[str, None]:
        timeout_s = 3600
        elapsed = 0.0
        while elapsed < timeout_s:
            events = loop_drain(loop_id)
            for event in events:
                yield sse_line(event)
                if event.get("done"):
                    return
            await asyncio.sleep(0.4)
            elapsed += 0.4
        yield sse_line({"loop_id": loop_id, "step": "loop_failed", "status": "failed", "message": "stream timeout", "done": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/loop/{loop_id}/metrics")
async def loop_metrics(loop_id: str):
    return loop_metrics_payload(loop_id)


@router.get("/loop/sessions")
async def list_loop_sessions():
    return list_loop_sessions_payload()
