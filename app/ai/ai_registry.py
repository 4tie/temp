"""
AI Model Registry — fetches free models from OpenRouter + Ollama, assigns roles.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ROLE_PREFERENCES: dict[str, list[str]] = {
    "classifier": [
        "meta-llama/llama-3.2-1b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-2-2b-it:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "reasoner": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
    ],
    "code_gen": [
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
    ],
    "analyst_a": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
    ],
    "analyst_b": [
        "deepseek/deepseek-r1:free",
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ],
    "judge": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.1-70b-instruct:free",
    ],
    "composer": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
    ],
    "explainer": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
    ],
}

_FALLBACK_MODEL = "meta-llama/llama-3.2-1b-instruct:free"


async def fetch_free_models(provider: str = "openrouter") -> list[dict]:
    models: list[dict] = []

    if provider in ("openrouter", "all"):
        from .openrouter_client import list_models as or_list
        try:
            or_models = await or_list()
            for m in or_models:
                mid = m.get("id", "")
                pricing = m.get("pricing", {})
                if mid.endswith(":free") or str(pricing.get("prompt", "1")) == "0":
                    models.append({
                        "id": mid,
                        "name": m.get("name", mid),
                        "provider": "openrouter",
                        "context_length": m.get("context_length", 4096),
                    })
        except Exception as exc:
            logger.warning("OpenRouter model fetch failed: %s", exc)

    if provider in ("ollama", "all"):
        from .ollama_client import is_available, list_models as oll_list
        try:
            if await is_available():
                oll_models = await oll_list()
                for name in oll_models:
                    models.append({
                        "id": f"ollama/{name}",
                        "name": name,
                        "provider": "ollama",
                        "context_length": 4096,
                    })
        except Exception as exc:
            logger.debug("Ollama model fetch failed: %s", exc)

    return models


def get_model_for_role(
    role: str,
    models: list[dict],
    overrides: dict[str, str] | None = None,
) -> tuple[str, str]:
    if overrides and role in overrides:
        return overrides[role], f"override:{role}"

    available_ids = {m["id"] for m in models}
    preferences = ROLE_PREFERENCES.get(role, ROLE_PREFERENCES.get("explainer", []))

    for preferred in preferences:
        if preferred in available_ids:
            return preferred, f"preferred:{role}"

    if available_ids:
        chosen = next(iter(available_ids))
        return chosen, f"fallback:first-available"

    return _FALLBACK_MODEL, "fallback:hardcoded"
