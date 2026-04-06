"""AI chat router package."""
from __future__ import annotations

from fastapi import APIRouter

from .apply_code import router as apply_code_router
from .chat_stream import router as chat_stream_router
from .loop_sessions import router as loop_sessions_router
from .providers import router as providers_router
from .reports import router as reports_router
from .threads import router as threads_router

router = APIRouter(prefix="/ai", tags=["ai"])
router.include_router(providers_router)
router.include_router(chat_stream_router)
router.include_router(threads_router)
router.include_router(apply_code_router)
router.include_router(loop_sessions_router)
router.include_router(reports_router)

__all__ = ["router"]
