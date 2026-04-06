"""
AI Chat Router package.
Split from monolithic router into focused modules.
"""
from __future__ import annotations

import threading

from fastapi import APIRouter

from app.ai.context_builder import build_context_bundle
from app.ai.memory.threads import append_message, list_threads, load_thread, validate_thread_id
from app.ai.models.ollama_client import is_available, list_models as oll_list_models
from app.ai.models.openrouter_client import has_api_keys, list_models as or_list_models
from app.ai.pipelines.orchestrator import stream_run
from app.core.config import AI_LOOP_REPORTS_DIR
from app.services.ai_chat.loop_service import (
    LOOP_EVENTS,
    LOOP_SESSIONS,
    LOOP_STATE_DIR,
    LOOP_STATE_FILE,
    load_loop_state,
)
from app.services.ai_chat.apply_code_service import (
    extract_code_blocks_with_hints as _extract_code_blocks_with_hints,
)

from .chat_stream import router as chat_stream_router, chat, analyze_run, get_pipeline_logs
from .providers import router as providers_router, get_providers
from .threads import (
    router as threads_router,
    append_thread_message,
    delete_conversation_endpoint,
    delete_thread_endpoint,
    get_conversation,
    get_thread,
    list_conversations_endpoint,
    list_threads_endpoint,
)
from .apply_code import router as apply_code_router, apply_code
from .loop_sessions import (
    router as loop_sessions_router,
    loop_confirm_rerun,
    loop_metrics,
    loop_start,
    loop_stop,
    loop_stream,
    list_loop_sessions,
)
from .reports import router as reports_router, loop_report, loop_report_download

router = APIRouter(prefix="/ai", tags=["ai"])
router.include_router(providers_router)
router.include_router(chat_stream_router)
router.include_router(threads_router)
router.include_router(apply_code_router)
router.include_router(loop_sessions_router)
router.include_router(reports_router)

# Compatibility exports for existing tests/callers.
threading = threading

load_loop_state()

__all__ = [
    "router",
    "get_providers",
    "chat",
    "list_threads_endpoint",
    "get_thread",
    "delete_thread_endpoint",
    "append_thread_message",
    "apply_code",
    "loop_start",
    "loop_confirm_rerun",
    "loop_stop",
    "loop_stream",
    "loop_report",
    "loop_report_download",
    "loop_metrics",
    "list_loop_sessions",
    "list_conversations_endpoint",
    "get_conversation",
    "delete_conversation_endpoint",
    "analyze_run",
    "get_pipeline_logs",
    "_extract_code_blocks_with_hints",
    "_LOOP_SESSIONS",
    "_LOOP_EVENTS",
    "_LOOP_STATE_DIR",
    "_LOOP_STATE_FILE",
]

# Preserve legacy names expected by tests.
_LOOP_SESSIONS = LOOP_SESSIONS
_LOOP_EVENTS = LOOP_EVENTS
_LOOP_STATE_DIR = LOOP_STATE_DIR
_LOOP_STATE_FILE = LOOP_STATE_FILE
