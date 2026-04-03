"""
Ollama client — local model inference.
Gracefully skips when Ollama is not running.
"""
from __future__ import annotations

import json
import logging
import os
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


async def is_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{_BASE_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def list_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{_BASE_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception as exc:
        logger.debug("Ollama list_models failed: %s", exc)
        return []


async def chat_complete(messages: list[dict], model: str) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
    except Exception as exc:
        logger.error("Ollama chat_complete failed: %s", exc)
        raise


async def stream_chat(
    messages: list[dict], model: str
) -> AsyncGenerator[dict, None]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", f"{_BASE_URL}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        delta = chunk.get("message", {}).get("content", "")
                        if delta:
                            yield {"delta": delta, "done": False}
                        if chunk.get("done"):
                            yield {"done": True}
                            return
                    except Exception:
                        continue
    except Exception as exc:
        logger.error("Ollama stream_chat error: %s", exc)
        yield {"error": str(exc), "done": True}
