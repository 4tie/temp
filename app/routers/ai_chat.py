"""
AI Chat Router — REST + SSE endpoints for the AI subsystem.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import AI_CONVERSATIONS_DIR
from app.schemas.ai_chat import ChatRequest, ChatResponse, ChatMessage, ConversationSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

_SAFE_CONV_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


# ─────────────────────────────────────────────────────────────────────────────
# Conversation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate_conv_id(conv_id: str) -> str:
    if not conv_id or not _SAFE_CONV_ID_RE.match(conv_id):
        raise HTTPException(status_code=400, detail=f"Invalid conversation ID: {conv_id!r}")
    resolved = (AI_CONVERSATIONS_DIR / f"{conv_id}.json").resolve()
    if not str(resolved).startswith(str(AI_CONVERSATIONS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal detected in conversation ID")
    return conv_id


def _conv_path(conv_id: str) -> Path:
    return AI_CONVERSATIONS_DIR / f"{conv_id}.json"


def _load_conv(conv_id: str) -> dict | None:
    _validate_conv_id(conv_id)
    p = _conv_path(conv_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_conv(conv: dict) -> None:
    _validate_conv_id(conv["conversation_id"])
    p = _conv_path(conv["conversation_id"])
    p.write_text(json.dumps(conv, indent=2, default=str), encoding="utf-8")


def _new_conv(conv_id: str, provider: str, model: str | None, goal_id: str | None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "conversation_id": conv_id,
        "title": "New conversation",
        "created_at": now,
        "updated_at": now,
        "provider": provider,
        "model": model,
        "goal_id": goal_id,
        "messages": [],
    }


def _build_context_from_run(run_id: str) -> str:
    try:
        from app.services.storage import load_run_results, load_run_meta
        meta = load_run_meta(run_id) or {}
        results = load_run_results(run_id) or {}
        parts = []
        if meta:
            parts.append(f"Backtest run: {run_id}")
            parts.append(f"Strategy: {meta.get('strategy', 'unknown')}")
            parts.append(f"Status: {meta.get('status', 'unknown')}")
        if results:
            summary = results.get("summary", {})
            if summary:
                parts.append(f"Summary: {json.dumps(summary)}")
        return "\n".join(parts)
    except Exception as exc:
        logger.debug("Failed to load run context: %s", exc)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# SSE helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sse_line(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/providers")
async def get_providers():
    from app.ai.openrouter_client import list_models as or_list_models
    from app.ai.ollama_client import is_available as oll_available, list_models as oll_list_models
    import os

    or_key = bool(os.environ.get("OPENROUTER_API_KEY", ""))
    or_models = []
    if or_key:
        try:
            raw = await or_list_models()
            or_models = [{"id": m["id"], "name": m.get("name", m["id"])} for m in raw[:50]]
        except Exception as exc:
            logger.warning("OpenRouter model list failed: %s", exc)

    oll_avail = await oll_available()
    oll_models = []
    if oll_avail:
        try:
            names = await oll_list_models()
            oll_models = [{"id": f"ollama/{n}", "name": n} for n in names]
        except Exception as exc:
            logger.warning("Ollama model list failed: %s", exc)

    return {
        "openrouter": {
            "available": or_key,
            "models": or_models,
        },
        "ollama": {
            "available": oll_avail,
            "models": oll_models,
        },
    }


@router.post("/chat")
async def chat(req: ChatRequest):
    conv_id = req.conversation_id or str(uuid.uuid4())
    conv = _load_conv(conv_id) or _new_conv(conv_id, req.provider, req.model, req.goal_id)

    conv["messages"].append({"role": "user", "content": req.message})

    context = ""
    if req.context_run_id:
        context = _build_context_from_run(req.context_run_id)

    history = conv["messages"][:-1]

    async def event_stream() -> AsyncGenerator[str, None]:
        nonlocal conv

        import os
        if req.provider == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
            yield _sse_line({"error": "OPENROUTER_API_KEY is not configured. Please set it in environment secrets.", "done": True})
            return
        if req.provider == "ollama":
            from app.ai.ollama_client import is_available as oll_check
            if not await oll_check():
                yield _sse_line({"error": "Ollama is not available. Please ensure Ollama is running locally.", "done": True})
                return

        try:
            from app.ai.ai_orchestrator import stream_run

            pipeline_history = "\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in history[-10:]
            )
            full_context = context
            if pipeline_history:
                full_context = f"{pipeline_history}\n\n{full_context}" if full_context else pipeline_history

            full_text = ""
            pipeline_info = None

            role_overrides: dict[str, str] | None = None
            if req.model:
                role_overrides = {
                    "reasoner": req.model,
                    "analyst_a": req.model,
                    "analyst_b": req.model,
                    "composer": req.model,
                    "explainer": req.model,
                    "code_gen": req.model,
                }

            async for chunk in stream_run(
                task_text=req.message,
                context=full_context,
                goal_id=req.goal_id,
                provider=req.provider,
                role_overrides=role_overrides,
            ):
                if chunk.get("error"):
                    yield _sse_line({"error": chunk["error"], "done": True})
                    return
                if chunk.get("status"):
                    yield _sse_line({"status": chunk["status"], "done": False})
                if chunk.get("delta"):
                    full_text += chunk["delta"]
                    yield _sse_line({"delta": chunk["delta"], "done": False})
                if chunk.get("done"):
                    pipeline_info = chunk.get("pipeline")
                    if not full_text and chunk.get("fullText"):
                        full_text = chunk["fullText"]
                    break

            conv["messages"].append({"role": "assistant", "content": full_text})
            conv["updated_at"] = datetime.now(timezone.utc).isoformat()
            if conv["title"] == "New conversation" and req.message:
                conv["title"] = req.message[:60]
            _save_conv(conv)

            yield _sse_line({
                "done": True,
                "conversation_id": conv_id,
                "pipeline": pipeline_info,
            })

        except Exception as exc:
            logger.error("Chat stream error: %s", exc)
            yield _sse_line({"error": str(exc), "done": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations")
async def list_conversations():
    convs = []
    if not AI_CONVERSATIONS_DIR.exists():
        return convs
    files = sorted(
        AI_CONVERSATIONS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:50]
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            convs.append(ConversationSummary(
                conversation_id=data.get("conversation_id", f.stem),
                title=data.get("title", "Untitled"),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                message_count=len(data.get("messages", [])),
                provider=data.get("provider", "openrouter"),
                model=data.get("model"),
                goal_id=data.get("goal_id"),
            ))
        except Exception:
            continue
    return convs


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = _load_conv(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    p = _conv_path(conv_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Conversation not found")
    p.unlink()
    return {"deleted": conv_id}


@router.post("/analyze/{run_id}")
async def analyze_run(run_id: str):
    from app.services.storage import load_run_results, load_run_meta
    from app.ai.deep_analysis import analyze

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
    from app.ai.ai_orchestrator import list_pipeline_logs
    return list_pipeline_logs(limit=50)
