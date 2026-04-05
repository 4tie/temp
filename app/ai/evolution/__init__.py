from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["start_evolution", "get_evolution_status", "list_evolution_runs"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module("app.ai.evolution.evolver")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
