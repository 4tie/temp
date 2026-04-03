"""
OpenRouter client — free models only.
Appends :free suffix when absent; rejects non-free models.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://openrouter.ai/api/v1"
_MODELS_CACHE: list[dict] = []
_MODELS_CACHE_TS: float = 0.0
_MODELS_CACHE_TTL = 300


def _api_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://replit.com",
        "X-Title": "4tie",
    }


def _ensure_free(model: str) -> str:
    if not model.endswith(":free"):
        return model + ":free"
    return model


async def list_models() -> list[dict]:
    global _MODELS_CACHE, _MODELS_CACHE_TS
    now = time.monotonic()
    if _MODELS_CACHE and (now - _MODELS_CACHE_TS) < _MODELS_CACHE_TTL:
        return _MODELS_CACHE

    key = _api_key()
    if not key:
        return []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{_BASE_URL}/models", headers=_headers())
            resp.raise_for_status()
            data = resp.json().get("data", [])
            free = [
                m for m in data
                if m.get("id", "").endswith(":free")
                or str(m.get("pricing", {}).get("prompt", "1")) == "0"
            ]
            _MODELS_CACHE = free
            _MODELS_CACHE_TS = now
            return free
    except Exception as exc:
        logger.warning("OpenRouter model list failed: %s", exc)
        return _MODELS_CACHE or []


def _validate_free_model(model: str) -> None:
    if not model.endswith(":free"):
        raise ValueError(
            f"Model '{model}' is not a free-tier model. Only :free suffix models are permitted."
        )


async def chat_complete(messages: list[dict], model: str) -> str:
    model = _ensure_free(model)
    _validate_free_model(model)
    key = _api_key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    payload = {
        "model": model,
        "messages": messages,
    }

    delay = 1.0
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{_BASE_URL}/chat/completions",
                    headers=_headers(),
                    json=payload,
                )
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", delay))
                    logger.warning("Rate limited; retrying after %.1fs", retry_after)
                    await asyncio.sleep(retry_after)
                    delay *= 2
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            if attempt == 2:
                raise
            logger.warning("OpenRouter attempt %d failed: %s", attempt + 1, exc)
            await asyncio.sleep(delay)
            delay *= 2

    raise RuntimeError(f"OpenRouter chat_complete failed after 3 attempts for model {model}")


async def stream_chat(
    messages: list[dict], model: str
) -> AsyncGenerator[dict, None]:
    model = _ensure_free(model)
    try:
        _validate_free_model(model)
    except ValueError as e:
        yield {"error": str(e), "done": True}
        return

    key = _api_key()
    if not key:
        yield {"error": "OPENROUTER_API_KEY not set", "done": True}
        return

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                f"{_BASE_URL}/chat/completions",
                headers=_headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        yield {"done": True}
                        return
                    try:
                        import json
                        chunk = json.loads(raw)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield {"delta": delta, "done": False}
                    except Exception:
                        continue
        yield {"done": True}
    except Exception as e:
        logger.error("OpenRouter stream failed: %s", e)
        yield {"error": str(e), "done": True}
