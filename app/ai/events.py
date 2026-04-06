from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class LoopStream(str, Enum):
    AI_LOOP = "ai_loop"
    EVOLUTION = "evolution"


class LoopEventStatus(str, Enum):
    INFO = "info"
    OK = "ok"
    RUNNING = "running"
    WARNING = "warning"
    FAILED = "failed"
    STOPPED = "stopped"
    COMPLETED = "completed"


class LoopEventType(str, Enum):
    LOOP_STARTED = "loop_started"
    LOOP_RECOVERED = "loop_recovered"
    APPLY_DONE = "apply_done"
    VALIDATE_DONE = "validate_done"
    RERUN_STARTED = "rerun_started"
    RERUN_DONE = "rerun_done"
    RESULT_DIFF = "result_diff"
    FILE_DIFF = "file_diff"
    TESTS_DONE = "tests_done"
    ROLLBACK_DONE = "rollback_done"
    CYCLE_DONE = "cycle_done"
    LOOP_COMPLETED = "loop_completed"
    LOOP_STOPPED = "loop_stopped"
    LOOP_FAILED = "loop_failed"
    ANALYSIS_STARTED = "analysis_started"
    MUTATION_STARTED = "mutation_started"
    MUTATION_FAILED = "mutation_failed"
    BACKTEST_STARTED = "backtest_started"
    BACKTEST_FAILED = "backtest_failed"
    COMPARISON_DONE = "comparison_done"


_LEGACY_EVENT_ALIASES: dict[str, LoopEventType] = {
    "ai_validate_done": LoopEventType.VALIDATE_DONE,
    "analyzing": LoopEventType.ANALYSIS_STARTED,
    "mutating": LoopEventType.MUTATION_STARTED,
    "backtesting": LoopEventType.BACKTEST_STARTED,
    "comparing": LoopEventType.COMPARISON_DONE,
    "done": LoopEventType.LOOP_COMPLETED,
    "error": LoopEventType.LOOP_FAILED,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def coerce_loop_event_type(value: LoopEventType | str) -> LoopEventType:
    if isinstance(value, LoopEventType):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Event type is required")
    alias = _LEGACY_EVENT_ALIASES.get(raw)
    if alias is not None:
        return alias
    return LoopEventType(raw)


def serialize_loop_event(
    *,
    loop_id: str,
    event_type: LoopEventType | str,
    status: LoopEventStatus | str = LoopEventStatus.INFO,
    payload: Mapping[str, Any] | None = None,
    message: str | None = None,
    done: bool = False,
    cycle_index: int | None = None,
    timestamp: str | None = None,
    stream: LoopStream | str | None = None,
) -> dict[str, Any]:
    event_kind = coerce_loop_event_type(event_type)
    event_status = status.value if isinstance(status, LoopEventStatus) else str(status or LoopEventStatus.INFO.value)
    envelope_payload = dict(payload or {})
    if message is None and isinstance(envelope_payload.get("message"), str):
        message = envelope_payload["message"]
    if cycle_index is None:
        raw_cycle = envelope_payload.get("cycle_index", envelope_payload.get("generation"))
        if isinstance(raw_cycle, int):
            cycle_index = raw_cycle

    event: dict[str, Any] = {
        "event_type": event_kind.value,
        "step": event_kind.value,
        "status": event_status,
        "timestamp": timestamp or _utc_now(),
        "loop_id": loop_id,
        "done": bool(done),
        "payload": envelope_payload,
    }
    if stream:
        event["stream"] = stream.value if isinstance(stream, LoopStream) else str(stream)
    if message is not None:
        event["message"] = message
    if cycle_index is not None:
        event["cycle_index"] = cycle_index

    for key, value in envelope_payload.items():
        event.setdefault(key, value)
    return event


def serialize_ai_loop_event(
    loop_id: str,
    event_type: LoopEventType | str,
    *,
    status: LoopEventStatus | str = LoopEventStatus.INFO,
    payload: Mapping[str, Any] | None = None,
    message: str | None = None,
    done: bool = False,
    cycle_index: int | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return serialize_loop_event(
        loop_id=loop_id,
        event_type=event_type,
        status=status,
        payload=payload,
        message=message,
        done=done,
        cycle_index=cycle_index,
        timestamp=timestamp,
        stream=LoopStream.AI_LOOP,
    )


def serialize_evolution_event(
    loop_id: str,
    event_type: LoopEventType | str,
    *,
    status: LoopEventStatus | str = LoopEventStatus.INFO,
    payload: Mapping[str, Any] | None = None,
    message: str | None = None,
    done: bool = False,
    generation: int | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    merged_payload = dict(payload or {})
    if generation is not None:
        merged_payload.setdefault("generation", generation)
    return serialize_loop_event(
        loop_id=loop_id,
        event_type=event_type,
        status=status,
        payload=merged_payload,
        message=message,
        done=done,
        cycle_index=generation,
        timestamp=timestamp,
        stream=LoopStream.EVOLUTION,
    )


def sse_event_line(data: Mapping[str, Any]) -> str:
    return f"data: {json.dumps(dict(data), default=str)}\n\n"


__all__ = [
    "LoopEventStatus",
    "LoopEventType",
    "LoopStream",
    "coerce_loop_event_type",
    "serialize_ai_loop_event",
    "serialize_evolution_event",
    "serialize_loop_event",
    "sse_event_line",
]
