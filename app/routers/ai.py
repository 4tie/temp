"""AI Chat router — SSE streaming, conversations, deep analysis."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ai.models.openrouter_client import (
    list_models as fetch_openrouter_models,
    stream_chat,
    chat_complete,
)
from app.ai.models.ollama_client import (
    list_models as _oll_list_models,
    is_available as check_ollama_status,
)
from app.ai.conversation_store import (
    list_conversations, get_conversation, create_conversation,
    append_message, delete_conversation,
)
from app.services.storage import list_runs, load_run_results, load_run_meta


async def fetch_ollama_models() -> list[dict]:
    names = await _oll_list_models()
    return [{"name": n} for n in names]

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


# ─── Provider/Model endpoints ────────────────────────────────────────────────

@router.get("/providers")
async def get_providers():
    """Return provider status + available models."""
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    ollama_online = await check_ollama_status()
    ollama_models = []
    openrouter_models = []

    if ollama_online:
        raw = await fetch_ollama_models()
        ollama_models = [{"id": m["name"], "name": m["name"]} for m in raw]

    if openrouter_key:
        raw = await fetch_openrouter_models()
        openrouter_models = [
            {"id": m["id"], "name": m.get("name", m["id"])}
            for m in raw[:60]
        ]

    return {
        "providers": {
            "ollama": {
                "available": ollama_online,
                "models": ollama_models,
            },
            "openrouter": {
                "available": bool(openrouter_key),
                "models": openrouter_models,
            },
        }
    }


# ─── Conversation endpoints ───────────────────────────────────────────────────

@router.get("/conversations")
async def get_conversations():
    return list_conversations()


@router.get("/conversations/{conv_id}")
async def get_conversation_detail(conv_id: str = Path(...)):
    conv = get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/conversations/{conv_id}")
async def delete_conv(conv_id: str = Path(...)):
    if not delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


# ─── Chat (SSE stream) ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    provider: str = "openrouter"
    model: Optional[str] = None
    goal: Optional[str] = None
    context_run_id: Optional[str] = None
    strategy_name: Optional[str] = None


async def _build_context(run_id: str | None) -> tuple[str, dict | None]:
    """Build context string from a backtest run."""
    if not run_id:
        return "", None
    try:
        meta = load_run_meta(run_id)
        results = load_run_results(run_id)
        if not results:
            return "", None
        summary = results.get("summary", {})
        ctx_parts = []
        if meta:
            ctx_parts.append(f"Strategy: {meta.get('strategy', 'unknown')}")
            ctx_parts.append(f"Timeframe: {meta.get('timeframe', '')}")
        ctx_parts.append(f"Total Profit: {summary.get('profit_total_pct', 0):.2f}%")
        ctx_parts.append(f"Win Rate: {summary.get('win_rate', 0):.1%}")
        ctx_parts.append(f"Max Drawdown: {summary.get('max_drawdown_pct', 0):.2f}%")
        ctx_parts.append(f"Total Trades: {summary.get('total_trades', 0)}")
        ctx_parts.append(f"Sharpe Ratio: {summary.get('sharpe_ratio', 'N/A')}")
        ctx_parts.append(f"Profit Factor: {summary.get('profit_factor', 'N/A')}")
        return "\n".join(ctx_parts), {"run_id": run_id, "strategy": meta.get("strategy") if meta else ""}
    except Exception as e:
        logger.warning("Could not build context for run %s: %s", run_id, e)
        return "", None


async def _sse_generator(
    request: ChatRequest,
    conv_id: str,
) -> AsyncGenerator[str, None]:
    def sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    context, ctx_meta = await _build_context(request.context_run_id)

    # Build messages for AI — include conversation history
    conv = get_conversation(conv_id)
    messages: list[dict] = []

    # System message
    system_parts = [
        "You are an expert FreqTrade trading strategy analyst.",
        "Provide clear, evidence-based analysis with specific numbers and actionable recommendations.",
    ]
    if context:
        system_parts.append(f"\nBacktest Context:\n{context}")

    if request.goal and request.goal != "auto":
        goal_labels = {
            "lower_drawdown": "reduce drawdown",
            "higher_win_rate": "increase win rate",
            "higher_profit": "maximize profit",
            "more_trades": "increase trade frequency",
            "cut_losers": "cut losing trades",
            "lower_risk": "lower risk",
            "scalping": "optimize for scalping",
            "swing_trading": "optimize for swing trading",
            "compound_growth": "achieve compound growth",
        }
        goal_label = goal_labels.get(request.goal, request.goal)
        system_parts.append(f"\nUser Goal: {goal_label}. Focus your response on this goal.")

    messages.append({"role": "system", "content": "\n".join(system_parts)})

    # Add conversation history (last 10 exchanges)
    if conv and conv.get("messages"):
        for m in conv["messages"][-20:]:
            if m["role"] in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})

    # Add current user message
    messages.append({"role": "user", "content": request.message})

    # Save user message
    append_message(conv_id, "user", request.message)

    # Classify pipeline (simple detection without full AI classifier to avoid extra latency)
    msg_lower = request.message.lower()
    if any(w in msg_lower for w in ["write", "generate", "create strategy", "code", "python"]):
        pipeline_type = "code"
    elif any(w in msg_lower for w in ["compare", "versus", "vs ", "which is better", "debate"]):
        pipeline_type = "debate"
    elif any(w in msg_lower for w in ["analyze", "analyse", "deep", "explain", "why", "how does"]):
        pipeline_type = "analysis"
    else:
        pipeline_type = "simple"

    yield sse({"status": "classified", "pipeline_type": pipeline_type, "done": False})

    model = request.model or "meta-llama/llama-3.2-3b-instruct:free"
    provider = request.provider

    full_text = ""
    start = time.monotonic()

    try:
        async for chunk in stream_chat(messages, model=model, provider=provider):
            if chunk.get("error"):
                yield sse({"error": chunk["error"], "done": True})
                return
            if chunk.get("delta"):
                full_text += chunk["delta"]
                yield sse({"delta": chunk["delta"], "done": False})
            if chunk.get("done") and not chunk.get("delta"):
                break
    except Exception as e:
        yield sse({"error": str(e), "done": True})
        return

    duration_ms = int((time.monotonic() - start) * 1000)

    # Save assistant message
    append_message(conv_id, "assistant", full_text, meta={
        "pipeline_type": pipeline_type,
        "model": model,
        "duration_ms": duration_ms,
        "context_run_id": request.context_run_id,
    })

    pipeline_info = {
        "pipeline_type": pipeline_type,
        "model": model,
        "duration_ms": duration_ms,
    }
    yield sse({"done": True, "fullText": full_text, "pipeline": pipeline_info, "conversation_id": conv_id})


@router.post("/chat")
async def chat(request: ChatRequest):
    # Create or resolve conversation
    conv_id = request.conversation_id
    if not conv_id:
        conv = create_conversation(strategy_name=request.strategy_name or "")
        conv_id = conv["id"]

    return StreamingResponse(
        _sse_generator(request, conv_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ─── Deep Analysis ────────────────────────────────────────────────────────────

@router.post("/analyze/{run_id}")
async def deep_analyze(run_id: str = Path(...)):
    """Run deep analysis on a backtest run."""
    try:
        meta = load_run_meta(run_id)
        results = load_run_results(run_id)
        if not results:
            raise HTTPException(status_code=404, detail="Run results not found")

        from app.ai.tools.deep_analysis import analyze as run_analysis
        result = run_analysis(results, run_id=run_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Deep analysis failed for run %s: %s", run_id, e)
        raise HTTPException(status_code=500, detail=str(e))
