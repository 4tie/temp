from __future__ import annotations

import logging
from typing import Any

from app.ai.models.openrouter_client import has_api_keys, list_models as or_list_models
from app.ai.models.ollama_client import is_available, list_models as oll_list_models

logger = logging.getLogger(__name__)


def _safe_log_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown error"
    return text.encode("ascii", "backslashreplace").decode("ascii")


async def get_providers_payload() -> dict[str, Any]:
    openrouter_available = has_api_keys()
    openrouter_models = []
    if openrouter_available:
        try:
            raw = await or_list_models()
            openrouter_models = [{"id": model["id"], "name": model.get("name", model["id"])} for model in raw[:50]]
        except Exception as exc:
            logger.warning("OpenRouter provider payload model list failed: %s", _safe_log_text(exc))

    ollama_available = await is_available()
    ollama_models = []
    if ollama_available:
        try:
            names = await oll_list_models()
            ollama_models = [{"id": f"ollama/{name}", "name": name} for name in names]
        except Exception as exc:
            logger.warning("Ollama model list failed: %s", exc)

    return {
        "openrouter": {"available": openrouter_available and bool(openrouter_models), "models": openrouter_models},
        "ollama": {"available": ollama_available, "models": ollama_models},
    }
