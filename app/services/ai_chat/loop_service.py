from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import threading
import time
import uuid
from typing import Any

from fastapi import HTTPException

from app.ai.events import LoopEventStatus, LoopEventType, serialize_ai_loop_event
from app.ai.context_builder import build_context_bundle
from app.ai.goals import normalize_goal_id
from app.ai.memory.threads import append_message
from app.ai.pipelines.orchestrator import stream_run
from app.core.config import AI_LOOP_REPORTS_DIR, AI_LOOP_STATE_DIR, AI_LOOP_STATE_FILE
from app.services.ai_chat.apply_code_service import apply_code_impl, atomic_write_text
from app.services.ai_chat.loop_report_service import (
    result_delta_rows,
    run_validation_tests,
    summarize_step_metrics,
    utc_now,
    write_loop_report,
)
from app.services.ai_chat.thread_service import role_overrides, validate_thread_id_http
from app.services.runner import start_backtest, wait_for_run
from app.services.storage import load_run_meta, load_run_results

logger = logging.getLogger(__name__)

LOOP_SESSIONS: dict[str, dict[str, Any]] = {}
LOOP_EVENTS: dict[str, list[dict[str, Any]]] = {}
LOOP_IDEMPOTENCY: dict[str, dict[str, Any]] = {}
# Recovery/import paths can emit events while already holding the loop lock.
# Use an RLock so startup restoration does not deadlock on nested acquisition.
LOOP_LOCK = threading.RLock()
IDEMPOTENCY_TTL_S = 6 * 3600
MAX_IDEMPOTENCY_RECORDS = 2000


def loop_emit(loop_id: str, event: dict[str, Any]) -> None:
    with LOOP_LOCK:
        if loop_id not in LOOP_EVENTS:
            LOOP_EVENTS[loop_id] = []
        LOOP_EVENTS[loop_id].append(event)


def loop_drain(loop_id: str) -> list[dict[str, Any]]:
    with LOOP_LOCK:
        events = list(LOOP_EVENTS.get(loop_id, []))
        if loop_id in LOOP_EVENTS:
            LOOP_EVENTS[loop_id].clear()
        return events


def prune_idempotency_locked() -> None:
    now = time.time()
    stale_keys = []
    for k, v in LOOP_IDEMPOTENCY.items():
        stored_at = float((v or {}).get("stored_at") or 0)
        if not stored_at or (now - stored_at) > IDEMPOTENCY_TTL_S:
            stale_keys.append(k)
    for k in stale_keys:
        LOOP_IDEMPOTENCY.pop(k, None)
    if len(LOOP_IDEMPOTENCY) <= MAX_IDEMPOTENCY_RECORDS:
        return
    ordered = sorted(
        LOOP_IDEMPOTENCY.items(),
        key=lambda item: float((item[1] or {}).get("stored_at") or 0),
    )
    to_remove = len(LOOP_IDEMPOTENCY) - MAX_IDEMPOTENCY_RECORDS
    for k, _ in ordered[:to_remove]:
        LOOP_IDEMPOTENCY.pop(k, None)


def persist_loop_state_locked() -> None:
    payload = {
        "sessions": LOOP_SESSIONS,
        "idempotency": LOOP_IDEMPOTENCY,
        "updated_at": utc_now(),
    }
    fd, tmp_path = tempfile.mkstemp(prefix="loop_state.", suffix=".tmp", dir=str(LOOP_STATE_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, LOOP_STATE_FILE)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def load_loop_state() -> None:
    if not LOOP_STATE_FILE.exists():
        return
    try:
        data = json.loads(LOOP_STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read loop state file: %s", exc)
        return
    sessions = data.get("sessions") or {}
    idempotency = data.get("idempotency") or {}
    now = utc_now()
    with LOOP_LOCK:
        LOOP_SESSIONS.clear()
        LOOP_SESSIONS.update(sessions)
        LOOP_IDEMPOTENCY.clear()
        LOOP_IDEMPOTENCY.update(idempotency)
        prune_idempotency_locked()
        for loop_id, session in LOOP_SESSIONS.items():
            if session.get("status") == "running":
                session["status"] = "interrupted"
                session["updated_at"] = now
                session.setdefault("steps", []).append(
                    {
                        "ts": now,
                        "step": LoopEventType.LOOP_RECOVERED.value,
                        "status": "warning",
                        "message": "Server restarted while loop was running. Session recovered from disk.",
                    }
                )
                loop_emit(
                    loop_id,
                    serialize_ai_loop_event(
                        loop_id,
                        LoopEventType.LOOP_RECOVERED,
                        status=LoopEventStatus.WARNING,
                        message="Recovered from disk after restart.",
                        done=True,
                    ),
                )
        persist_loop_state_locked()


def idempotency_hit(action: str, key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    with LOOP_LOCK:
        prune_idempotency_locked()
        record = LOOP_IDEMPOTENCY.get(f"{action}:{key}")
        if not record:
            return None
        return record.get("response")


def idempotency_store(action: str, key: str | None, response: dict[str, Any]) -> None:
    if not key:
        return
    with LOOP_LOCK:
        LOOP_IDEMPOTENCY[f"{action}:{key}"] = {
            "stored_at": time.time(),
            "response": response,
        }
        prune_idempotency_locked()
        persist_loop_state_locked()


def retry_sync(
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


async def run_validation_text(
    *,
    thread_id: str,
    strategy: str,
    diff_summary: dict[str, Any],
    context_run_id: str | None,
    provider: str,
    model: str | None,
    goal_id: str | None,
) -> str:
    goal = normalize_goal_id(goal_id)
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
        role_overrides=role_overrides(model),
        has_strategy_source=bool(bundle.snapshot.get("strategy_config")),
    ):
        if chunk.get("delta"):
            full += chunk["delta"]
        if chunk.get("done"):
            return chunk.get("fullText") or full
    return full


def run_validation_text_sync(**kwargs: Any) -> str:
    async_loop = asyncio.new_event_loop()
    try:
        return async_loop.run_until_complete(run_validation_text(**kwargs))
    finally:
        async_loop.close()


def loop_worker(loop_id: str) -> None:
    with LOOP_LOCK:
        session = LOOP_SESSIONS.get(loop_id)
    if not session:
        return

    def mark_step(event_type: LoopEventType, status: str, message: str, duration_ms: int | None = None, **extra: Any) -> None:
        now = utc_now()
        with LOOP_LOCK:
            s = LOOP_SESSIONS.get(loop_id)
            if not s:
                return
            s["updated_at"] = now
            s.setdefault("steps", []).append({"ts": now, "step": event_type.value, "status": status, "message": message})
            if duration_ms is not None:
                s.setdefault("step_metrics", []).append({"ts": now, "step": event_type.value, "duration_ms": duration_ms})
            s.update(extra)
            s["md_report_path"] = write_loop_report(s)
            event_payload = {
                "md_report_path": s["md_report_path"],
                **extra,
            }
            if duration_ms is not None:
                event_payload["duration_ms"] = duration_ms
            loop_emit(
                loop_id,
                serialize_ai_loop_event(
                    loop_id,
                    event_type,
                    status=status,
                    message=message,
                    payload=event_payload,
                    done=bool(extra.get("done")),
                    timestamp=now,
                ),
            )
            persist_loop_state_locked()

    try:
        mark_step(
            LoopEventType.LOOP_STARTED,
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
        apply_result = retry_sync(
            label="apply_code",
            loop_id=loop_id,
            thread_id=req.get("thread_id"),
            fn=lambda: apply_code_impl(
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
            LoopEventType.APPLY_DONE,
            "ok",
            f"Applied changes to {apply_result['strategy']}.py",
            duration_ms=apply_duration,
            apply_result=apply_result,
            strategy=apply_result["strategy"],
            file_changes=apply_result.get("file_changes"),
        )

        with LOOP_LOCK:
            if LOOP_SESSIONS.get(loop_id, {}).get("stop_requested"):
                mark_step(LoopEventType.LOOP_STOPPED, "stopped", "Loop stopped by user before validation.", done=True)
                return

        validate_started = time.perf_counter()
        validation_text = retry_sync(
            label="ai_validate",
            loop_id=loop_id,
            thread_id=req.get("thread_id"),
            fn=lambda: run_validation_text_sync(
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
            LoopEventType.VALIDATE_DONE,
            "ok",
            "AI validation completed. Awaiting user rerun confirmation.",
            duration_ms=validate_duration,
            validation_text=validation_text,
            awaiting_confirm=True,
        )

        while True:
            with LOOP_LOCK:
                s = LOOP_SESSIONS.get(loop_id, {})
                if s.get("stop_requested"):
                    mark_step(LoopEventType.LOOP_STOPPED, "stopped", "Loop stopped by user.", done=True)
                    return
                decision = s.get("rerun_confirmed")
            if decision is None:
                time.sleep(0.4)
                continue
            if not decision:
                mark_step(LoopEventType.LOOP_STOPPED, "stopped", "User declined rerun. Loop closed.", done=True)
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
        mark_step(LoopEventType.RERUN_STARTED, "ok", "Backtest rerun started.", rerun_request=rerun_body)
        rerun_started = time.perf_counter()
        run_id = retry_sync(
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
        final_meta = retry_sync(
            label="wait_backtest",
            loop_id=loop_id,
            thread_id=req.get("thread_id"),
            fn=lambda: wait_for_run(run_id, timeout_s=1200),
        )
        rerun_duration = round((time.perf_counter() - rerun_started) * 1000)
        run_status = final_meta.get("status", "unknown")
        mark_step(
            LoopEventType.RERUN_DONE,
            "ok" if run_status == "completed" else "failed",
            f"Rerun finished: {run_status}",
            duration_ms=rerun_duration,
            run_id=run_id,
        )

        before_results = load_run_results(base_run_id) if base_run_id else {}
        after_results = load_run_results(run_id) if run_status == "completed" else {}
        diff_started = time.perf_counter()
        table_rows = result_delta_rows(before_results, after_results)
        mark_step(
            LoopEventType.RESULT_DIFF,
            "ok",
            "Computed full summary table deltas.",
            duration_ms=round((time.perf_counter() - diff_started) * 1000),
            table_rows=table_rows,
        )

        file_changes = apply_result.get("file_changes") or {}
        mark_step(LoopEventType.FILE_DIFF, "ok", "Computed file change summary (.py/.json).", file_changes=file_changes)

        tests_started = time.perf_counter()
        tests = run_validation_tests(apply_result["strategy"])
        tests_ok = all(item.get("ok") for item in tests)
        mark_step(
            LoopEventType.TESTS_DONE,
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
        overview = {r.get("metric"): r for r in table_rows if r.get("section") == "core"}
        profit_delta = overview.get("profit_percent", {}).get("delta")
        drawdown_delta = overview.get("max_drawdown", {}).get("delta")
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
            atomic_write_text(strategy_path, original_source)
            rollback_applied = True
            mark_step(
                LoopEventType.ROLLBACK_DONE,
                "warning",
                "Rollback applied because stop rules were violated.",
                stop_rule_violations=stop_rule_violations,
            )

        with LOOP_LOCK:
            s = LOOP_SESSIONS.get(loop_id)
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
                s["updated_at"] = utc_now()
                s["md_report_path"] = write_loop_report(s)
                metrics = summarize_step_metrics(s)
                loop_emit(
                    loop_id,
                    serialize_ai_loop_event(
                        loop_id,
                        LoopEventType.CYCLE_DONE,
                        status=s["status"],
                        message=f"Cycle complete. Recommendation: {recommendation}.",
                        done=True,
                        payload={
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
                        },
                    ),
                )
                persist_loop_state_locked()
    except Exception as exc:
        logger.error("Loop worker failed (%s): %s", loop_id, exc)
        with LOOP_LOCK:
            s = LOOP_SESSIONS.get(loop_id)
            if s:
                s["status"] = "failed"
                s["updated_at"] = utc_now()
                s["error"] = str(exc)
                s["md_report_path"] = write_loop_report(s)
                loop_emit(
                    loop_id,
                    serialize_ai_loop_event(
                        loop_id,
                        LoopEventType.LOOP_FAILED,
                        status=LoopEventStatus.FAILED,
                        message=str(exc),
                        done=True,
                        payload={"md_report_path": s["md_report_path"]},
                    ),
                )
                persist_loop_state_locked()


def start_loop_session(req: Any) -> dict[str, Any]:
    cached = idempotency_hit("loop_start", req.idempotency_key)
    if cached:
        return cached
    thread_id = validate_thread_id_http(req.thread_id)
    loop_id = str(uuid.uuid4())
    now = utc_now()
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
    session["md_report_path"] = write_loop_report(session)
    with LOOP_LOCK:
        LOOP_SESSIONS[loop_id] = session
        LOOP_EVENTS[loop_id] = []
        persist_loop_state_locked()

    thread = threading.Thread(target=loop_worker, args=(loop_id,), daemon=True)
    thread.start()
    response = {
        "loop_id": loop_id,
        "status": "running",
        "md_report_path": session["md_report_path"],
        "report_url": f"/ai/loop/{loop_id}/report",
        "report_download_url": f"/ai/loop/{loop_id}/report/download",
    }
    idempotency_store("loop_start", req.idempotency_key, response)
    return response


def confirm_rerun(loop_id: str, req: Any) -> dict[str, Any]:
    cached = idempotency_hit(f"loop_confirm:{loop_id}", req.idempotency_key)
    if cached:
        return cached
    with LOOP_LOCK:
        session = LOOP_SESSIONS.get(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Loop not found")
        session["rerun_confirmed"] = bool(req.confirm)
        session["updated_at"] = utc_now()
        session["md_report_path"] = write_loop_report(session)
        persist_loop_state_locked()
    response = {"loop_id": loop_id, "confirm": bool(req.confirm)}
    idempotency_store(f"loop_confirm:{loop_id}", req.idempotency_key, response)
    return response


def stop_loop(loop_id: str, req: Any | None = None) -> dict[str, Any]:
    idem_key = req.idempotency_key if req else None
    cached = idempotency_hit(f"loop_stop:{loop_id}", idem_key)
    if cached:
        return cached
    with LOOP_LOCK:
        session = LOOP_SESSIONS.get(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Loop not found")
        session["stop_requested"] = True
        session["updated_at"] = utc_now()
        session["md_report_path"] = write_loop_report(session)
        persist_loop_state_locked()
    response = {"loop_id": loop_id, "stopping": True}
    idempotency_store(f"loop_stop:{loop_id}", idem_key, response)
    return response


def loop_report_payload(loop_id: str) -> dict[str, Any]:
    with LOOP_LOCK:
        session = LOOP_SESSIONS.get(loop_id)
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
        "metrics": summarize_step_metrics(session),
    }


def loop_metrics_payload(loop_id: str) -> dict[str, Any]:
    with LOOP_LOCK:
        session = LOOP_SESSIONS.get(loop_id)
        if not session:
            raise HTTPException(status_code=404, detail="Loop not found")
        metrics = summarize_step_metrics(session)
        return {
            "loop_id": loop_id,
            "status": session.get("status"),
            "thread_id": session.get("thread_id"),
            "run_id": session.get("new_run_id"),
            "metrics": metrics,
        }


def list_loop_sessions_payload() -> dict[str, Any]:
    with LOOP_LOCK:
        rows = []
        for loop_id, session in sorted(
            LOOP_SESSIONS.items(),
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
