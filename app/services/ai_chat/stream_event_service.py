from __future__ import annotations

import json
from typing import Any


def sse_line(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\\n\\n"
