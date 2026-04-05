"""
AI Chat Router — REST + SSE endpoints for the AI subsystem.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.ai_chat import ChatRequest, ConversationSummary, ThreadMessageAppendRequest
from app.ai.context_builder import build_context_bundle
from app.ai.goals import normalize_goal_id
from app.ai.pipelines.orchestrator import stream_run
from app.ai.models.openrouter_client import has_api_keys, list_models as or_list_models
from app.ai.models.ollama_client import is_available, list_models as oll_list_models
from app.ai.tools.deep_analysis import analyze
from app.ai.memory.threads import (
    append_message,
    create_thread,
    delete_thread,
    list_threads,
    load_thread,
    validate_thread_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


# ─────────────────────────────────────────────────────────────────────────────
# Conversation helpers (local wrappers for HTTP error handling)
# ─────────────────────────────────────────────────────────────────────────────

def _validate_thread_id_http(thread_id: str) -> str:
    try:
        return validate_thread_id(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _thread_summary(thread: dict[str, Any]) -> ConversationSummary:
    thread_id = thread.get("thread_id") or thread.get("conversation_id") or ""
    return ConversationSummary(
        thread_id=thread_id,
        conversation_id=thread_id,
        title=thread.get("title", "Untitled"),
        preview=thread.get("preview"),
        created_at=thread.get("created_at", ""),
        updated_at=thread.get("updated_at", ""),
        message_count=len(thread.get("messages", [])),
        provider=thread.get("provider", "openrouter"),
        model=thread.get("model"),
        goal_id=thread.get("goal_id"),
        context_run_id=thread.get("context_run_id"),
        context_mode=thread.get("context_mode"),
    )


def _history_context(messages: list[dict[str, Any]], limit: int = 12) -> str:
    lines = []
    for message in messages[-limit:]:
        role = str(message.get("role", "user")).upper()
        content = str(message.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _resolve_thread_id(req: ChatRequest) -> str:
    return req.thread_id or req.conversation_id or str(uuid.uuid4())


def _role_overrides(model_id: str | None) -> dict[str, str] | None:
    if not model_id:
        return None
    return {
        "reasoner": model_id,
        "analyst_a": model_id,
        "analyst_b": model_id,
        "judge": model_id,
        "composer": model_id,
        "explainer": model_id,
        "code_gen": model_id,
        "structured_output": model_id,
        "classifier": model_id,
    }


def _assistant_meta(
    *,
    pipeline: dict[str, Any],
    goal_id: str,
    thread_id: str,
    context_run_id: str | None,
    context_mode: str,
) -> dict[str, Any]:
    steps = pipeline.get("steps") or []
    final_step = next((step for step in reversed(steps) if step.get("role") != "classifier"), {}) if steps else {}
    return {
        "pipeline_type": pipeline.get("pipeline_type", "simple"),
        "duration_ms": pipeline.get("total_duration_ms"),
        "model": final_step.get("model_id"),
        "provider": final_step.get("provider"),
        "goal_id": goal_id,
        "thread_id": thread_id,
        "conversation_id": thread_id,
        "context_run_id": context_run_id,
        "context_mode": context_mode,
        "trace": pipeline.get("trace", []),
        "pipeline": pipeline,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SSE helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sse_line(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/providers")
async def get_providers():
    openrouter_available = has_api_keys()
    openrouter_models = []
    if openrouter_available:
        try:
            raw = await or_list_models()
            openrouter_models = [{"id": model["id"], "name": model.get("name", model["id"])} for model in raw[:50]]
        except Exception as exc:
            logger.warning("OpenRouter model list failed: %s", exc)

    ollama_available = await is_available()
    ollama_models = []
    if ollama_available:
        try:
            names = await oll_list_models()
            ollama_models = [{"id": f"ollama/{name}", "name": name} for name in names]
        except Exception as exc:
            logger.warning("Ollama model list failed: %s", exc)

    return {
        "openrouter": {"available": openrouter_available and bool(openrouter_models), "models": openrouter_models},
        "ollama": {"available": ollama_available, "models": ollama_models},
    }


@router.post("/chat")
async def chat(req: ChatRequest):
    thread_id = _resolve_thread_id(req)
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
    history_text = _history_context(thread.get("messages", []))
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
                role_overrides=_role_overrides(model_id),
                has_strategy_source=bool(context_bundle.snapshot.get("strategy_config")),
            ):
                if chunk.get("error"):
                    yield _sse_line({"error": chunk["error"], "done": True})
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
                        meta=_assistant_meta(
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
                    final_chunk = dict(chunk)
                    final_chunk["thread_id"] = thread_id
                    final_chunk["conversation_id"] = thread_id
                    yield _sse_line(final_chunk)
                    return
                yield _sse_line(chunk)
        except Exception as exc:
            logger.error("Chat stream error for thread %s: %s", thread_id, exc)
            yield _sse_line({"error": str(exc), "done": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/threads")
async def list_threads_endpoint():
    return [_thread_summary(thread) for thread in list_threads(limit=50)]


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    _validate_thread_id_http(thread_id)
    thread = load_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/threads/{thread_id}")
async def delete_thread_endpoint(thread_id: str):
    _validate_thread_id_http(thread_id)
    deleted = delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"deleted": thread_id}


@router.post("/threads/{thread_id}/messages")
async def append_thread_message(thread_id: str, req: ThreadMessageAppendRequest):
    _validate_thread_id_http(thread_id)
    return append_message(
        thread_id,
        req.role,
        req.content,
        meta=req.meta,
        goal_id=req.goal_id,
        provider=req.provider,
        model=req.model,
        context_run_id=req.context_run_id,
        context_mode=req.context_mode,
    )


@router.get("/conversations")
async def list_conversations_endpoint():
    return await list_threads_endpoint()


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    return await get_thread(conv_id)


@router.delete("/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: str):
    return await delete_thread_endpoint(conv_id)


@router.post("/analyze/{run_id}")
async def analyze_run(run_id: str):
    from app.services.storage import load_run_results, load_run_meta

    meta = load_run_meta(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    results = load_run_results(run_id) or {}
    run_data = {**results, "strategy": meta.get("strategy", "")}

    try:
        analysis = analyze(run_data, run_id=run_id)
        return analysis
    except Exception as exc:
        logger.error("Deep analysis failed for run %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.get("/pipeline-logs")
async def get_pipeline_logs():
    from app.ai.pipelines.orchestrator import list_pipeline_logs
    return list_pipeline_logs(limit=50)
