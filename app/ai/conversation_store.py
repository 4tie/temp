"""Simple file-based conversation persistence."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

CONV_DIR = Path("user_data/ai_conversations")


def _ensure() -> Path:
    CONV_DIR.mkdir(parents=True, exist_ok=True)
    return CONV_DIR


def _conv_path(conv_id: str) -> Path:
    return CONV_DIR / f"{conv_id}.json"


def list_conversations(limit: int = 100) -> list[dict]:
    _ensure()
    convs = []
    for f in sorted(CONV_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            convs.append({
                "id": data["id"],
                "strategy_name": data.get("strategy_name", ""),
                "preview": data.get("preview", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            pass
    return convs


def get_conversation(conv_id: str) -> dict | None:
    _ensure()
    path = _conv_path(conv_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def create_conversation(strategy_name: str = "") -> dict:
    _ensure()
    conv_id = str(uuid.uuid4())
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conv = {
        "id": conv_id,
        "strategy_name": strategy_name,
        "preview": "",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    _conv_path(conv_id).write_text(json.dumps(conv, indent=2), encoding="utf-8")
    return conv


def append_message(conv_id: str, role: str, content: str, meta: dict | None = None) -> dict | None:
    conv = get_conversation(conv_id)
    if conv is None:
        conv = {
            "id": conv_id,
            "strategy_name": "",
            "preview": "",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "messages": [],
        }
    msg: dict[str, Any] = {
        "role": role,
        "content": content,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if meta:
        msg["meta"] = meta
    conv["messages"].append(msg)
    conv["updated_at"] = msg["ts"]

    # Update preview from first user message
    if not conv.get("preview"):
        for m in conv["messages"]:
            if m["role"] == "user":
                conv["preview"] = m["content"][:80]
                break

    _ensure()
    _conv_path(conv_id).write_text(json.dumps(conv, indent=2), encoding="utf-8")
    return conv


def delete_conversation(conv_id: str) -> bool:
    path = _conv_path(conv_id)
    if path.exists():
        path.unlink()
        return True
    return False
