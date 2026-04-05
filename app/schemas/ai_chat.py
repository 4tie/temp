from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    thread_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message: str
    provider: str = "openrouter"
    model: Optional[str] = None
    goal_id: Optional[str] = None
    context_run_id: Optional[str] = None


class ChatResponse(BaseModel):
    thread_id: str
    conversation_id: str
    message: ChatMessage
    pipeline: Optional[dict] = None


class ConversationSummary(BaseModel):
    thread_id: Optional[str] = None
    conversation_id: str
    title: str
    preview: Optional[str] = None
    created_at: str
    updated_at: str
    message_count: int
    provider: str
    model: Optional[str] = None
    goal_id: Optional[str] = None
    context_run_id: Optional[str] = None
    context_mode: Optional[str] = None


class ThreadMessageAppendRequest(BaseModel):
    role: str
    content: str
    meta: Optional[dict[str, Any]] = None
    goal_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    context_run_id: Optional[str] = None
    context_mode: Optional[str] = None
