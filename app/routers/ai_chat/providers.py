from __future__ import annotations

from fastapi import APIRouter

from app.services.ai_chat.provider_service import get_providers_payload

router = APIRouter()


@router.get("/providers")
async def get_providers():
    return await get_providers_payload()
