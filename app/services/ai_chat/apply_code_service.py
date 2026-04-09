from __future__ import annotations

import ast
import difflib
import re
from typing import Any

from fastapi import HTTPException

from app.ai.memory.threads import load_thread
from app.core.config import STRATEGIES_DIR
from app.services.strategies import (
    atomic_write_text,
    create_snapshot,
    resolve_strategy_sidecar_path,
    resolve_strategy_source_path,
    stage_strategy_source_change,
    validate_strategy_name as validate_strategy_identifier,
)

_CODE_FENCE_RE = re.compile(r"```([A-Za-z0-9_\-]*)\n?([\s\S]*?)```")
_PY_FILE_RE = re.compile(r"\b([A-Za-z0-9_\-]+\.py)\b")


def validate_strategy_name(name: str) -> str:
    try:
        return validate_strategy_identifier(name, strategies_dir=STRATEGIES_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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

def apply_code_impl(
    *,
    thread_id: str,
    assistant_message_id: str,
    code_block_index: int,
    fallback_strategy: str | None,
    direct_apply: bool = True,
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

    py_path = resolve_strategy_source_path(strategy_name, strategies_dir=STRATEGIES_DIR)
    if not py_path.exists():
        raise HTTPException(status_code=404, detail=f"Strategy source not found: {strategy_name}.py")
    json_path = resolve_strategy_sidecar_path(strategy_name, strategies_dir=STRATEGIES_DIR)

    old_py = py_path.read_text(encoding="utf-8")
    old_json = json_path.read_text(encoding="utf-8") if json_path.exists() else None
    bytes_written = 0
    new_json = old_json
    target_py_path = py_path
    target_json_path = json_path
    version_name: str | None = None
    staged = not direct_apply

    if direct_apply:
        # Create snapshot before direct apply to live strategy
        try:
            snapshot_result = create_snapshot(
                strategy_name=strategy_name,
                reason="apply_code_impl_direct",
                actor="ai",
                linked_run_id=None,
                metadata={
                    "operation": "direct_apply",
                    "thread_id": thread_id,
                    "assistant_message_id": assistant_message_id,
                    "code_block_index": code_block_index,
                    "source_bytes": len(source.encode("utf-8"))
                }
            )
        except Exception:
            # Don't fail the apply if snapshot creation fails
            pass

        bytes_written = atomic_write_text(py_path, source)
        new_json = json_path.read_text(encoding="utf-8") if json_path.exists() else None
    else:
        staged_result = stage_strategy_source_change(
            strategy_name=strategy_name,
            source=source,
            strategies_dir=STRATEGIES_DIR,
            reason="ai_chat_apply_code",
            actor="ai",
        )
        bytes_written = int(staged_result.get("bytes_written") or 0)
        version_name = str(staged_result.get("version_name") or "")
        if not version_name:
            raise HTTPException(status_code=500, detail="Failed to stage strategy change")
        target_py_path = resolve_strategy_source_path(version_name, strategies_dir=STRATEGIES_DIR)
        target_json_path = resolve_strategy_sidecar_path(version_name, strategies_dir=STRATEGIES_DIR)
        new_json = target_json_path.read_text(encoding="utf-8") if target_json_path.exists() else None

    diff_lines = list(
        difflib.unified_diff(
            old_py.splitlines(),
            source.splitlines(),
            fromfile=f"{strategy_name}.py",
            tofile=target_py_path.name,
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
                tofile=target_json_path.name,
                lineterm="",
            )
        )[:80]

    return {
        "ok": True,
        "strategy": strategy_name,
        "file_path": str(target_py_path),
        "bytes_written": bytes_written,
        "diff_summary": {"added": added, "removed": removed, "changed": added + removed},
        "diff_preview": preview,
        "file_changes": {
            "strategy_py": {
                "path": str(target_py_path),
                "changed": bool(preview),
                "diff_preview": preview,
                "staged": staged,
                "version_name": version_name,
            },
            "strategy_json": {
                "path": str(target_json_path),
                "exists": target_json_path.exists(),
                "changed": json_changed,
                "diff_preview": json_preview,
            },
        },
        "staged": staged,
        "version_name": version_name,
        "requires_manual_promotion": staged,
        "promotion_endpoint": (
            f"/strategies/{strategy_name}/versions/{version_name}/accept" if staged and version_name else None
        ),
        "_old_source": old_py,
    }
