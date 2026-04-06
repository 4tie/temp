from __future__ import annotations

from fastapi import APIRouter

from app.schemas.ai_chat import ApplyCodeRequest
from app.services.ai_chat.apply_code_service import apply_code_impl
from app.services.ai_chat.thread_service import validate_thread_id_http

router = APIRouter()


@router.post("/chat/apply-code")
async def apply_code(req: ApplyCodeRequest):
    thread_id = validate_thread_id_http(req.thread_id)
    result = apply_code_impl(
        thread_id=thread_id,
        assistant_message_id=req.assistant_message_id,
        code_block_index=req.code_block_index,
        fallback_strategy=req.fallback_strategy,
    )
    result.pop("_old_source", None)
    return result
