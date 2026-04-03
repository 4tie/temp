from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    provider: str = "openrouter"
    model: Optional[str] = None
    goal_id: Optional[str] = None
    context_run_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    pipeline: Optional[dict] = None


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    provider: str
    model: Optional[str] = None
    goal_id: Optional[str] = None
