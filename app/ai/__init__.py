from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["chat_complete", "stream_chat", "run", "stream_run", "classify", "analyze"]


def __getattr__(name: str) -> Any:
    if name in {"chat_complete", "stream_chat"}:
        module = import_module("app.ai.models.provider_dispatch")
        return getattr(module, name)
    if name in {"run", "stream_run"}:
        module = import_module("app.ai.pipelines.orchestrator")
        return getattr(module, name)
    if name == "classify":
        module = import_module("app.ai.pipelines.classifier")
        return module.classify
    if name == "analyze":
        module = import_module("app.ai.tools.deep_analysis")
        return module.analyze
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
