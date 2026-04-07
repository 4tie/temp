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
_LAST_GOOD_BASE_URL: str | None = None


# V2 implementation: single-attempt calls; retry/fallback handled by dispatch.
def current_base_url() -> str:
    raw = os.environ.get("OLLAMA_BASE_URL", _BASE_URL) or _BASE_URL
    value = str(raw).strip().strip('"').strip("'")
    if not value:
        value = _BASE_URL
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value.rstrip("/")


def _candidate_base_urls() -> list[str]:
    base = current_base_url()
    candidates = [base]
    if "localhost" in base:
        candidates.append(base.replace("localhost", "127.0.0.1"))
    elif "127.0.0.1" in base:
        candidates.append(base.replace("127.0.0.1", "localhost"))
    # Preserve order and uniqueness.
    out: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


async def _probe(url: str, *, timeout: float = 3) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=True) as client:
            resp = await client.get(f"{url}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def _resolve_live_base_url() -> str | None:
    global _LAST_GOOD_BASE_URL
    if _LAST_GOOD_BASE_URL and await _probe(_LAST_GOOD_BASE_URL):
        return _LAST_GOOD_BASE_URL
    for url in _candidate_base_urls():
        if await _probe(url):
            _LAST_GOOD_BASE_URL = url
            return url
    return None


async def is_available() -> bool:
    return (await _resolve_live_base_url()) is not None


async def list_models() -> list[str]:
    base_url = await _resolve_live_base_url()
    if not base_url:
        return []
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False, follow_redirects=True) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [model["name"] for model in data.get("models", [])]
    except Exception as exc:
        logger.debug("Ollama list_models failed: %s", exc)
        return []


async def default_model() -> str | None:
    models = await list_models()
    return models[0] if models else None


async def chat_complete(messages: list[dict], model: str) -> str:
    base_url = await _resolve_live_base_url()
    if not base_url:
        raise RuntimeError(
            "Ollama is not reachable. Check OLLAMA_BASE_URL and ensure Ollama is running."
        )
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=120, trust_env=False, follow_redirects=True) as client:
        resp = await client.post(f"{base_url}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


async def stream_chat(
    messages: list[dict],
    model: str,
) -> AsyncGenerator[dict, None]:
    base_url = await _resolve_live_base_url()
    if not base_url:
        raise RuntimeError(
            "Ollama is not reachable. Check OLLAMA_BASE_URL and ensure Ollama is running."
        )
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=120, trust_env=False, follow_redirects=True) as client:
        async with client.stream(
            "POST",
            f"{base_url}/api/chat",
            json=payload,
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
