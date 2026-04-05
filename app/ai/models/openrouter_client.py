"""
OpenRouter client — free models only.
Appends :free suffix when absent; rejects non-free models.
"""
from __future__ import annotations

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

# V2 implementation: single-attempt calls with multi-key support.
def get_api_keys() -> list[str]:
    raw = os.environ.get("OPENROUTER_API_KEYS", "").strip()
    keys = [key.strip() for key in raw.split(",") if key.strip()]
    if not keys:
        single = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if single:
            keys = [single]
    return keys


def has_api_keys() -> bool:
    return bool(get_api_keys())


def ensure_free_model(model: str) -> str:
    if model.startswith("ollama/"):
        return model
    if not model.endswith(":free"):
        return f"{model}:free"
    return model


def validate_free_model(model: str) -> None:
    if not model.endswith(":free"):
        raise ValueError(
            f"Model '{model}' is not a free-tier model. Only :free suffix models are permitted."
        )


def _headers_for(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "",
        "X-Title": "4tie",
    }


async def list_models() -> list[dict]:
    global _MODELS_CACHE, _MODELS_CACHE_TS
    now = time.monotonic()
    if _MODELS_CACHE and (now - _MODELS_CACHE_TS) < _MODELS_CACHE_TTL:
        return _MODELS_CACHE

    keys = get_api_keys()
    if not keys:
        return []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{_BASE_URL}/models", headers=_headers_for(keys[0]))
            resp.raise_for_status()
            data = resp.json().get("data", [])
            free = [
                model for model in data
                if model.get("id", "").endswith(":free")
                or str(model.get("pricing", {}).get("prompt", "1")) == "0"
            ]
            _MODELS_CACHE = free
            _MODELS_CACHE_TS = now
            return free
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in (401, 403):
            _MODELS_CACHE = []
            _MODELS_CACHE_TS = 0.0
            logger.warning("OpenRouter model list auth failed: %s", exc)
            return []
        logger.warning("OpenRouter model list failed: %s", exc)
        return _MODELS_CACHE or []
    except Exception as exc:
        logger.warning("OpenRouter model list failed: %s", exc)
        return _MODELS_CACHE or []


async def chat_complete(messages: list[dict], model: str, *, api_key: str | None = None) -> str:
    model = ensure_free_model(model)
    validate_free_model(model)
    selected_key = api_key or (get_api_keys()[0] if get_api_keys() else "")
    if not selected_key:
        raise RuntimeError("OPENROUTER_API_KEY(S) not set")

    payload = {
        "model": model,
        "messages": messages,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{_BASE_URL}/chat/completions",
            headers=_headers_for(selected_key),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def stream_chat(
    messages: list[dict],
    model: str,
    *,
    api_key: str | None = None,
) -> AsyncGenerator[dict, None]:
    model = ensure_free_model(model)
    validate_free_model(model)
    selected_key = api_key or (get_api_keys()[0] if get_api_keys() else "")
    if not selected_key:
        raise RuntimeError("OPENROUTER_API_KEY(S) not set")

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        async with client.stream(
            "POST",
            f"{_BASE_URL}/chat/completions",
            headers=_headers_for(selected_key),
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
