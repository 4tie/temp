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

_DEFAULT_HTTP_REFERER = os.environ.get("OPENROUTER_HTTP_REFERER", "https://4tie.local").strip() or "https://4tie.local"
_DEFAULT_APP_TITLE = os.environ.get("OPENROUTER_APP_TITLE", "4tie").strip() or "4tie"

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
        "HTTP-Referer": _DEFAULT_HTTP_REFERER,
        "X-Title": _DEFAULT_APP_TITLE,
    }


def _extract_error_detail(resp: httpx.Response | None) -> str:
    if resp is None:
        return ""
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                msg = err.get("message") or err.get("code")
                if msg:
                    return str(msg)
            if payload.get("message"):
                return str(payload.get("message"))
        text = resp.text.strip()
        return text[:300]
    except Exception:
        return ""


def _raise_with_detail(exc: httpx.HTTPStatusError, context: str) -> None:
    status = exc.response.status_code if exc.response is not None else "unknown"
    detail = _extract_error_detail(exc.response)
    retry_after = ""
    if exc.response is not None:
        ra = exc.response.headers.get("Retry-After")
        if ra:
            retry_after = f" retry_after={ra}s"
    if detail:
        raise RuntimeError(f"{context} failed (status={status}{retry_after}): {detail}") from exc
    raise RuntimeError(f"{context} failed (status={status}{retry_after})") from exc


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
            for key in keys:
                try:
                    resp = await client.get(f"{_BASE_URL}/models", headers=_headers_for(key))
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
                        logger.warning("OpenRouter model list auth failed for one key: %s", exc)
                        continue
                    if status == 429:
                        logger.warning("OpenRouter model list rate-limited for one key: %s", exc)
                        continue
                    logger.warning("OpenRouter model list failed for one key: %s", exc)
                    continue
            _MODELS_CACHE = []
            _MODELS_CACHE_TS = 0.0
            return []
    except Exception as exc:
        logger.warning("OpenRouter model list failed: %s", exc)
        return _MODELS_CACHE or []


async def chat_complete(messages: list[dict], model: str, *, api_key: str | None = None) -> str:
    model = ensure_free_model(model)
    validate_free_model(model)
    keys = get_api_keys()
    selected_key = api_key or (keys[0] if keys else "")
    if not selected_key:
        raise RuntimeError("OPENROUTER_API_KEY(S) not set")

    payload = {
        "model": model,
        "messages": messages,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                f"{_BASE_URL}/chat/completions",
                headers=_headers_for(selected_key),
                json=payload,
            )
            resp.raise_for_status()
            try:
                payload_json = resp.json()
                return payload_json["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError("OpenRouter chat_complete returned malformed payload: missing choices") from exc
        except httpx.HTTPStatusError as exc:
            _raise_with_detail(exc, "OpenRouter chat_complete")


async def stream_chat(
    messages: list[dict],
    model: str,
    *,
    api_key: str | None = None,
) -> AsyncGenerator[dict, None]:
    model = ensure_free_model(model)
    validate_free_model(model)
    keys = get_api_keys()
    selected_key = api_key or (keys[0] if keys else "")
    if not selected_key:
        raise RuntimeError("OPENROUTER_API_KEY(S) not set")

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        try:
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
                        try:
                            delta = chunk["choices"][0]["delta"].get("content", "")
                        except (KeyError, IndexError, TypeError) as exc:
                            raise RuntimeError("OpenRouter stream_chat returned malformed payload: missing choices") from exc
                        if delta:
                            yield {"delta": delta, "done": False}
                    except RuntimeError:
                        raise
                    except Exception:
                        continue
        except httpx.HTTPStatusError as exc:
            _raise_with_detail(exc, "OpenRouter stream_chat")
    yield {"done": True}


async def test_api_key(api_key: str) -> dict[str, bool | str]:
    """
    Test an OpenRouter API key by making a minimal request.
    Returns {"valid": bool, "error": str or None}
    """
    if not api_key or not api_key.strip():
        return {"valid": False, "error": "API key is empty"}
    
    api_key = api_key.strip()
    
    # Use a simple model list request to test the key
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        try:
            resp = await client.get(
                f"{_BASE_URL}/models",
                headers=_headers_for(api_key),
            )
            resp.raise_for_status()
            return {"valid": True, "error": None}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                return {"valid": False, "error": "Invalid API key"}
            elif exc.response.status_code == 429:
                return {"valid": False, "error": "Rate limited"}
            else:
                return {"valid": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:100]}"}
        except httpx.TimeoutException:
            return {"valid": False, "error": "Request timeout"}
        except Exception as exc:
            return {"valid": False, "error": f"Connection error: {str(exc)}"}
