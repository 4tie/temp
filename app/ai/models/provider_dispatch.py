"""
Provider dispatch — routes chat_complete and stream_chat to either
OpenRouter or Ollama based on provider name and model ID.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

_OLLAMA_PREFIX = "ollama/"


def _is_ollama_model(model: str) -> bool:
    return model.startswith(_OLLAMA_PREFIX)


def _strip_ollama_prefix(model: str) -> str:
    return model[len(_OLLAMA_PREFIX):]


async def chat_complete(messages: list[dict], model: str, provider: str = "openrouter") -> str:
    if provider == "ollama" or _is_ollama_model(model):
        from .ollama_client import chat_complete as oll_chat
        m = _strip_ollama_prefix(model) if _is_ollama_model(model) else model
        return await oll_chat(messages, m)
    else:
        from .openrouter_client import chat_complete as or_chat
        return await or_chat(messages, model)


async def stream_chat(
    messages: list[dict], model: str, provider: str = "openrouter"
) -> AsyncGenerator[dict, None]:
    if provider == "ollama" or _is_ollama_model(model):
        from .ollama_client import stream_chat as oll_stream
        m = _strip_ollama_prefix(model) if _is_ollama_model(model) else model
        async for chunk in oll_stream(messages, m):
            yield chunk
    else:
        from .openrouter_client import stream_chat as or_stream
        async for chunk in or_stream(messages, model):
            yield chunk
