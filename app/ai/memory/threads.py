from __future__ import annotations

import json
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ai.goals import normalize_goal_id
from app.ai.context_builder import build_context_snapshot
from app.core.config import AI_CONVERSATIONS_DIR, AI_THREADS_DIR

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _thread_path(thread_id: str) -> Path:
    return AI_THREADS_DIR / f"{thread_id}.json"


def _legacy_path(thread_id: str) -> Path:
    return AI_CONVERSATIONS_DIR / f"{thread_id}.json"


def validate_thread_id(thread_id: str) -> str:
    if not thread_id or not _SAFE_ID_RE.match(thread_id):
        raise ValueError(f"Invalid thread ID: {thread_id!r}")
    return thread_id


def new_thread_id() -> str:
    return str(uuid.uuid4())


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".tmp",
        prefix=f"{path.stem}_",
        dir=str(path.parent),
        delete=False,
        encoding="utf-8",
    ) as tmp:
        json.dump(payload, tmp, indent=2, ensure_ascii=True)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _message_preview(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"])[:80]
    return ""


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": message.get("id") or str(uuid.uuid4()),
        "role": message.get("role", "user"),
        "content": message.get("content", ""),
        "created_at": message.get("created_at") or message.get("ts") or _utc_now(),
        "meta": message.get("meta") or {},
    }


def _migrate_legacy_conversation(thread_id: str) -> dict[str, Any] | None:
    legacy = _read_json(_legacy_path(thread_id))
    if not legacy:
        return None

    messages = [_normalize_message(message) for message in legacy.get("messages", [])]
    goal_id = normalize_goal_id(legacy.get("goal_id"))
    thread = {
        "schema_version": 1,
        "thread_id": thread_id,
        "conversation_id": thread_id,
        "title": legacy.get("title") or legacy.get("strategy_name") or legacy.get("preview") or "Migrated thread",
        "preview": legacy.get("preview") or _message_preview(messages),
        "created_at": legacy.get("created_at") or _utc_now(),
        "updated_at": legacy.get("updated_at") or legacy.get("created_at") or _utc_now(),
        "goal_id": goal_id,
        "provider": legacy.get("provider", "openrouter"),
        "model": legacy.get("model"),
        "context_run_id": None,
        "context_mode": "migrated",
        "context_snapshot": {},
        "messages": messages,
        "migrated_from": "ai_conversations",
    }
    save_thread(thread)
    return thread


def load_thread(thread_id: str) -> dict[str, Any] | None:
    validate_thread_id(thread_id)
    thread = _read_json(_thread_path(thread_id))
    if thread:
        return thread
    return _migrate_legacy_conversation(thread_id)


def save_thread(thread: dict[str, Any]) -> None:
    thread_id = validate_thread_id(thread["thread_id"])
    payload = {
        "schema_version": 1,
        "thread_id": thread_id,
        "conversation_id": thread_id,
        "title": thread.get("title") or "New thread",
        "preview": thread.get("preview") or _message_preview(thread.get("messages", [])),
        "created_at": thread.get("created_at") or _utc_now(),
        "updated_at": thread.get("updated_at") or _utc_now(),
        "goal_id": normalize_goal_id(thread.get("goal_id")),
        "provider": thread.get("provider", "openrouter"),
        "model": thread.get("model"),
        "context_run_id": thread.get("context_run_id"),
        "context_mode": thread.get("context_mode", "auto"),
        "context_snapshot": thread.get("context_snapshot") or {},
        "messages": [_normalize_message(message) for message in thread.get("messages", [])],
    }
    if thread.get("migrated_from"):
        payload["migrated_from"] = thread["migrated_from"]
    _atomic_write(_thread_path(thread_id), payload)


def create_thread(
    thread_id: str | None = None,
    provider: str = "openrouter",
    model: str | None = None,
    goal_id: str | None = None,
    context_run_id: str | None = None,
) -> dict[str, Any]:
    thread_id = validate_thread_id(thread_id) if thread_id else new_thread_id()
    now = _utc_now()
    thread = {
        "schema_version": 1,
        "thread_id": thread_id,
        "conversation_id": thread_id,
        "title": "New thread",
        "preview": "",
        "created_at": now,
        "updated_at": now,
        "goal_id": normalize_goal_id(goal_id),
        "provider": provider,
        "model": model,
        "context_run_id": context_run_id,
        "context_mode": "pinned" if context_run_id else "auto",
        "context_snapshot": build_context_snapshot(goal_id, context_run_id),
        "messages": [],
    }
    save_thread(thread)
    return thread


def list_threads(limit: int = 50) -> list[dict[str, Any]]:
    AI_THREADS_DIR.mkdir(parents=True, exist_ok=True)
    legacy_ids = {
        path.stem for path in AI_CONVERSATIONS_DIR.glob("*.json")
        if not _thread_path(path.stem).exists()
    }
    for legacy_id in legacy_ids:
        _migrate_legacy_conversation(legacy_id)

    threads: list[dict[str, Any]] = []
    files = sorted(
        AI_THREADS_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limit]
    for file_path in files:
        data = _read_json(file_path)
        if data:
            threads.append(data)
    return threads


def delete_thread(thread_id: str) -> bool:
    validate_thread_id(thread_id)
    path = _thread_path(thread_id)
    if path.exists():
        path.unlink()
        return True
    return False


def append_message(
    thread_id: str,
    role: str,
    content: str,
    *,
    meta: dict[str, Any] | None = None,
    goal_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    context_run_id: str | None = None,
    context_mode: str | None = None,
) -> dict[str, Any]:
    thread = load_thread(thread_id)
    if thread is None:
        thread = create_thread(
            thread_id=thread_id,
            provider=provider or "openrouter",
            model=model,
            goal_id=goal_id,
            context_run_id=context_run_id,
        )

    if not thread.get("context_snapshot"):
        thread["context_snapshot"] = build_context_snapshot(goal_id or thread.get("goal_id"), context_run_id)

    message = {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "created_at": _utc_now(),
        "meta": meta or {},
    }
    thread.setdefault("messages", []).append(message)
    thread["updated_at"] = message["created_at"]
    thread["preview"] = thread.get("preview") or _message_preview(thread["messages"])
    if thread.get("title") == "New thread" and role == "user" and content:
        thread["title"] = content[:60]
    if goal_id:
        thread["goal_id"] = normalize_goal_id(goal_id)
    if provider:
        thread["provider"] = provider
    if model:
        thread["model"] = model
    if context_run_id:
        thread["context_run_id"] = context_run_id
    if context_mode:
        thread["context_mode"] = context_mode
    save_thread(thread)
    return thread
