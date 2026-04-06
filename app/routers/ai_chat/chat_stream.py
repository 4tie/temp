from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.ai_chat import ChatRequest
from app.ai.context_builder import build_context_bundle
from app.ai.goals import normalize_goal_id
from app.ai.pipelines.orchestrator import stream_run, list_pipeline_logs
from app.ai.tools.deep_analysis import analyze
from app.ai.memory.threads import append_message, create_thread, load_thread
from app.services.ai_chat.stream_event_service import sse_line
from app.services.ai_chat.thread_service import (
    assistant_meta,
    history_context,
    resolve_thread_id,
    role_overrides,
)
from app.services.storage import load_run_meta, load_run_results

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest):
    thread_id = resolve_thread_id(req)
    thread = load_thread(thread_id)
    goal_id = normalize_goal_id(req.goal_id or (thread or {}).get("goal_id"))
    provider_name = req.provider or (thread or {}).get("provider", "openrouter")
    model_id = req.model or (thread or {}).get("model")

    if thread is None:
        thread = create_thread(
            thread_id=thread_id,
            provider=provider_name,
            model=model_id,
            goal_id=goal_id,
            context_run_id=req.context_run_id,
        )

    pinned_context_run_id = req.context_run_id
    if not pinned_context_run_id and thread.get("context_mode") == "pinned":
        pinned_context_run_id = thread.get("context_run_id")

    context_bundle = build_context_bundle(goal_id, pinned_context_run_id)
    actual_context_run_id = context_bundle.metadata.get("context_run_id")
    context_mode = "pinned" if pinned_context_run_id else context_bundle.metadata.get("context_mode", "auto")
    history_text = history_context(thread.get("messages", []))
    full_context = context_bundle.context_text
    if history_text:
        full_context = f"{full_context}\n\n--- CONVERSATION HISTORY ---\n{history_text}"

    append_message(
        thread_id,
        "user",
        req.message,
        goal_id=goal_id,
        provider=provider_name,
        model=model_id,
        context_run_id=actual_context_run_id,
        context_mode=context_mode,
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        full_text = ""
        pipeline_info: dict[str, Any] | None = None
        try:
            async for chunk in stream_run(
                task_text=req.message,
                context=full_context,
                context_hint=context_bundle.context_hint,
                context_metadata=context_bundle.metadata,
                goal_id=goal_id,
                provider=provider_name,
                role_overrides=role_overrides(model_id),
                has_strategy_source=bool(context_bundle.snapshot.get("strategy_config")),
            ):
                if chunk.get("error"):
                    yield sse_line({"error": chunk["error"], "done": True})
                    return
                if chunk.get("delta"):
                    full_text += chunk["delta"]
                if chunk.get("done"):
                    pipeline_info = chunk.get("pipeline") or {}
                    full_text = chunk.get("fullText") or full_text
                    append_message(
                        thread_id,
                        "assistant",
                        full_text,
                        meta=assistant_meta(
                            pipeline=pipeline_info,
                            goal_id=goal_id,
                            thread_id=thread_id,
                            context_run_id=actual_context_run_id,
                            context_mode=context_mode,
                        ),
                        goal_id=goal_id,
                        provider=provider_name,
                        model=(pipeline_info.get("steps") or [{}])[-1].get("model_id") if pipeline_info else model_id,
                        context_run_id=actual_context_run_id,
                        context_mode=context_mode,
                    )
                    latest_thread = load_thread(thread_id) or {}
                    assistant_message_id = None
                    messages = latest_thread.get("messages") or []
                    if messages:
                        assistant_message_id = messages[-1].get("id")
                    final_chunk = dict(chunk)
                    final_chunk["thread_id"] = thread_id
                    final_chunk["conversation_id"] = thread_id
                    final_chunk["assistant_message_id"] = assistant_message_id
                    yield sse_line(final_chunk)
                    return
                yield sse_line(chunk)
        except Exception as exc:
            logger.error("Chat stream error for thread %s: %s", thread_id, exc)
            yield sse_line({"error": str(exc), "done": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze/{run_id}")
async def analyze_run(run_id: str):
    meta = load_run_meta(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    results = load_run_results(run_id) or {}
    run_data = {**results, "strategy": meta.get("strategy", "")}

    try:
        analysis = analyze(run_data, run_id=run_id, include_ai_narrative=False)
        return analysis
    except Exception as exc:
        logger.error("Deep analysis failed for run %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.get("/pipeline-logs")
async def get_pipeline_logs():
    return list_pipeline_logs(limit=50)
