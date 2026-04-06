"""
Feedback store — persists per-strategy mutation history to disk.

File: user_data/ai_evolution/{strategy}_feedback.json
Schema: list of feedback entry dicts, newest last.
"""
from __future__ import annotations

from app.core.config import AI_EVOLUTION_DIR
from app.core.json_io import read_json, write_json


def _path(strategy: str):
    return AI_EVOLUTION_DIR / f"{strategy}_feedback.json"


def record_pending(
    strategy: str,
    generation: int,
    changes_summary: str,
    fitness_before: float,
    version_name: str,
) -> None:
    history: list[dict] = read_json(_path(strategy), [])
    history = [entry for entry in history if entry.get("generation") != generation]
    history.append(
        {
            "generation": generation,
            "version_name": version_name,
            "changes_summary": changes_summary,
            "fitness_before": round(fitness_before, 2),
            "fitness_after": None,
            "delta": None,
            "accepted": None,
            "status": "pending",
        }
    )
    write_json(_path(strategy), history)


def record(
    strategy: str,
    generation: int,
    changes_summary: str,
    fitness_before: float,
    fitness_after: float,
    accepted: bool,
    version_name: str | None = None,
) -> None:
    history: list[dict] = read_json(_path(strategy), [])
    updated = False
    for entry in history:
        if entry.get("generation") != generation:
            continue
        entry.update(
            {
                "version_name": version_name or entry.get("version_name"),
                "changes_summary": changes_summary,
                "fitness_before": round(fitness_before, 2),
                "fitness_after": round(fitness_after, 2),
                "delta": round(fitness_after - fitness_before, 2),
                "accepted": accepted,
                "status": "completed",
            }
        )
        updated = True
        break

    if not updated:
        history.append(
            {
                "generation": generation,
                "version_name": version_name,
                "changes_summary": changes_summary,
                "fitness_before": round(fitness_before, 2),
                "fitness_after": round(fitness_after, 2),
                "delta": round(fitness_after - fitness_before, 2),
                "accepted": accepted,
                "status": "completed",
            }
        )

    write_json(_path(strategy), history)


def get_history(strategy: str, limit: int = 10) -> list[dict]:
    history: list[dict] = read_json(_path(strategy), [])
    return history[-limit:]


def get_winning_patterns(strategy: str) -> list[str]:
    history: list[dict] = read_json(_path(strategy), [])
    return [
        e["changes_summary"]
        for e in history
        if e.get("accepted") and e.get("delta", 0) > 0
    ]
