from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.ai_chat import ThreadMessageAppendRequest
from app.ai.memory.threads import append_message, delete_thread, list_threads, load_thread
from app.services.ai_chat.thread_service import thread_summary, validate_thread_id_http

router = APIRouter()


@router.get("/threads")
async def list_threads_endpoint():
    return [thread_summary(thread) for thread in list_threads(limit=50)]


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    validate_thread_id_http(thread_id)
    thread = load_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/threads/{thread_id}")
async def delete_thread_endpoint(thread_id: str):
    validate_thread_id_http(thread_id)
    deleted = delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"deleted": thread_id}


@router.post("/threads/{thread_id}/messages")
async def append_thread_message(thread_id: str, req: ThreadMessageAppendRequest):
    validate_thread_id_http(thread_id)
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
