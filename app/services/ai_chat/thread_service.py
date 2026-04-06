from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException

from app.schemas.ai_chat import ChatRequest, ConversationSummary
from app.ai.memory.threads import validate_thread_id


def validate_thread_id_http(thread_id: str) -> str:
    try:
        return validate_thread_id(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def thread_summary(thread: dict[str, Any]) -> ConversationSummary:
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


def history_context(messages: list[dict[str, Any]], limit: int = 12) -> str:
    lines = []
    for message in messages[-limit:]:
        role = str(message.get("role", "user")).upper()
        content = str(message.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def resolve_thread_id(req: ChatRequest) -> str:
    return req.thread_id or req.conversation_id or str(uuid.uuid4())


def role_overrides(model_id: str | None) -> dict[str, str] | None:
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


def assistant_meta(
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
