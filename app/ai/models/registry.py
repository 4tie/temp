"""
AI Model Registry — fetches free models from OpenRouter + Ollama, assigns roles.
"""
from __future__ import annotations

import logging
import os

from app.ai.model_router import select_model_for_role
from app.ai.model_routing_policy import LOW_RISK_ROLES, ROLE_CANDIDATES

logger = logging.getLogger(__name__)


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
    mode = str(os.environ.get("MODEL_ROUTER_MODE", "log_only")).strip().lower()
    if mode not in {"legacy", "log_only", "low_risk", "all"}:
        mode = "all"

    legacy_model, legacy_reason = _legacy_select_model(role=role, models=models, overrides=overrides)
    proposed = select_model_for_role(role=role, models=models, overrides=overrides)

    if mode == "legacy":
        return legacy_model, f"{legacy_reason}|mode=legacy"
    if mode == "log_only":
        logger.info(
            "model_router_compare role=%s chosen=%s proposed=%s legacy=%s reason=%s proposed_reason=%s",
            role,
            legacy_model,
            proposed.model_id,
            legacy_model,
            legacy_reason,
            proposed.reason,
        )
        return legacy_model, f"{legacy_reason}|mode=log_only|proposed={proposed.model_id}"
    if mode == "low_risk" and role not in LOW_RISK_ROLES:
        return legacy_model, f"{legacy_reason}|mode=low_risk"
    return proposed.model_id, f"{proposed.reason}|mode={mode}|fallbacks={','.join(proposed.fallback_chain)}"


def _legacy_select_model(
    role: str,
    models: list[dict],
    overrides: dict[str, str] | None = None,
) -> tuple[str, str]:
    if overrides and role in overrides:
        return overrides[role], f"override:{role}"

    available_ids = {m["id"] for m in models if m.get("id")}
    preferences = ROLE_CANDIDATES.get(role, ROLE_CANDIDATES.get("explainer", []))

    for preferred in preferences:
        if preferred in available_ids:
            return preferred, f"legacy:preferred:{role}"

    if available_ids:
        chosen = sorted(available_ids)[0]
        return chosen, "legacy:fallback:first-available"

    return "meta-llama/llama-3.2-1b-instruct:free", "legacy:fallback:hardcoded"
