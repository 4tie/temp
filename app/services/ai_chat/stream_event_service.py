from __future__ import annotations

from typing import Any

from app.ai.events import sse_event_line as _sse_event_line

def sse_line(data: dict[str, Any]) -> str:
    return _sse_event_line(data)
