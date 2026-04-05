"""
AI Chat Router — REST + SSE endpoints for the AI subsystem.
"""
from __future__ import annotations

import ast
import asyncio
import difflib
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas.ai_chat import (
    ChatRequest,
    ConversationSummary,
    ThreadMessageAppendRequest,
    ApplyCodeRequest,
    LoopStartRequest,
    LoopConfirmRequest,
)
from app.ai.context_builder import build_context_bundle
from app.ai.goals import normalize_goal_id
from app.ai.pipelines.orchestrator import stream_run
from app.ai.models.openrouter_client import has_api_keys, list_models as or_list_models
from app.ai.models.ollama_client import is_available, list_models as oll_list_models
from app.ai.tools.deep_analysis import analyze
from app.ai.memory.threads import (
    append_message,
    create_thread,
    delete_thread,
    list_threads,
    load_thread,
    validate_thread_id,
)
from app.core.config import STRATEGIES_DIR, AI_LOOP_REPORTS_DIR, BASE_DIR
from app.services.storage import load_run_meta, load_run_results
from app.services.runner import start_backtest, wait_for_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])
_SAFE_STRATEGY_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_CODE_FENCE_RE = re.compile(r"```([A-Za-z0-9_\-]*)\n?([\s\S]*?)```")
_PY_FILE_RE = re.compile(r"\b([A-Za-z0-9_\-]+\.py)\b")
_LOOP_SESSIONS: dict[str, dict[str, Any]] = {}
_LOOP_EVENTS: dict[str, list[dict[str, Any]]] = {}
_LOOP_IDEMPOTENCY: dict[str, dict[str, Any]] = {}
_LOOP_LOCK = threading.Lock()
_LOOP_STATE_DIR = BASE_DIR / "ai_loop_state"
_LOOP_STATE_FILE = _LOOP_STATE_DIR / "sessions.json"
_LOOP_STATE_DIR.mkdir(parents=True, exist_ok=True)
_IDEMPOTENCY_TTL_S = 6 * 3600
_MAX_IDEMPOTENCY_RECORDS = 2000


# ─────────────────────────────────────────────────────────────────────────────
# Conversation helpers (local wrappers for HTTP error handling)
# ─────────────────────────────────────────────────────────────────────────────

def _validate_thread_id_http(thread_id: str) -> str:
    try:
        return validate_thread_id(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _thread_summary(thread: dict[str, Any]) -> ConversationSummary:
    thread_id = thread.get("thread_id") or thread.get("conversation_id") or ""
    return ConversationSummary(
        thread_id=thread_id,
        conversation_id=thread_id,
        title=thread.get("title", "Untitled"),
        preview=thread.get("preview"),
        created_at=thread.get("created_at", ""),
        updated_at=thread.get("updated_at", ""),
        message_count=len(thread.get("messages", [])),
        provider=thread.get("provider", "openrouter"),
        model=thread.get("model"),
        goal_id=thread.get("goal_id"),
        context_run_id=thread.get("context_run_id"),
        context_mode=thread.get("context_mode"),
    )


def _history_context(messages: list[dict[str, Any]], limit: int = 12) -> str:
    lines = []
    for message in messages[-limit:]:
        role = str(message.get("role", "user")).upper()
        content = str(message.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _resolve_thread_id(req: ChatRequest) -> str:
    return req.thread_id or req.conversation_id or str(uuid.uuid4())


def _role_overrides(model_id: str | None) -> dict[str, str] | None:
    if not model_id:
        return None
    return {
        "reasoner": model_id,
        "analyst_a": model_id,
        "analyst_b": model_id,
        "judge": model_id,
        "composer": model_id,
        "explainer": model_id,
        "code_gen": model_id,
        "structured_output": model_id,
        "classifier": model_id,
    }


def _assistant_meta(
    *,
    pipeline: dict[str, Any],
    goal_id: str,
    thread_id: str,
    context_run_id: str | None,
    context_mode: str,
) -> dict[str, Any]:
    steps = pipeline.get("steps") or []
    final_step = next((step for step in reversed(steps) if step.get("role") != "classifier"), {}) if steps else {}
    return {
        "pipeline_type": pipeline.get("pipeline_type", "simple"),
        "duration_ms": pipeline.get("total_duration_ms"),
        "model": final_step.get("model_id"),
        "provider": final_step.get("provider"),
        "goal_id": goal_id,
        "thread_id": thread_id,
        "conversation_id": thread_id,
        "context_run_id": context_run_id,
        "context_mode": context_mode,
        "trace": pipeline.get("trace", []),
        "pipeline": pipeline,
    }


def _validate_strategy_name(name: str) -> str:
    value = str(name or "").strip()
    if value.lower().endswith(".py"):
        value = value[:-3]
    if not value or not _SAFE_STRATEGY_RE.match(value):
        raise HTTPException(status_code=400, detail="Invalid strategy name")
    resolved = (STRATEGIES_DIR / f"{value}.py").resolve()
    if not str(resolved).startswith(str(STRATEGIES_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid strategy name")
    return value


def _extract_code_blocks_with_hints(text: str) -> list[dict[str, Any]]:
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


def _atomic_write_text(path, content: str) -> int:
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


def _apply_code_impl(
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

    blocks = _extract_code_blocks_with_hints(target_message.get("content", ""))
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

    strategy_name = _validate_strategy_name(strategy_name_raw)
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
    bytes_written = _atomic_write_text(py_path, source)
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


def _loop_emit(loop_id: str, event: dict[str, Any]) -> None:
    with _LOOP_LOCK:
        if loop_id not in _LOOP_EVENTS:
            _LOOP_EVENTS[loop_id] = []
        _LOOP_EVENTS[loop_id].append(event)


def _loop_drain(loop_id: str) -> list[dict[str, Any]]:
    with _LOOP_LOCK:
        events = list(_LOOP_EVENTS.get(loop_id, []))
        if loop_id in _LOOP_EVENTS:
            _LOOP_EVENTS[loop_id].clear()
        return events


def _persist_loop_state_locked() -> None:
    payload = {
        "sessions": _LOOP_SESSIONS,
        "idempotency": _LOOP_IDEMPOTENCY,
        "updated_at": _utc_now(),
    }
    fd, tmp_path = tempfile.mkstemp(prefix="loop_state.", suffix=".tmp", dir=str(_LOOP_STATE_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _LOOP_STATE_FILE)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _load_loop_state() -> None:
    if not _LOOP_STATE_FILE.exists():
        return
    try:
        data = json.loads(_LOOP_STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read loop state file: %s", exc)
        return
    sessions = data.get("sessions") or {}
    idempotency = data.get("idempotency") or {}
    now = _utc_now()
    with _LOOP_LOCK:
        _LOOP_SESSIONS.clear()
        _LOOP_SESSIONS.update(sessions)
        _LOOP_IDEMPOTENCY.clear()
        _LOOP_IDEMPOTENCY.update(idempotency)
        _prune_idempotency_locked()
        for loop_id, session in _LOOP_SESSIONS.items():
            if session.get("status") == "running":
                session["status"] = "interrupted"
                session["updated_at"] = now
                session.setdefault("steps", []).append(
                    {
                        "ts": now,
                        "step": "loop_recovered",
                        "status": "warning",
                        "message": "Server restarted while loop was running. Session recovered from disk.",
                    }
                )
                _LOOP_EVENTS.setdefault(loop_id, []).append(
                    {
                        "loop_id": loop_id,
                        "step": "loop_recovered",
                        "status": "warning",
                        "message": "Recovered from disk after restart.",
                        "done": True,
                    }
                )
        _persist_loop_state_locked()


def _idempotency_hit(action: str, key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    with _LOOP_LOCK:
        _prune_idempotency_locked()
        record = _LOOP_IDEMPOTENCY.get(f"{action}:{key}")
        if not record:
            return None
        return record.get("response")


def _idempotency_store(action: str, key: str | None, response: dict[str, Any]) -> None:
    if not key:
        return
    with _LOOP_LOCK:
        _LOOP_IDEMPOTENCY[f"{action}:{key}"] = {
            "stored_at": time.time(),
            "response": response,
        }
        _prune_idempotency_locked()
        _persist_loop_state_locked()


def _prune_idempotency_locked() -> None:
    now = time.time()
    stale_keys = []
    for k, v in _LOOP_IDEMPOTENCY.items():
        stored_at = float((v or {}).get("stored_at") or 0)
        if not stored_at or (now - stored_at) > _IDEMPOTENCY_TTL_S:
            stale_keys.append(k)
    for k in stale_keys:
        _LOOP_IDEMPOTENCY.pop(k, None)
    if len(_LOOP_IDEMPOTENCY) <= _MAX_IDEMPOTENCY_RECORDS:
        return
    ordered = sorted(
        _LOOP_IDEMPOTENCY.items(),
        key=lambda item: float((item[1] or {}).get("stored_at") or 0),
    )
    to_remove = len(_LOOP_IDEMPOTENCY) - _MAX_IDEMPOTENCY_RECORDS
    for k, _ in ordered[:to_remove]:
        _LOOP_IDEMPOTENCY.pop(k, None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_delta(before: Any, after: Any) -> str:
    try:
        b = float(before)
        a = float(after)
        return f"{a - b:+.4f}"
    except Exception:
        return "n/a"


def _retry_sync(
    *,
    label: str,
    fn,
    attempts: int = 3,
    base_delay_s: float = 0.8,
    loop_id: str | None = None,
    thread_id: str | None = None,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            delay = base_delay_s * (2 ** (attempt - 1))
            logger.warning(
                "loop_retry label=%s attempt=%s/%s delay=%.2fs loop_id=%s thread_id=%s err=%s",
                label,
                attempt,
                attempts,
                delay,
                loop_id,
                thread_id,
                exc,
            )
            time.sleep(delay)
    if last_exc:
        raise last_exc


def _summarize_step_metrics(session: dict[str, Any]) -> dict[str, Any]:
    step_metrics = session.get("step_metrics") or []
    by_step: dict[str, list[float]] = defaultdict(list)
    for row in step_metrics:
        by_step[str(row.get("step"))].append(float(row.get("duration_ms") or 0))
    summary = {}
    for step, arr in by_step.items():
        summary[step] = {
            "count": len(arr),
            "avg_ms": round(sum(arr) / len(arr), 2) if arr else 0,
            "max_ms": round(max(arr), 2) if arr else 0,
            "min_ms": round(min(arr), 2) if arr else 0,
        }
    return {"steps": step_metrics, "summary": summary}


def _result_delta_rows(before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[dict[str, Any]]:
    b = before or {}
    a = after or {}
    sections = [
        ("overview", ["profit_percent", "win_rate", "max_drawdown", "profit_factor", "total_trades", "final_balance"]),
        ("summary_metrics", sorted(set((a.get("summary_metrics") or {}).keys()) | set((b.get("summary_metrics") or {}).keys()))),
        ("balance_metrics", sorted(set((a.get("balance_metrics") or {}).keys()) | set((b.get("balance_metrics") or {}).keys()))),
        ("risk_metrics", sorted(set((a.get("risk_metrics") or {}).keys()) | set((b.get("risk_metrics") or {}).keys()))),
    ]
    rows: list[dict[str, Any]] = []
    for section, keys in sections:
        sec_b = b.get(section) or {}
        sec_a = a.get(section) or {}
        for key in keys:
            if key not in sec_a and key not in sec_b:
                continue
            before_v = sec_b.get(key)
            after_v = sec_a.get(key)
            rows.append(
                {
                    "section": section,
                    "metric": key,
                    "before": before_v,
                    "after": after_v,
                    "delta": _safe_delta(before_v, after_v),
                }
            )
    return rows


def _run_validation_tests(strategy_name: str) -> list[dict[str, Any]]:
    py = os.environ.get("FREQTRADE_PYTHON") or os.environ.get("PYTHON") or "python"
    commands: list[tuple[str, list[str]]] = [
        (
            "Python syntax compile",
            [
                py,
                "-m",
                "py_compile",
                str(STRATEGIES_DIR / f"{strategy_name}.py"),
                "app/routers/ai_chat.py",
                "app/services/strategy_scanner.py",
            ],
        ),
        ("AI chat router tests", [py, "-m", "unittest", "-q", "app.test_ai_chat_router"]),
        ("JS chat page syntax", ["node", "--check", "static/js/pages/ai-diagnosis.js"]),
    ]
    results: list[dict[str, Any]] = []
    for label, cmd in commands:
        started = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(Path(BASE_DIR).parent),
                capture_output=True,
                text=True,
                timeout=180,
            )
            elapsed = round((time.time() - started) * 1000)
            results.append(
                {
                    "name": label,
                    "command": " ".join(cmd),
                    "ok": proc.returncode == 0,
                    "code": proc.returncode,
                    "duration_ms": elapsed,
                    "stdout": (proc.stdout or "").strip()[:2000],
                    "stderr": (proc.stderr or "").strip()[:2000],
                }
            )
        except Exception as exc:
            elapsed = round((time.time() - started) * 1000)
            results.append(
                {
                    "name": label,
                    "command": " ".join(cmd),
                    "ok": False,
                    "code": -1,
                    "duration_ms": elapsed,
                    "stdout": "",
                    "stderr": str(exc),
                }
            )
    return results


def _render_loop_markdown(session: dict[str, Any]) -> str:
    rows = session.get("table_rows") or []
    tests = session.get("test_results") or []
    file_changes = session.get("file_changes") or {}
    lines = [
        f"# AI Loop Report: {session.get('loop_id')}",
        "",
        f"- Thread: `{session.get('thread_id')}`",
        f"- Strategy: `{session.get('strategy')}`",
        f"- Baseline run: `{session.get('baseline_run_id')}`",
        f"- New run: `{session.get('new_run_id')}`",
        f"- Status: `{session.get('status')}`",
        f"- Started: `{session.get('started_at')}`",
        f"- Updated: `{session.get('updated_at')}`",
        f"- Rollback On Regression: `{bool(session.get('request', {}).get('rollback_on_regression'))}`",
        "",
        "## Step Timeline",
    ]
    for step in session.get("steps", []):
        lines.append(f"- `{step.get('ts')}` **{step.get('step')}**: {step.get('message')}")
    lines.extend(["", "## Result Deltas (Full Summary Table)", "", "| Section | Metric | Before | After | Delta |", "|---|---|---:|---:|---:|"])
    for row in rows:
        lines.append(
            f"| {row.get('section')} | {row.get('metric')} | {row.get('before')} | {row.get('after')} | {row.get('delta')} |"
        )
    lines.extend(["", "## File Changes"])
    py_change = (file_changes.get("strategy_py") or {}).get("changed")
    json_change = (file_changes.get("strategy_json") or {}).get("changed")
    lines.append(f"- Strategy `.py`: {'changed' if py_change else 'unchanged'}")
    lines.append(f"- Strategy `.json`: {'changed' if json_change else 'unchanged'}")
    lines.extend(["", "## Test Results", "", "| Test | OK | Code | Duration (ms) |", "|---|---|---:|---:|"])
    for tr in tests:
        lines.append(f"| {tr.get('name')} | {'yes' if tr.get('ok') else 'no'} | {tr.get('code')} | {tr.get('duration_ms')} |")
    lines.extend(["", "## Test Output Snippets"])
    for tr in tests:
        lines.append(f"### {tr.get('name')}")
        lines.append("")
        lines.append("```text")
        snippet = tr.get("stderr") or tr.get("stdout") or "(no output)"
        lines.append(snippet[:1200])
        lines.append("```")
        lines.append("")
    if session.get("validation_text"):
        lines.extend(["## AI Validation", "", session.get("validation_text"), ""])
    metrics = _summarize_step_metrics(session)
    lines.extend(["## Step Latency Metrics", "", "| Step | Count | Avg ms | Min ms | Max ms |", "|---|---:|---:|---:|---:|"])
    for step, row in (metrics.get("summary") or {}).items():
        lines.append(f"| {step} | {row.get('count')} | {row.get('avg_ms')} | {row.get('min_ms')} | {row.get('max_ms')} |")
    violations = session.get("stop_rule_violations") or []
    if violations:
        lines.extend(["", "## Stop Rule Violations"])
        for violation in violations:
            lines.append(f"- {violation}")
    if session.get("rollback_applied"):
        lines.extend(["", "## Rollback", "", "- Regression detected; strategy source was rolled back to pre-loop state."])
    return "\n".join(lines)


def _write_loop_report(session: dict[str, Any]) -> str:
    loop_id = session["loop_id"]
    path = AI_LOOP_REPORTS_DIR / f"{loop_id}.md"
    payload = _render_loop_markdown(session)
    fd, tmp_path = tempfile.mkstemp(prefix=f"{loop_id}.", suffix=".tmp", dir=str(AI_LOOP_REPORTS_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return str(path)


# ─────────────────────────────────────────────────────────────────────────────
# SSE helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sse_line(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
_load_loop_state()

@router.get("/providers")
async def get_providers():
    openrouter_available = has_api_keys()
    openrouter_models = []
    if openrouter_available:
        try:
            raw = await or_list_models()
            openrouter_models = [{"id": model["id"], "name": model.get("name", model["id"])} for model in raw[:50]]
        except Exception as exc:
            logger.warning("OpenRouter model list failed: %s", exc)

    ollama_available = await is_available()
    ollama_models = []
    if ollama_available:
        try:
            names = await oll_list_models()
            ollama_models = [{"id": f"ollama/{name}", "name": name} for name in names]
        except Exception as exc:
            logger.warning("Ollama model list failed: %s", exc)

    return {
        "openrouter": {"available": openrouter_available and bool(openrouter_models), "models": openrouter_models},
        "ollama": {"available": ollama_available, "models": ollama_models},
    }


@router.post("/chat")
async def chat(req: ChatRequest):
    thread_id = _resolve_thread_id(req)
    thread = load_thread(thread_id)
    goal_id = normalize_goal_id(req.goal_id or (thread or {}).get("goal_id"))
    provider_name = req.provider or (thread or {}).get("provider", "openrouter")
    model_id = req.model or (thread or {}).get("model")

    if thread is None:
        thread = create_thread(
            thread_id=thread_id,
            provider=provider_name,
            model=model_id,
            goal_id=goal_id,
            context_run_id=req.context_run_id,
        )

    pinned_context_run_id = req.context_run_id
    if not pinned_context_run_id and thread.get("context_mode") == "pinned":
        pinned_context_run_id = thread.get("context_run_id")

    context_bundle = build_context_bundle(goal_id, pinned_context_run_id)
    actual_context_run_id = context_bundle.metadata.get("context_run_id")
    context_mode = "pinned" if pinned_context_run_id else context_bundle.metadata.get("context_mode", "auto")
    history_text = _history_context(thread.get("messages", []))
    full_context = context_bundle.context_text
    if history_text:
        full_context = f"{full_context}\n\n--- CONVERSATION HISTORY ---\n{history_text}"

    append_message(
        thread_id,
        "user",
        req.message,
        goal_id=goal_id,
        provider=provider_name,
        model=model_id,
        context_run_id=actual_context_run_id,
        context_mode=context_mode,
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        full_text = ""
        pipeline_info: dict[str, Any] | None = None
        try:
            async for chunk in stream_run(
                task_text=req.message,
                context=full_context,
                context_hint=context_bundle.context_hint,
                context_metadata=context_bundle.metadata,
                goal_id=goal_id,
                provider=provider_name,
                role_overrides=_role_overrides(model_id),
                has_strategy_source=bool(context_bundle.snapshot.get("strategy_config")),
            ):
                if chunk.get("error"):
                    yield _sse_line({"error": chunk["error"], "done": True})
                    return
                if chunk.get("delta"):
                    full_text += chunk["delta"]
                if chunk.get("done"):
                    pipeline_info = chunk.get("pipeline") or {}
                    full_text = chunk.get("fullText") or full_text
                    append_message(
                        thread_id,
                        "assistant",
                        full_text,
                        meta=_assistant_meta(
                            pipeline=pipeline_info,
                            goal_id=goal_id,
                            thread_id=thread_id,
                            context_run_id=actual_context_run_id,
                            context_mode=context_mode,
                        ),
                        goal_id=goal_id,
                        provider=provider_name,
                        model=(pipeline_info.get("steps") or [{}])[-1].get("model_id") if pipeline_info else model_id,
                        context_run_id=actual_context_run_id,
                        context_mode=context_mode,
                    )
                    latest_thread = load_thread(thread_id) or {}
                    assistant_message_id = None
                    messages = latest_thread.get("messages") or []
                    if messages:
                        assistant_message_id = messages[-1].get("id")
                    final_chunk = dict(chunk)
                    final_chunk["thread_id"] = thread_id
                    final_chunk["conversation_id"] = thread_id
                    final_chunk["assistant_message_id"] = assistant_message_id
                    yield _sse_line(final_chunk)
                    return
                yield _sse_line(chunk)
        except Exception as exc:
            logger.error("Chat stream error for thread %s: %s", thread_id, exc)
            yield _sse_line({"error": str(exc), "done": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/threads")
async def list_threads_endpoint():
    return [_thread_summary(thread) for thread in list_threads(limit=50)]


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    _validate_thread_id_http(thread_id)
    thread = load_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/threads/{thread_id}")
async def delete_thread_endpoint(thread_id: str):
    _validate_thread_id_http(thread_id)
    deleted = delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"deleted": thread_id}


@router.post("/threads/{thread_id}/messages")
async def append_thread_message(thread_id: str, req: ThreadMessageAppendRequest):
    _validate_thread_id_http(thread_id)
    return append_message(
        thread_id,
        req.role,
        req.content,
        meta=req.meta,
        goal_id=req.goal_id,
        provider=req.provider,
        model=req.model,
        context_run_id=req.context_run_id,
        context_mode=req.context_mode,
    )


@router.post("/chat/apply-code")
async def apply_code(req: ApplyCodeRequest):
    thread_id = _validate_thread_id_http(req.thread_id)
    result = _apply_code_impl(
        thread_id=thread_id,
        assistant_message_id=req.assistant_message_id,
        code_block_index=req.code_block_index,
        fallback_strategy=req.fallback_strategy,
    )
    result.pop("_old_source", None)
    return result


async def _run_validation_text(
    *,
    thread_id: str,
    strategy: str,
    diff_summary: dict[str, Any],
    context_run_id: str | None,
    provider: str,
    model: str | None,
    goal_id: str | None,
) -> str:
    thread = load_thread(thread_id) or {}
    goal = normalize_goal_id(goal_id or thread.get("goal_id"))
    bundle = build_context_bundle(goal, context_run_id)
    prompt = (
        f"I applied code updates to {strategy}.py.\n"
        f"Diff summary: +{diff_summary.get('added', 0)} / -{diff_summary.get('removed', 0)}.\n"
        "Validate this change before rerun. Return:\n"
        "1) logic correctness checks\n2) overfitting risk checks\n3) rerun focus metrics\n"
        "Use concise bullets."
    )
    full = ""
    async for chunk in stream_run(
        task_text=prompt,
        context=bundle.context_text,
        context_hint=bundle.context_hint,
        context_metadata=bundle.metadata,
        goal_id=goal,
        provider=provider,
        role_overrides=_role_overrides(model),
        has_strategy_source=bool(bundle.snapshot.get("strategy_config")),
    ):
        if chunk.get("delta"):
            full += chunk["delta"]
        if chunk.get("done"):
            return chunk.get("fullText") or full
    return full


def _run_validation_text_sync(**kwargs: Any) -> str:
    async_loop = asyncio.new_event_loop()
    try:
        return async_loop.run_until_complete(_run_validation_text(**kwargs))
    finally:
        async_loop.close()


def _loop_worker(loop_id: str) -> None:
    with _LOOP_LOCK:
        session = _LOOP_SESSIONS.get(loop_id)
    if not session:
        return

    def mark_step(step: str, status: str, message: str, duration_ms: int | None = None, **extra: Any) -> None:
        now = _utc_now()
        with _LOOP_LOCK:
            s = _LOOP_SESSIONS.get(loop_id)
            if not s:
                return
            s["updated_at"] = now
            s.setdefault("steps", []).append({"ts": now, "step": step, "status": status, "message": message})
            if duration_ms is not None:
                s.setdefault("step_metrics", []).append({"ts": now, "step": step, "duration_ms": duration_ms})
            s.update(extra)
            s["md_report_path"] = _write_loop_report(s)
            payload = {
                "loop_id": loop_id,
                "step": step,
                "status": status,
                "message": message,
                "md_report_path": s["md_report_path"],
                "duration_ms": duration_ms,
                **extra,
            }
            _LOOP_EVENTS.setdefault(loop_id, []).append(payload)
            _persist_loop_state_locked()
            logger.info(
                "loop_step loop_id=%s thread_id=%s step=%s status=%s duration_ms=%s run_id=%s",
                loop_id,
                s.get("thread_id"),
                step,
                status,
                duration_ms,
                s.get("new_run_id"),
            )

    try:
        mark_step(
            "loop_started",
            "ok",
            "Loop started. Planned steps: apply -> AI validate -> wait confirm -> rerun -> compare -> tests -> report.",
            planned_steps=[
                "apply code",
                "ai validate",
                "wait rerun confirmation",
                "run backtest",
                "compute result delta table",
                "compute file changes",
                "run tests",
                "write markdown report",
            ],
        )

        req = session["request"]
        stop_rules = req.get("stop_rules") or {}
        apply_started = time.perf_counter()
        apply_result = _retry_sync(
            label="apply_code",
            loop_id=loop_id,
            thread_id=req.get("thread_id"),
            fn=lambda: _apply_code_impl(
                thread_id=req["thread_id"],
                assistant_message_id=req["assistant_message_id"],
                code_block_index=req["code_block_index"],
                fallback_strategy=req.get("fallback_strategy"),
            ),
        )
        apply_duration = round((time.perf_counter() - apply_started) * 1000)
        original_source = apply_result.pop("_old_source", None)
        strategy_path = Path(apply_result.get("file_path") or "")
        mark_step(
            "apply_done",
            "ok",
            f"Applied changes to {apply_result['strategy']}.py",
            duration_ms=apply_duration,
            apply_result=apply_result,
            strategy=apply_result["strategy"],
            file_changes=apply_result.get("file_changes"),
        )

        with _LOOP_LOCK:
            if _LOOP_SESSIONS.get(loop_id, {}).get("stop_requested"):
                mark_step("loop_stopped", "stopped", "Loop stopped by user before validation.", done=True)
                return

        validate_started = time.perf_counter()
        validation_text = _retry_sync(
            label="ai_validate",
            loop_id=loop_id,
            thread_id=req.get("thread_id"),
            fn=lambda: _run_validation_text_sync(
                thread_id=req["thread_id"],
                strategy=apply_result["strategy"],
                diff_summary=apply_result.get("diff_summary") or {},
                context_run_id=req.get("context_run_id"),
                provider=req.get("provider") or "openrouter",
                model=req.get("model"),
                goal_id=req.get("goal_id"),
            ),
        )
        validate_duration = round((time.perf_counter() - validate_started) * 1000)

        append_message(
            req["thread_id"],
            "assistant",
            validation_text,
            meta={"auto_loop": True, "phase": "validation"},
            goal_id=req.get("goal_id"),
            provider=req.get("provider"),
            model=req.get("model"),
            context_run_id=req.get("context_run_id"),
            context_mode="pinned",
        )

        mark_step(
            "ai_validate_done",
            "ok",
            "AI validation completed. Awaiting user rerun confirmation.",
            duration_ms=validate_duration,
            validation_text=validation_text,
            awaiting_confirm=True,
        )

        while True:
            with _LOOP_LOCK:
                s = _LOOP_SESSIONS.get(loop_id, {})
                if s.get("stop_requested"):
                    mark_step("loop_stopped", "stopped", "Loop stopped by user.", done=True)
                    return
                decision = s.get("rerun_confirmed")
            if decision is None:
                time.sleep(0.4)
                continue
            if not decision:
                mark_step("loop_stopped", "stopped", "User declined rerun. Loop closed.", done=True)
                return
            break

        base_run_id = req.get("context_run_id")
        base_meta = load_run_meta(base_run_id) if base_run_id else None
        if not base_meta:
            raise RuntimeError(f"Context run not found: {base_run_id}")
        rerun_body = {
            "strategy": apply_result["strategy"],
            "pairs": base_meta.get("pairs") or [],
            "timeframe": base_meta.get("timeframe") or "5m",
            "timerange": base_meta.get("timerange"),
            "exchange": base_meta.get("exchange") or "binance",
            "strategy_params": base_meta.get("strategy_params") or {},
        }
        mark_step("rerun_started", "ok", "Backtest rerun started.", rerun_request=rerun_body)
        rerun_started = time.perf_counter()
        run_id = _retry_sync(
            label="start_backtest",
            loop_id=loop_id,
            thread_id=req.get("thread_id"),
            fn=lambda: start_backtest(
                strategy=rerun_body["strategy"],
                pairs=rerun_body["pairs"],
                timeframe=rerun_body["timeframe"],
                timerange=rerun_body["timerange"],
                strategy_params=rerun_body["strategy_params"],
                exchange=rerun_body["exchange"],
            ),
        )
        final_meta = _retry_sync(
            label="wait_backtest",
            loop_id=loop_id,
            thread_id=req.get("thread_id"),
            fn=lambda: wait_for_run(run_id, timeout_s=1200),
        )
        rerun_duration = round((time.perf_counter() - rerun_started) * 1000)
        run_status = final_meta.get("status", "unknown")
        mark_step(
            "rerun_done",
            "ok" if run_status == "completed" else "failed",
            f"Rerun finished: {run_status}",
            duration_ms=rerun_duration,
            run_id=run_id,
        )

        before_results = load_run_results(base_run_id) if base_run_id else {}
        after_results = load_run_results(run_id) if run_status == "completed" else {}
        diff_started = time.perf_counter()
        table_rows = _result_delta_rows(before_results, after_results)
        mark_step(
            "result_diff",
            "ok",
            "Computed full summary table deltas.",
            duration_ms=round((time.perf_counter() - diff_started) * 1000),
            table_rows=table_rows,
        )

        file_changes = apply_result.get("file_changes") or {}
        mark_step("file_diff", "ok", "Computed file change summary (.py/.json).", file_changes=file_changes)

        tests_started = time.perf_counter()
        tests = _run_validation_tests(apply_result["strategy"])
        tests_ok = all(item.get("ok") for item in tests)
        mark_step(
            "tests_done",
            "ok" if tests_ok else "warning",
            "Validation test pack completed.",
            duration_ms=round((time.perf_counter() - tests_started) * 1000),
            test_results=tests,
        )

        recommendation = "ITERATE"
        if run_status != "completed":
            recommendation = "REVIEW_FAILURE"
        elif tests_ok:
            recommendation = "KEEP_OR_ITERATE"

        stop_rule_violations: list[str] = []
        overview = {(r.get("metric"), r.get("section")): r for r in table_rows}
        profit_delta = overview.get(("profit_percent", "overview"), {}).get("delta")
        drawdown_delta = overview.get(("max_drawdown", "overview"), {}).get("delta")
        try:
            min_profit_delta = stop_rules.get("min_profit_delta")
            if min_profit_delta is not None and float(profit_delta) < float(min_profit_delta):
                stop_rule_violations.append(
                    f"profit delta {profit_delta} below threshold {min_profit_delta}"
                )
        except Exception:
            pass
        try:
            max_drawdown_increase = stop_rules.get("max_drawdown_increase")
            if max_drawdown_increase is not None and float(drawdown_delta) > float(max_drawdown_increase):
                stop_rule_violations.append(
                    f"max drawdown delta {drawdown_delta} above threshold {max_drawdown_increase}"
                )
        except Exception:
            pass
        if stop_rules.get("require_tests_pass") and not tests_ok:
            stop_rule_violations.append("tests must pass but one or more validations failed")
        if run_status != "completed":
            stop_rule_violations.append(f"rerun status is {run_status}")
        if stop_rule_violations:
            recommendation = "REVERT" if req.get("rollback_on_regression") else "STOP"

        rollback_applied = False
        if stop_rule_violations and req.get("rollback_on_regression") and original_source and strategy_path.exists():
            _atomic_write_text(strategy_path, original_source)
            rollback_applied = True
            mark_step(
                "rollback_done",
                "warning",
                "Rollback applied because stop rules were violated.",
                stop_rule_violations=stop_rule_violations,
            )

        with _LOOP_LOCK:
            s = _LOOP_SESSIONS.get(loop_id)
            if s:
                if stop_rule_violations:
                    s["status"] = "warning"
                else:
                    s["status"] = "completed" if run_status == "completed" else "failed"
                s["new_run_id"] = run_id
                s["baseline_run_id"] = base_run_id
                s["recommendation"] = recommendation
                s["table_rows"] = table_rows
                s["test_results"] = tests
                s["file_changes"] = file_changes
                s["stop_rule_violations"] = stop_rule_violations
                s["rollback_applied"] = rollback_applied
                s["updated_at"] = _utc_now()
                s["md_report_path"] = _write_loop_report(s)
                metrics = _summarize_step_metrics(s)
                _LOOP_EVENTS.setdefault(loop_id, []).append(
                    {
                        "loop_id": loop_id,
                        "step": "cycle_done",
                        "status": s["status"],
                        "message": f"Cycle complete. Recommendation: {recommendation}.",
                        "run_id": run_id,
                        "table_rows": table_rows,
                        "file_changes": file_changes,
                        "test_results": tests,
                        "stop_rule_violations": stop_rule_violations,
                        "rollback_applied": rollback_applied,
                        "metrics": metrics,
                        "report_url": f"/ai/loop/{loop_id}/report",
                        "report_download_url": f"/ai/loop/{loop_id}/report/download",
                        "md_report_path": s["md_report_path"],
                        "done": True,
                    }
                )
                _persist_loop_state_locked()
    except Exception as exc:
        logger.error("Loop worker failed (%s): %s", loop_id, exc)
        with _LOOP_LOCK:
            s = _LOOP_SESSIONS.get(loop_id)
            if s:
                s["status"] = "failed"
                s["updated_at"] = _utc_now()
                s["error"] = str(exc)
                s["md_report_path"] = _write_loop_report(s)
                _LOOP_EVENTS.setdefault(loop_id, []).append(
                    {
                        "loop_id": loop_id,
                        "step": "loop_failed",
                        "status": "failed",
                        "message": str(exc),
                        "md_report_path": s["md_report_path"],
                        "done": True,
                    }
                )
                _persist_loop_state_locked()


@router.post("/loop/start")
async def loop_start(req: LoopStartRequest):
    cached = _idempotency_hit("loop_start", req.idempotency_key)
    if cached:
        return cached
    thread_id = _validate_thread_id_http(req.thread_id)
    loop_id = str(uuid.uuid4())
    now = _utc_now()
    session = {
        "loop_id": loop_id,
        "thread_id": thread_id,
        "status": "running",
        "started_at": now,
        "updated_at": now,
        "strategy": None,
        "baseline_run_id": req.context_run_id,
        "new_run_id": None,
        "steps": [],
        "table_rows": [],
        "test_results": [],
        "file_changes": {},
        "validation_text": "",
        "step_metrics": [],
        "request": {
            "thread_id": thread_id,
            "assistant_message_id": req.assistant_message_id,
            "code_block_index": req.code_block_index,
            "fallback_strategy": req.fallback_strategy,
            "context_run_id": req.context_run_id,
            "provider": req.provider,
            "model": req.model,
            "goal_id": normalize_goal_id(req.goal_id),
            "rollback_on_regression": bool(req.rollback_on_regression),
            "stop_rules": req.stop_rules or {},
        },
        "rerun_confirmed": None,
        "stop_requested": False,
    }
    session["md_report_path"] = _write_loop_report(session)
    with _LOOP_LOCK:
        _LOOP_SESSIONS[loop_id] = session
        _LOOP_EVENTS[loop_id] = []
        _persist_loop_state_locked()

    thread = threading.Thread(target=_loop_worker, args=(loop_id,), daemon=True)
    thread.start()
    logger.info(
        "loop_start loop_id=%s thread_id=%s context_run_id=%s provider=%s",
        loop_id,
        thread_id,
        req.context_run_id,
        req.provider,
    )
    response = {
        "loop_id": loop_id,
        "status": "running",
        "md_report_path": session["md_report_path"],
        "report_url": f"/ai/loop/{loop_id}/report",
        "report_download_url": f"/ai/loop/{loop_id}/report/download",
    }
    _idempotency_store("loop_start", req.idempotency_key, response)
    return response


@router.post("/loop/{loop_id}/confirm-rerun")
async def loop_confirm_rerun(loop_id: str, req: LoopConfirmRequest):
    cached = _idempotency_hit(f"loop_confirm:{loop_id}", req.idempotency_key)
    if cached:
        return cached
    with _LOOP_LOCK:
        session = _LOOP_SESSIONS.get(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Loop not found")
        session["rerun_confirmed"] = bool(req.confirm)
        session["updated_at"] = _utc_now()
        session["md_report_path"] = _write_loop_report(session)
        _persist_loop_state_locked()
    response = {"loop_id": loop_id, "confirm": bool(req.confirm)}
    logger.info("loop_confirm loop_id=%s confirm=%s", loop_id, bool(req.confirm))
    _idempotency_store(f"loop_confirm:{loop_id}", req.idempotency_key, response)
    return response


@router.post("/loop/{loop_id}/stop")
async def loop_stop(loop_id: str, req: LoopConfirmRequest | None = None):
    idem_key = req.idempotency_key if req else None
    cached = _idempotency_hit(f"loop_stop:{loop_id}", idem_key)
    if cached:
        return cached
    with _LOOP_LOCK:
        session = _LOOP_SESSIONS.get(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Loop not found")
        session["stop_requested"] = True
        session["updated_at"] = _utc_now()
        session["md_report_path"] = _write_loop_report(session)
        _persist_loop_state_locked()
    response = {"loop_id": loop_id, "stopping": True}
    logger.info("loop_stop loop_id=%s", loop_id)
    _idempotency_store(f"loop_stop:{loop_id}", idem_key, response)
    return response


@router.get("/loop/{loop_id}/stream")
async def loop_stream(loop_id: str):
    async def event_stream() -> AsyncGenerator[str, None]:
        timeout_s = 3600
        elapsed = 0.0
        while elapsed < timeout_s:
            events = _loop_drain(loop_id)
            for event in events:
                yield _sse_line(event)
                if event.get("done"):
                    return
            await asyncio.sleep(0.4)
            elapsed += 0.4
        yield _sse_line({"loop_id": loop_id, "step": "loop_failed", "status": "failed", "message": "stream timeout", "done": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/loop/{loop_id}/report")
async def loop_report(loop_id: str):
    with _LOOP_LOCK:
        session = _LOOP_SESSIONS.get(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Loop not found")
        md_path = Path(session.get("md_report_path") or (AI_LOOP_REPORTS_DIR / f"{loop_id}.md"))
    preview = ""
    if md_path.exists():
        preview = md_path.read_text(encoding="utf-8")[:12000]
    return {
        "loop_id": loop_id,
        "status": session.get("status"),
        "path": str(md_path),
        "exists": md_path.exists(),
        "preview": preview,
        "download_url": f"/ai/loop/{loop_id}/report/download",
        "metrics": _summarize_step_metrics(session),
    }


@router.get("/loop/{loop_id}/report/download")
async def loop_report_download(loop_id: str):
    with _LOOP_LOCK:
        session = _LOOP_SESSIONS.get(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Loop not found")
        md_path = Path(session.get("md_report_path") or (AI_LOOP_REPORTS_DIR / f"{loop_id}.md"))
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(
        path=str(md_path),
        media_type="text/markdown",
        filename=f"{loop_id}.md",
    )


@router.get("/loop/{loop_id}/metrics")
async def loop_metrics(loop_id: str):
    with _LOOP_LOCK:
        session = _LOOP_SESSIONS.get(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Loop not found")
        metrics = _summarize_step_metrics(session)
        return {
            "loop_id": loop_id,
            "status": session.get("status"),
            "thread_id": session.get("thread_id"),
            "run_id": session.get("new_run_id"),
            "metrics": metrics,
        }


@router.get("/loop/sessions")
async def list_loop_sessions():
    with _LOOP_LOCK:
        rows = []
        for loop_id, session in sorted(
            _LOOP_SESSIONS.items(),
            key=lambda item: item[1].get("updated_at") or "",
            reverse=True,
        ):
            rows.append(
                {
                    "loop_id": loop_id,
                    "thread_id": session.get("thread_id"),
                    "status": session.get("status"),
                    "updated_at": session.get("updated_at"),
                    "report_url": f"/ai/loop/{loop_id}/report",
                    "report_download_url": f"/ai/loop/{loop_id}/report/download",
                }
            )
        return {"sessions": rows}


@router.get("/conversations")
async def list_conversations_endpoint():
    return await list_threads_endpoint()


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    return await get_thread(conv_id)


@router.delete("/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: str):
    return await delete_thread_endpoint(conv_id)


@router.post("/analyze/{run_id}")
async def analyze_run(run_id: str):
    from app.services.storage import load_run_results, load_run_meta

    meta = load_run_meta(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    results = load_run_results(run_id) or {}
    run_data = {**results, "strategy": meta.get("strategy", "")}

    try:
        analysis = analyze(run_data, run_id=run_id)
        return analysis
    except Exception as exc:
        logger.error("Deep analysis failed for run %s: %s", run_id, exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.get("/pipeline-logs")
async def get_pipeline_logs():
    from app.ai.pipelines.orchestrator import list_pipeline_logs
    return list_pipeline_logs(limit=50)
