"""
Conversation CRUD — load, save, list, delete conversations stored as JSON files.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import AI_CONVERSATIONS_DIR

_SAFE_CONV_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _conv_path(conv_id: str) -> Path:
    return AI_CONVERSATIONS_DIR / f"{conv_id}.json"


def _validate_conv_id(conv_id: str) -> str:
    if not conv_id or not _SAFE_CONV_ID_RE.match(conv_id):
        raise ValueError(f"Invalid conversation ID: {conv_id!r}")
    resolved = (AI_CONVERSATIONS_DIR / f"{conv_id}.json").resolve()
    if not str(resolved).startswith(str(AI_CONVERSATIONS_DIR.resolve())):
        raise ValueError("Path traversal detected in conversation ID")
    return conv_id


def new_conversation_id() -> str:
    return str(uuid.uuid4())


def load_conversation(conv_id: str) -> dict | None:
    _validate_conv_id(conv_id)
    p = _conv_path(conv_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_conversation(conv: dict) -> None:
    _validate_conv_id(conv["conversation_id"])
    p = _conv_path(conv["conversation_id"])
    p.write_text(json.dumps(conv, indent=2, default=str), encoding="utf-8")


def list_conversations(limit: int = 50) -> list[dict]:
    if not AI_CONVERSATIONS_DIR.exists():
        return []
    files = sorted(
        AI_CONVERSATIONS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    convs = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            convs.append(data)
        except Exception:
            continue
    return convs


def delete_conversation(conv_id: str) -> bool:
    _validate_conv_id(conv_id)
    p = _conv_path(conv_id)
    if not p.exists():
        return False
    p.unlink()
    return True
