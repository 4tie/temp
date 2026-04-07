"""
Feedback store — persists per-strategy mutation history to disk.

File: user_data/ai_evolution/{strategy}_feedback.json
Schema: list of feedback entry dicts, newest last.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import AI_EVOLUTION_DIR
from app.core.json_io import read_json, write_json


def _path(strategy: str):
    return AI_EVOLUTION_DIR / f"{strategy}_feedback.json"


def _candidate_path(strategy: str):
    return AI_EVOLUTION_DIR / f"{strategy}_candidates.json"


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


def list_candidate_attempts(strategy: str, limit: int = 200) -> list[dict]:
    history: list[dict] = read_json(_candidate_path(strategy), [])
    if limit <= 0:
        return []
    return history[-limit:]


def find_candidate(strategy: str, fingerprint: str) -> dict[str, Any] | None:
    if not fingerprint:
        return None
    history: list[dict] = read_json(_candidate_path(strategy), [])
    for entry in reversed(history):
        if str(entry.get("candidate_fingerprint") or "") == fingerprint:
            return entry
    return None


def record_candidate_attempt(
    *,
    strategy: str,
    loop_id: str,
    generation_index: int,
    version_id: str,
    candidate_vector: dict[str, Any],
    candidate_fingerprint: str,
    status: str,
    accepted: bool | None,
    fitness_after: float | None,
    rejection_reason: str | None,
) -> None:
    history: list[dict] = read_json(_candidate_path(strategy), [])
    history.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "strategy": strategy,
            "loop_id": loop_id,
            "generation_index": generation_index,
            "version_id": version_id,
            "candidate_vector": dict(candidate_vector or {}),
            "candidate_fingerprint": candidate_fingerprint,
            "status": status,
            "accepted": accepted,
            "fitness_after": None if fitness_after is None else round(float(fitness_after), 4),
            "rejection_reason": rejection_reason,
        }
    )
    # Keep file bounded for safety.
    if len(history) > 2000:
        history = history[-2000:]
    write_json(_candidate_path(strategy), history)
