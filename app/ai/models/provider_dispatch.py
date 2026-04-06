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


# V2 implementation: key rotation, retries, and OpenRouter -> Ollama fallback.
import asyncio as _asyncio
import contextvars as _contextvars
from itertools import count as _count
from typing import Awaitable as _Awaitable, Callable as _Callable

from .ollama_client import default_model as _ollama_default_model
from .ollama_client import list_models as _ollama_list_models
from .openrouter_client import ensure_free_model as _ensure_free_model
from .openrouter_client import get_api_keys as _get_openrouter_api_keys

_last_dispatch_meta: _contextvars.ContextVar[dict | None] = _contextvars.ContextVar(
    "last_dispatch_meta_v2",
    default=None,
)
_key_counter = _count()


def get_last_dispatch_meta() -> dict:
    return _last_dispatch_meta.get() or {}


def _sanitize_key_slot(index: int | None) -> str | None:
    if index is None:
        return None
    return f"openrouter-key-{index + 1}"


def _next_openrouter_key() -> tuple[str | None, int | None]:
    keys = _get_openrouter_api_keys()
    if not keys:
        return None, None
    index = next(_key_counter) % len(keys)
    return keys[index], index


def _is_retryable_provider_error(provider_name: str, error_text: str) -> bool:
    text = str(error_text or "").lower()
    if provider_name != "openrouter":
        return True
    if any(marker in text for marker in ("status=401", "status=403", "user not found", "no openrouter api keys configured")):
        return False
    if "malformed payload" in text or "missing choices" in text:
        return False
    return True


async def _retry_call_v2(
    provider_name: str,
    requested_model: str,
    actual_model: str,
    caller: _Callable[..., _Awaitable[str]],
    *,
    caller_kwargs: dict | None = None,
) -> tuple[str, dict]:
    caller_kwargs = caller_kwargs or {}
    attempts: list[dict] = []
    delay = 1.0

    for attempt in range(1, 4):
        key_slot = None
        try:
            if provider_name == "openrouter":
                api_key, key_index = _next_openrouter_key()
                if not api_key:
                    raise RuntimeError("No OpenRouter API keys configured")
                key_slot = _sanitize_key_slot(key_index)
                text = await caller(api_key=api_key, **caller_kwargs)
            else:
                text = await caller(**caller_kwargs)

            return text, {
                "requested_provider": provider_name,
                "requested_model": requested_model,
                "provider": provider_name,
                "model": actual_model,
                "attempt_count": attempt,
                "key_slot": key_slot,
                "attempts": attempts + [{
                    "provider": provider_name,
                    "model": actual_model,
                    "attempt": attempt,
                    "key_slot": key_slot,
                    "status": "success",
                }],
            }
        except Exception as exc:
            error_text = str(exc)
            retryable = _is_retryable_provider_error(provider_name, error_text)
            attempts.append({
                "provider": provider_name,
                "model": actual_model,
                "attempt": attempt,
                "key_slot": key_slot,
                "status": "error",
                "error": error_text,
                "retryable": retryable,
            })
            if retryable and attempt < 3:
                logger.debug("%s attempt %d failed for %s: %s", provider_name, attempt, actual_model, exc)
                await _asyncio.sleep(delay)
                delay *= 2
                continue
            if retryable:
                logger.warning("%s failed for %s after %d attempts: %s", provider_name, actual_model, attempt, exc)
            else:
                logger.warning("%s failed for %s without retry: %s", provider_name, actual_model, exc)
            break

    raise RuntimeError(str(attempts[-1]["error"]))


async def _stream_with_retries_v2(
    provider_name: str,
    requested_model: str,
    actual_model: str,
    caller: _Callable[..., AsyncGenerator[dict, None]],
    *,
    caller_kwargs: dict | None = None,
) -> AsyncGenerator[dict, None]:
    caller_kwargs = caller_kwargs or {}
    attempts: list[dict] = []
    delay = 1.0

    for attempt in range(1, 4):
        key_slot = None
        first_delta_seen = False
        try:
            if provider_name == "openrouter":
                api_key, key_index = _next_openrouter_key()
                if not api_key:
                    raise RuntimeError("No OpenRouter API keys configured")
                key_slot = _sanitize_key_slot(key_index)
                stream = caller(api_key=api_key, **caller_kwargs)
            else:
                stream = caller(**caller_kwargs)

            async for chunk in stream:
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                if chunk.get("delta"):
                    first_delta_seen = True
                    yield {"delta": chunk["delta"], "done": False}
                if chunk.get("done"):
                    attempts.append({
                        "provider": provider_name,
                        "model": actual_model,
                        "attempt": attempt,
                        "key_slot": key_slot,
                        "status": "success",
                    })
                    yield {
                        "done": True,
                        "meta": {
                            "requested_provider": provider_name,
                            "requested_model": requested_model,
                            "provider": provider_name,
                            "model": actual_model,
                            "attempt_count": attempt,
                            "key_slot": key_slot,
                            "attempts": attempts,
                        },
                    }
                    return
            attempts.append({
                "provider": provider_name,
                "model": actual_model,
                "attempt": attempt,
                "key_slot": key_slot,
                "status": "success",
            })
            yield {
                "done": True,
                "meta": {
                    "requested_provider": provider_name,
                    "requested_model": requested_model,
                    "provider": provider_name,
                    "model": actual_model,
                    "attempt_count": attempt,
                    "key_slot": key_slot,
                    "attempts": attempts,
                },
            }
            return
        except Exception as exc:
            error_text = str(exc)
            retryable = _is_retryable_provider_error(provider_name, error_text)
            attempts.append({
                "provider": provider_name,
                "model": actual_model,
                "attempt": attempt,
                "key_slot": key_slot,
                "status": "error",
                "error": error_text,
                "retryable": retryable,
            })
            if first_delta_seen:
                yield {"error": error_text, "done": True}
                return
            if retryable and attempt < 3:
                logger.debug("%s stream attempt %d failed for %s: %s", provider_name, attempt, actual_model, exc)
                await _asyncio.sleep(delay)
                delay *= 2
                continue
            if retryable:
                logger.warning("%s stream failed for %s after %d attempts: %s", provider_name, actual_model, attempt, exc)
            else:
                logger.warning("%s stream failed for %s without retry: %s", provider_name, actual_model, exc)
            raise RuntimeError(error_text)


async def _dispatch_ollama_model_v2(requested_model: str) -> str:
    if _is_ollama_model(requested_model):
        return _strip_ollama_prefix(requested_model)
    model = await _ollama_default_model()
    if model:
        return model
    models = await _ollama_list_models()
    if models:
        return models[0]
    raise RuntimeError("No Ollama models available for fallback")


def _finalize_meta_v2(
    requested_provider: str,
    requested_model: str,
    meta: dict,
    provider_attempts: list[dict],
    fallback_chain: list[str],
) -> dict:
    finalized = dict(meta)
    finalized["requested_provider"] = requested_provider
    finalized["requested_model"] = requested_model
    finalized["provider_attempts"] = provider_attempts + finalized.get("attempts", [])
    finalized["fallback_chain"] = fallback_chain + [f"{finalized['provider']}:{finalized['model']}"]
    finalized["fallback_used"] = len(finalized["fallback_chain"]) > 1 or finalized.get("attempt_count", 1) > 1
    _last_dispatch_meta.set(finalized)
    return finalized


async def chat_complete(messages: list[dict], model: str, provider: str = "openrouter") -> str:
    requested_provider = "ollama" if provider == "ollama" or _is_ollama_model(model) else "openrouter"
    requested_model = model
    provider_attempts: list[dict] = []
    fallback_chain: list[str] = []
    openrouter_error: str | None = None

    if requested_provider == "ollama":
        from .ollama_client import chat_complete as ollama_chat

        actual_model = await _dispatch_ollama_model_v2(model)
        text, meta = await _retry_call_v2(
            "ollama",
            requested_model,
            actual_model,
            ollama_chat,
            caller_kwargs={"messages": messages, "model": actual_model},
        )
        _finalize_meta_v2(requested_provider, requested_model, meta, provider_attempts, fallback_chain)
        return text

    from .openrouter_client import chat_complete as openrouter_chat

    actual_model = _ensure_free_model(model)
    try:
        text, meta = await _retry_call_v2(
            "openrouter",
            requested_model,
            actual_model,
            openrouter_chat,
            caller_kwargs={"messages": messages, "model": actual_model},
        )
        _finalize_meta_v2(requested_provider, requested_model, meta, provider_attempts, fallback_chain)
        return text
    except Exception as openrouter_exc:
        openrouter_error = str(openrouter_exc)
        provider_attempts.append({
            "provider": "openrouter",
            "model": actual_model,
            "status": "failed",
            "error": openrouter_error,
        })
        fallback_chain.append(f"openrouter:{actual_model}")
        logger.warning("OpenRouter failed for %s, falling back to Ollama: %s", actual_model, openrouter_exc)

    from .ollama_client import chat_complete as ollama_chat

    try:
        fallback_model = await _dispatch_ollama_model_v2(model)
    except Exception as fallback_exc:
        raise RuntimeError(
            f"OpenRouter failed for {actual_model}: {openrouter_error or 'unknown error'}. "
            f"Ollama fallback unavailable: {fallback_exc}"
        ) from fallback_exc

    text, meta = await _retry_call_v2(
        "ollama",
        requested_model,
        fallback_model,
        ollama_chat,
        caller_kwargs={"messages": messages, "model": fallback_model},
    )
    _finalize_meta_v2(requested_provider, requested_model, meta, provider_attempts, fallback_chain)
    return text


async def stream_chat(
    messages: list[dict],
    model: str,
    provider: str = "openrouter",
) -> AsyncGenerator[dict, None]:
    requested_provider = "ollama" if provider == "ollama" or _is_ollama_model(model) else "openrouter"
    requested_model = model

    if requested_provider == "ollama":
        from .ollama_client import stream_chat as ollama_stream

        actual_model = await _dispatch_ollama_model_v2(model)
        async for chunk in _stream_with_retries_v2(
            "ollama",
            requested_model,
            actual_model,
            ollama_stream,
            caller_kwargs={"messages": messages, "model": actual_model},
        ):
            if chunk.get("meta"):
                chunk["meta"] = _finalize_meta_v2(requested_provider, requested_model, chunk["meta"], [], [])
            yield chunk
        return

    from .openrouter_client import stream_chat as openrouter_stream

    actual_model = _ensure_free_model(model)
    openrouter_error: str | None = None
    try:
        async for chunk in _stream_with_retries_v2(
            "openrouter",
            requested_model,
            actual_model,
            openrouter_stream,
            caller_kwargs={"messages": messages, "model": actual_model},
        ):
            if chunk.get("meta"):
                chunk["meta"] = _finalize_meta_v2(requested_provider, requested_model, chunk["meta"], [], [])
            yield chunk
        return
    except Exception as openrouter_exc:
        openrouter_error = str(openrouter_exc)
        logger.warning("OpenRouter stream failed for %s, falling back to Ollama: %s", actual_model, openrouter_exc)

    openrouter_completion_error: str | None = None
    try:
        from .openrouter_client import chat_complete as openrouter_chat

        text, meta = await _retry_call_v2(
            "openrouter",
            requested_model,
            actual_model,
            openrouter_chat,
            caller_kwargs={"messages": messages, "model": actual_model},
        )
        finalized = _finalize_meta_v2(
            requested_provider,
            requested_model,
            meta,
            [{
                "provider": "openrouter",
                "model": actual_model,
                "status": "stream_failed",
                "error": openrouter_error or "stream_failed",
            }],
            [],
        )
        yield {"delta": text, "done": False}
        yield {"done": True, "meta": finalized}
        return
    except Exception as completion_exc:
        openrouter_completion_error = str(completion_exc)
        logger.warning(
            "OpenRouter non-stream fallback failed for %s: %s",
            actual_model,
            completion_exc,
        )

    from .ollama_client import stream_chat as ollama_stream

    try:
        fallback_model = await _dispatch_ollama_model_v2(model)
    except Exception as fallback_exc:
        parts = [f"OpenRouter stream failed for {actual_model}: {openrouter_error or 'unknown error'}"]
        if openrouter_completion_error:
            parts.append(f"OpenRouter non-stream fallback failed: {openrouter_completion_error}")
        parts.append(f"Ollama fallback unavailable: {fallback_exc}")
        yield {"error": " | ".join(parts), "done": True}
        return

    async for chunk in _stream_with_retries_v2(
        "ollama",
        requested_model,
        fallback_model,
        ollama_stream,
        caller_kwargs={"messages": messages, "model": fallback_model},
    ):
        if chunk.get("meta"):
            chunk["meta"] = _finalize_meta_v2(
                requested_provider,
                requested_model,
                chunk["meta"],
                [{
                    "provider": "openrouter",
                    "model": actual_model,
                    "status": "failed",
                    "error": "fallback_to_ollama",
                }],
                [f"openrouter:{actual_model}"],
            )
        yield chunk
