from __future__ import annotations

import ast
import difflib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.ai.memory.threads import load_thread
from app.core.config import STRATEGIES_DIR

_SAFE_STRATEGY_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_CODE_FENCE_RE = re.compile(r"```([A-Za-z0-9_\-]*)\n?([\s\S]*?)```")
_PY_FILE_RE = re.compile(r"\b([A-Za-z0-9_\-]+\.py)\b")


def validate_strategy_name(name: str) -> str:
    value = str(name or "").strip()
    if value.lower().endswith(".py"):
        value = value[:-3]
    if not value or not _SAFE_STRATEGY_RE.match(value):
        raise HTTPException(status_code=400, detail="Invalid strategy name")
    resolved = (STRATEGIES_DIR / f"{value}.py").resolve()
    if not str(resolved).startswith(str(STRATEGIES_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid strategy name")
    return value


def extract_code_blocks_with_hints(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    raw = str(text or "")
    for match in _CODE_FENCE_RE.finditer(raw):
        lang = (match.group(1) or "").strip().lower()
        code = (match.group(2) or "")
        before = raw[max(0, match.start() - 500):match.start()]
        after = raw[match.end():match.end() + 160]
        files_before = _PY_FILE_RE.findall(before)
        files_after = _PY_FILE_RE.findall(after)
        filename_hint = files_before[-1] if files_before else (files_after[0] if files_after else None)
        blocks.append(
            {
                "language": lang,
                "code": code.rstrip("\n"),
                "filename_hint": filename_hint,
            }
        )
    return blocks


def atomic_write_text(path: Path, content: str) -> int:
    encoded = content.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return len(encoded)


def apply_code_impl(
    *,
    thread_id: str,
    assistant_message_id: str,
    code_block_index: int,
    fallback_strategy: str | None,
) -> dict[str, Any]:
    thread = load_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    target_message = None
    for message in thread.get("messages", []):
        if message.get("id") == assistant_message_id:
            target_message = message
            break
    if not target_message:
        raise HTTPException(status_code=404, detail="Assistant message not found")
    if target_message.get("role") != "assistant":
        raise HTTPException(status_code=400, detail="Target message must be an assistant message")

    blocks = extract_code_blocks_with_hints(target_message.get("content", ""))
    if code_block_index < 0 or code_block_index >= len(blocks):
        raise HTTPException(status_code=400, detail="Invalid code block index")

    block = blocks[code_block_index]
    if block.get("language") not in {"python", "py"}:
        raise HTTPException(status_code=400, detail="Selected block is not a Python code block")

    filename_hint = block.get("filename_hint")
    strategy_hint = filename_hint.rsplit(".", 1)[0] if filename_hint else None
    strategy_name_raw = strategy_hint or fallback_strategy
    if not strategy_name_raw:
        raise HTTPException(status_code=400, detail="Could not resolve strategy target from message or fallback")

    strategy_name = validate_strategy_name(strategy_name_raw)
    source = str(block.get("code") or "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="Python code block is empty")

    try:
        ast.parse(source, filename=f"{strategy_name}.py")
    except SyntaxError as exc:
        line = exc.lineno or 0
        col = exc.offset or 0
        raise HTTPException(
            status_code=400,
            detail=f"Python syntax error at line {line}, column {col}: {exc.msg}",
        )

    py_path = STRATEGIES_DIR / f"{strategy_name}.py"
    if not py_path.exists():
        raise HTTPException(status_code=404, detail=f"Strategy source not found: {strategy_name}.py")
    json_path = STRATEGIES_DIR / f"{strategy_name}.json"

    old_py = py_path.read_text(encoding="utf-8")
    old_json = json_path.read_text(encoding="utf-8") if json_path.exists() else None
    bytes_written = atomic_write_text(py_path, source)
    new_json = json_path.read_text(encoding="utf-8") if json_path.exists() else None

    diff_lines = list(
        difflib.unified_diff(
            old_py.splitlines(),
            source.splitlines(),
            fromfile=f"{strategy_name}.py",
            tofile=f"{strategy_name}.py",
            lineterm="",
        )
    )
    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    preview = diff_lines[:80]

    json_changed = old_json != new_json
    json_preview: list[str] = []
    if old_json is not None or new_json is not None:
        json_preview = list(
            difflib.unified_diff(
                (old_json or "").splitlines(),
                (new_json or "").splitlines(),
                fromfile=f"{strategy_name}.json",
                tofile=f"{strategy_name}.json",
                lineterm="",
            )
        )[:80]

    return {
        "ok": True,
        "strategy": strategy_name,
        "file_path": str(py_path),
        "bytes_written": bytes_written,
        "diff_summary": {"added": added, "removed": removed, "changed": added + removed},
        "diff_preview": preview,
        "file_changes": {
            "strategy_py": {"path": str(py_path), "changed": bool(preview), "diff_preview": preview},
            "strategy_json": {
                "path": str(json_path),
                "exists": json_path.exists(),
                "changed": json_changed,
                "diff_preview": json_preview,
            },
        },
        "_old_source": old_py,
    }
