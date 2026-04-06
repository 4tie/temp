"""
AI Pipeline Orchestrator — multi-model pipeline engine.
Supports 6 pipeline types: simple, analysis, debate, code, structured, tool.
Supports true streaming for the final pipeline step.
Logs every run to configured AI pipeline logs directory.
"""
from __future__ import annotations

import ast
import asyncio
import contextvars
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, AsyncGenerator

from app.core.config import AI_PIPELINE_LOGS_DIR
from ...core.json_io import write_json, ensure_dir
import app.ai.models.provider_dispatch as _dispatch
from app.ai.model_metrics_store import record_observation
from ..models.registry import fetch_free_models, get_model_for_role
from .classifier import (
    classify, Classification, PipelineType, ComplexityLevel,
)
from ..prompts.trading import (
    REASONER_SYSTEM_PROMPT,
    COMPOSER_SYSTEM_PROMPT,
    ANALYST_SYSTEM_PROMPT,
    CODE_GEN_SYSTEM_PROMPT,
    CODE_EXPLAINER_SYSTEM_PROMPT,
    CODE_AWARE_ADVISOR_SYSTEM_PROMPT,
    TOOL_CALLER_SYSTEM_PROMPT,
    STRUCTURED_OUTPUT_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT_TEMPLATE,
    GOAL_DIRECTIVES,
)

logger = logging.getLogger(__name__)

_current_provider: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_provider", default="openrouter"
)


async def chat_complete(messages: list[dict], model: str) -> str:
    provider = _current_provider.get()
    return await _dispatch.chat_complete(messages, model, provider=provider)


async def stream_chat(messages: list[dict], model: str) -> AsyncGenerator[dict, None]:
    provider = _current_provider.get()
    async for chunk in _dispatch.stream_chat(messages, model, provider=provider):
        yield chunk

PIPELINE_LOG_DIR = AI_PIPELINE_LOGS_DIR


@dataclass
class CodeValidation:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    method: str = "ast_parse"

    def to_dict(self) -> dict:
        return asdict(self)


def _save_log(result: PipelineResult) -> None:
    ensure_dir(PIPELINE_LOG_DIR)
    log_data = {
        "id": result.run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **result.to_dict(),
    }
    log_data.pop("final_text", None)
    write_json(PIPELINE_LOG_DIR / f"{result.run_id}.json", log_data)


def _extract_python_code(code: str) -> str | None:
    fence_start = code.find("```python")
    if fence_start >= 0:
        fence_end = code.find("```", fence_start + 9)
        if fence_end > fence_start:
            return code[fence_start + 9:fence_end].strip()
    if "```" in code:
        parts = code.split("```")
        if len(parts) >= 3:
            block = parts[1].strip()
            if block.startswith("python"):
                block = block[6:].strip()
            return block
    return None


def _validate_python_code(code: str) -> CodeValidation:
    import subprocess
    import tempfile
    import shutil

    code_block = _extract_python_code(code)
    if not code_block:
        return CodeValidation(valid=True, errors=[], method="no_code_found")

    errors: list[str] = []
    method = "subprocess_ast"

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, prefix="ft_code_"
        ) as tmp:
            tmp.write(code_block)
            tmp_path = tmp.name

        proc = subprocess.run(
            [
                "python",
                "-c",
                "import ast, pathlib, sys; ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))",
                tmp_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            err_text = (proc.stderr or proc.stdout or "Unknown AST error").strip()
            for line in err_text.splitlines():
                if line.strip():
                    errors.append(line.strip())
            return CodeValidation(valid=False, errors=errors, method=method)

        ft_bin = shutil.which("freqtrade")
        if ft_bin and "IStrategy" in code_block:
            method = "subprocess_ast+freqtrade"
            try:
                import os
                strategy_dir = os.path.dirname(tmp_path)
                ft_proc = subprocess.run(
                    [ft_bin, "strategy-check", "--strategy-path", strategy_dir,
                     "--strategy", os.path.splitext(os.path.basename(tmp_path))[0]],
                    capture_output=True, text=True, timeout=30,
                )
                if ft_proc.returncode != 0:
                    ft_err = (ft_proc.stderr or ft_proc.stdout or "").strip()
                    if ft_err and "Error" in ft_err:
                        errors.append(f"FreqTrade check: {ft_err[:300]}")
            except Exception:
                pass

    except subprocess.TimeoutExpired:
        errors.append("Validation timed out")
        return CodeValidation(valid=False, errors=errors, method=method)
    except Exception as e:
        try:
            ast.parse(code_block)
        except SyntaxError as se:
            errors.append(f"Syntax error at line {se.lineno}: {se.msg}")
            return CodeValidation(valid=False, errors=errors, method="ast_parse_fallback")
        method = "ast_parse_fallback"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if errors:
        return CodeValidation(valid=False, errors=errors, method=method)
    return CodeValidation(valid=True, errors=[], method=method)

def _build_reasoner_prompt(goal_id: str | None = None) -> str:
    base = REASONER_SYSTEM_PROMPT
    if goal_id and goal_id in GOAL_DIRECTIVES:
        return f"{GOAL_DIRECTIVES[goal_id]}\n\n---\n\n{base}"
    return base


def _build_reasoner_msgs(
    task_prompt: str,
    context: str,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> list[dict]:
    system = _build_reasoner_prompt(goal_id)
    if has_strategy_source:
        system = f"{CODE_AWARE_ADVISOR_SYSTEM_PROMPT}\n\n---\n\n{system}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]
def list_pipeline_logs(limit: int = 50) -> list[dict]:
    ensure_dir(PIPELINE_LOG_DIR)
    logs = []
    for f in sorted(PIPELINE_LOG_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        from ...core.json_io import read_json
        data = read_json(f, None)
        if data:
            logs.append(data)
    return logs


def get_pipeline_log(run_id: str) -> dict | None:
    from ...core.json_io import read_json
    return read_json(PIPELINE_LOG_DIR / f"{run_id}.json", None)


# ---------------------------------------------------------------------------
# Canonical trace-aware orchestration for the live AI chat stack.
# ---------------------------------------------------------------------------

@dataclass
class PipelineStep:
    role: str
    model_id: str
    provider: str | None = None
    requested_provider: str | None = None
    requested_model_id: str | None = None
    duration_ms: int = 0
    attempt_count: int = 1
    fallback_used: bool = False
    fallback_reason: str | None = None
    fallback_chain: list[str] = field(default_factory=list)
    key_slot: str | None = None
    selection_reason: str = ""
    output_preview: str = ""
    output_full: str = ""
    provider_attempts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("output_full", None)
        return data


@dataclass
class PipelineResult:
    final_text: str
    pipeline_type: str
    steps: list[PipelineStep] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    total_duration_ms: int = 0
    confidence: float | None = None
    consensus: bool | None = None
    disagreements: list[str] = field(default_factory=list)
    judge_activated: bool | None = None
    judge_reason: str | None = None
    classification: Classification | None = None
    run_id: str = ""
    code_validation: CodeValidation | None = None
    context_metadata: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "final_text": self.final_text,
            "pipeline_type": self.pipeline_type,
            "steps": [step.to_dict() for step in self.steps],
            "trace": self.trace,
            "total_duration_ms": self.total_duration_ms,
            "confidence": self.confidence,
            "consensus": self.consensus,
            "disagreements": self.disagreements,
            "judge_activated": self.judge_activated,
            "judge_reason": self.judge_reason,
            "run_id": self.run_id,
        }
        if self.classification:
            data["classification"] = self.classification.model_dump()
        if self.code_validation:
            data["code_validation"] = self.code_validation.to_dict()
        if self.context_metadata:
            data["context_metadata"] = self.context_metadata
        return data


def _short_preview(text: str | None, limit: int = 220) -> str:
    flattened = " ".join((text or "").split())
    if len(flattened) <= limit:
        return flattened
    return flattened[: limit - 3] + "..."


def _requested_provider_for_model(model_id: str | None) -> str:
    if model_id and str(model_id).startswith("ollama/"):
        return "ollama"
    return _current_provider.get()


def _make_trace_event(
    event_type: str,
    *,
    role: str | None = None,
    model_id: str | None = None,
    provider: str | None = None,
    requested_model_id: str | None = None,
    requested_provider: str | None = None,
    duration_ms: int | None = None,
    output_preview: str | None = None,
    selection_reason: str | None = None,
    attempt_count: int | None = None,
    fallback_used: bool | None = None,
    fallback_chain: list[str] | None = None,
    key_slot: str | None = None,
    pipeline_type: str | None = None,
    classification: Classification | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {"event_type": event_type}
    if role is not None:
        event["role"] = role
    if model_id is not None:
        event["model_id"] = model_id
    if provider is not None:
        event["provider"] = provider
    if requested_model_id is not None:
        event["requested_model_id"] = requested_model_id
    if requested_provider is not None:
        event["requested_provider"] = requested_provider
    if duration_ms is not None:
        event["duration_ms"] = duration_ms
    if output_preview:
        event["output_preview"] = output_preview
    if selection_reason:
        event["selection_reason"] = selection_reason
    if attempt_count is not None:
        event["attempt_count"] = attempt_count
    if fallback_used is not None:
        event["fallback_used"] = fallback_used
    if fallback_chain:
        event["fallback_chain"] = fallback_chain
    if key_slot:
        event["key_slot"] = key_slot
    if pipeline_type:
        event["pipeline_type"] = pipeline_type
    if classification is not None:
        event["classification"] = classification.model_dump()
    if extra:
        event.update(extra)
    return event


def _step_from_output(
    *,
    role: str,
    requested_model_id: str,
    selection_reason: str,
    started_at: float,
    output_text: str,
    error_text: str | None = None,
) -> PipelineStep:
    dispatch_meta = _dispatch.get_last_dispatch_meta() or {}
    actual_model = dispatch_meta.get("model") or requested_model_id
    actual_provider = dispatch_meta.get("provider") or _requested_provider_for_model(actual_model)
    requested_provider = dispatch_meta.get("requested_provider") or _requested_provider_for_model(requested_model_id)
    provider_attempts = dispatch_meta.get("provider_attempts") or []
    fallback_reason = error_text
    if not fallback_reason and provider_attempts:
        fallback_reason = provider_attempts[-1].get("error")

    step = PipelineStep(
        role=role,
        model_id=actual_model,
        provider=actual_provider,
        requested_provider=requested_provider,
        requested_model_id=requested_model_id,
        duration_ms=int((time.monotonic() - started_at) * 1000),
        attempt_count=int(dispatch_meta.get("attempt_count") or 1),
        fallback_used=bool(dispatch_meta.get("fallback_used")),
        fallback_reason=fallback_reason,
        fallback_chain=list(dispatch_meta.get("fallback_chain") or []),
        key_slot=dispatch_meta.get("key_slot"),
        selection_reason=selection_reason,
        output_preview=_short_preview(output_text),
        output_full=output_text,
        provider_attempts=provider_attempts,
    )
    rate_limited = False
    if step.fallback_reason and "429" in str(step.fallback_reason):
        rate_limited = True
    success = not str(output_text).startswith("[Error:")
    record_observation(
        role=role,
        model_id=actual_model,
        success=success,
        latency_ms=step.duration_ms,
        rate_limited=rate_limited,
    )
    return step


def _trace_for_step(event_type: str, step: PipelineStep, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return _make_trace_event(
        event_type,
        role=step.role,
        model_id=step.model_id,
        provider=step.provider,
        requested_model_id=step.requested_model_id,
        requested_provider=step.requested_provider,
        duration_ms=step.duration_ms,
        output_preview=step.output_preview,
        selection_reason=step.selection_reason,
        attempt_count=step.attempt_count,
        fallback_used=step.fallback_used,
        fallback_chain=step.fallback_chain,
        key_slot=step.key_slot,
        extra=extra,
    )


def _classifier_step(classification: Classification) -> PipelineStep:
    return PipelineStep(
        role="classifier",
        model_id=classification.classifier_model_id,
        provider="ollama" if str(classification.classifier_model_id).startswith("ollama/") else _current_provider.get(),
        requested_provider=_current_provider.get(),
        requested_model_id=classification.classifier_model_id,
        duration_ms=classification.classifier_duration_ms,
        attempt_count=1,
        fallback_used=classification.classifier_fallback_used,
        fallback_reason=classification.classifier_fallback_reason,
        selection_reason=classification.classifier_selection_reason,
        output_preview=f"pipeline={classification.recommended_pipeline.value} complexity={classification.complexity.value}",
        output_full=classification.model_dump_json(),
    )


async def _call_model(
    role: str,
    messages: list[dict],
    models: list,
    role_overrides: dict[str, str] | None = None,
) -> PipelineStep:
    requested_model_id, selection_reason = get_model_for_role(role, models, role_overrides)
    started_at = time.monotonic()
    try:
        output_text = await chat_complete(messages, model=requested_model_id)
        return _step_from_output(
            role=role,
            requested_model_id=requested_model_id,
            selection_reason=selection_reason,
            started_at=started_at,
            output_text=output_text,
        )
    except Exception as exc:
        logger.error("Model call failed for role %s using %s: %s", role, requested_model_id, exc)
        return _step_from_output(
            role=role,
            requested_model_id=requested_model_id,
            selection_reason=selection_reason,
            started_at=started_at,
            output_text=f"[Error: model unavailable for {role}]",
            error_text=str(exc),
        )


def _step_start_event(role: str, requested_model_id: str, selection_reason: str, status: str | None = None) -> dict[str, Any]:
    requested_provider = _requested_provider_for_model(requested_model_id)
    extra = {"status": status} if status else None
    return _make_trace_event(
        "step_start",
        role=role,
        model_id=requested_model_id,
        provider=requested_provider,
        requested_model_id=requested_model_id,
        requested_provider=requested_provider,
        selection_reason=selection_reason,
        extra=extra,
    )


def _judge_system_prompt(goal_id: str | None) -> str:
    goal_guidance = GOAL_DIRECTIVES.get(goal_id or "", GOAL_DIRECTIVES.get("balanced", ""))
    return JUDGE_SYSTEM_PROMPT_TEMPLATE.format(goal_directive=goal_guidance)


def _analyst_messages(
    *,
    task_prompt: str,
    context: str,
    goal_id: str | None,
    has_strategy_source: bool,
    framing: str,
) -> list[dict[str, str]]:
    analyst_system = ANALYST_SYSTEM_PROMPT
    goal_prompt = GOAL_DIRECTIVES.get(goal_id or "", "")
    if goal_prompt:
        analyst_system = f"{goal_prompt}\n\n---\n\n{analyst_system}"
    if has_strategy_source:
        analyst_system = f"{CODE_AWARE_ADVISOR_SYSTEM_PROMPT}\n\n---\n\n{analyst_system}"
    analyst_system = f"{analyst_system}\n\n{framing}"
    return [
        {"role": "system", "content": analyst_system},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]


def _result_from_pipeline_dict(pipeline: dict[str, Any], final_text: str) -> PipelineResult:
    steps = [PipelineStep(**step) for step in pipeline.get("steps", [])]
    return PipelineResult(
        final_text=final_text,
        pipeline_type=pipeline.get("pipeline_type", "simple"),
        steps=steps,
        trace=pipeline.get("trace", []),
        total_duration_ms=pipeline.get("total_duration_ms", 0),
        confidence=pipeline.get("confidence"),
        consensus=pipeline.get("consensus"),
        disagreements=pipeline.get("disagreements", []),
        judge_activated=pipeline.get("judge_activated"),
        judge_reason=pipeline.get("judge_reason"),
        run_id=pipeline.get("run_id", ""),
        code_validation=CodeValidation(**pipeline["code_validation"]) if pipeline.get("code_validation") else None,
        context_metadata=pipeline.get("context_metadata"),
    )


async def run(
    task_text: str,
    context: str = "",
    role_overrides: dict[str, str] | None = None,
    context_hint: str | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
    provider: str = "openrouter",
    context_metadata: dict[str, Any] | None = None,
) -> PipelineResult:
    final_text = ""
    final_pipeline: dict[str, Any] | None = None
    async for event in stream_run(
        task_text=task_text,
        context=context,
        role_overrides=role_overrides,
        context_hint=context_hint,
        goal_id=goal_id,
        has_strategy_source=has_strategy_source,
        provider=provider,
        context_metadata=context_metadata,
    ):
        if event.get("delta"):
            final_text += event["delta"]
        if event.get("done"):
            final_text = event.get("fullText") or final_text
            final_pipeline = event.get("pipeline")
            break
    if final_pipeline is None:
        return PipelineResult(final_text=final_text, pipeline_type="simple")
    return _result_from_pipeline_dict(final_pipeline, final_text)


async def stream_run(
    task_text: str,
    context: str = "",
    role_overrides: dict[str, str] | None = None,
    context_hint: str | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
    provider: str = "openrouter",
    context_metadata: dict[str, Any] | None = None,
) -> AsyncGenerator[dict, None]:
    _current_provider.set(provider)
    classification = await classify(
        task_text,
        context_hint=context_hint,
        role_overrides=role_overrides,
        provider=_current_provider.get(),
    )
    pipeline = classification.recommended_pipeline
    classifier_step = _classifier_step(classification)
    trace: list[dict[str, Any]] = []
    steps: list[PipelineStep] = [classifier_step]
    started_at = time.monotonic()
    models = await fetch_free_models(_current_provider.get())

    classifier_event = _make_trace_event(
        "classifier_decision",
        role=classifier_step.role,
        model_id=classifier_step.model_id,
        provider=classifier_step.provider,
        requested_model_id=classifier_step.requested_model_id,
        requested_provider=classifier_step.requested_provider,
        duration_ms=classifier_step.duration_ms,
        output_preview=classifier_step.output_preview,
        selection_reason=classifier_step.selection_reason,
        fallback_used=classifier_step.fallback_used,
        pipeline_type=pipeline.value,
        classification=classification,
        extra={"status": "classified"},
    )
    trace.append(classifier_event)
    yield classifier_event

    pipeline_event = _make_trace_event(
        "pipeline_selected",
        role="orchestrator",
        pipeline_type=pipeline.value,
        output_preview=f"Selected {pipeline.value} pipeline for {classification.complexity.value} complexity request.",
        extra={"status": "classified", "pipeline_type": pipeline.value},
    )
    trace.append(pipeline_event)
    yield pipeline_event

    logger.info(
        "Orchestrator stream v2: classified as %s/%s -> pipeline=%s",
        [task.value for task in classification.task_types],
        classification.complexity.value,
        pipeline.value,
    )

    final_text = ""
    confidence: float | None = classification.confidence
    consensus: bool | None = None
    disagreements: list[str] = []
    judge_activated: bool | None = None
    judge_reason: str | None = None
    code_validation: CodeValidation | None = None

    if pipeline == PipelineType.simple:
        messages = [{"role": "user", "content": task_text}]
        if context:
            messages = [
                {"role": "system", "content": f"Context:\n{context}"},
                {"role": "user", "content": task_text},
            ]
        requested_model_id, selection_reason = get_model_for_role("explainer", models, role_overrides)
        start_event = _step_start_event("explainer", requested_model_id, selection_reason)
        trace.append(start_event)
        yield start_event
        stream_started = time.monotonic()
        async for chunk in stream_chat(messages, model=requested_model_id):
            if chunk.get("error"):
                yield {"error": chunk["error"], "done": True}
                return
            if chunk.get("delta"):
                final_text += chunk["delta"]
                yield {"delta": chunk["delta"], "done": False}
            if chunk.get("done"):
                break
        step = _step_from_output(
            role="explainer",
            requested_model_id=requested_model_id,
            selection_reason=selection_reason,
            started_at=stream_started,
            output_text=final_text,
        )
        steps.append(step)
        complete_event = _trace_for_step("step_complete", step)
        trace.append(complete_event)
        yield complete_event

    elif pipeline == PipelineType.analysis:
        reasoner_msgs = _build_reasoner_msgs(task_text, context, goal_id, has_strategy_source)
        reasoner_requested_model, reasoner_reason = get_model_for_role("reasoner", models, role_overrides)
        start_event = _step_start_event("reasoner", reasoner_requested_model, reasoner_reason, "reasoning")
        trace.append(start_event)
        yield start_event
        reasoner_step = await _call_model("reasoner", reasoner_msgs, models, role_overrides)
        steps.append(reasoner_step)
        complete_event = _trace_for_step("step_complete", reasoner_step, {"status": "reasoning"})
        trace.append(complete_event)
        yield complete_event

        composer_msgs = [
            {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Rewrite this analysis for the user:\n\n{reasoner_step.output_full}"},
        ]
        composer_requested_model, composer_reason = get_model_for_role("composer", models, role_overrides)
        start_event = _step_start_event("composer", composer_requested_model, composer_reason, "composing")
        trace.append(start_event)
        yield start_event
        stream_started = time.monotonic()
        async for chunk in stream_chat(composer_msgs, model=composer_requested_model):
            if chunk.get("error"):
                yield {"error": chunk["error"], "done": True}
                return
            if chunk.get("delta"):
                final_text += chunk["delta"]
                yield {"delta": chunk["delta"], "done": False}
            if chunk.get("done"):
                break
        composer_step = _step_from_output(
            role="composer",
            requested_model_id=composer_requested_model,
            selection_reason=composer_reason,
            started_at=stream_started,
            output_text=final_text,
        )
        steps.append(composer_step)
        complete_event = _trace_for_step("step_complete", composer_step, {"status": "composing"})
        trace.append(complete_event)
        yield complete_event

    elif pipeline == PipelineType.debate:
        analyst_a_msgs = _analyst_messages(
            task_prompt=task_text,
            context=context,
            goal_id=goal_id,
            has_strategy_source=has_strategy_source,
            framing="You are Analyst A. Build the strongest upside case aligned to the user's goal. Focus on opportunity, upside asymmetry, and why the strategy can work if executed well.",
        )
        analyst_b_msgs = _analyst_messages(
            task_prompt=task_text,
            context=context,
            goal_id=goal_id,
            has_strategy_source=has_strategy_source,
            framing="You are Analyst B. Stress-test the idea. Focus on downside, drawdowns, overfitting, fragility, regime dependence, and reasons the user should be cautious.",
        )
        analyst_a_model, analyst_a_reason = get_model_for_role("analyst_a", models, role_overrides)
        analyst_b_model, analyst_b_reason = get_model_for_role("analyst_b", models, role_overrides)
        analyst_a_start = _step_start_event("analyst_a", analyst_a_model, analyst_a_reason, "analyzing")
        analyst_b_start = _step_start_event("analyst_b", analyst_b_model, analyst_b_reason, "analyzing")
        trace.extend([analyst_a_start, analyst_b_start])
        yield analyst_a_start
        yield analyst_b_start
        analyst_a_step, analyst_b_step = await asyncio.gather(
            _call_model("analyst_a", analyst_a_msgs, models, role_overrides),
            _call_model("analyst_b", analyst_b_msgs, models, role_overrides),
        )
        steps.extend([analyst_a_step, analyst_b_step])
        analyst_a_complete = _trace_for_step("step_complete", analyst_a_step, {"status": "analyzing"})
        analyst_b_complete = _trace_for_step("step_complete", analyst_b_step, {"status": "analyzing"})
        trace.extend([analyst_a_complete, analyst_b_complete])
        yield analyst_a_complete
        yield analyst_b_complete

        judge_activated = True
        judge_reason = "always_on_for_debate"
        judge_msgs = [
            {"role": "system", "content": _judge_system_prompt(goal_id)},
            {"role": "user", "content": f"""User request: {task_text}

=== ANALYST A: UPSIDE CASE ===
{analyst_a_step.output_full}

=== ANALYST B: SKEPTICAL CASE ===
{analyst_b_step.output_full}

Use both perspectives and resolve the disagreement explicitly."""},
        ]
        judge_model, judge_selection_reason = get_model_for_role("judge", models, role_overrides)
        judge_start = _step_start_event("judge", judge_model, judge_selection_reason, "judging")
        trace.append(judge_start)
        yield judge_start
        stream_started = time.monotonic()
        async for chunk in stream_chat(judge_msgs, model=judge_model):
            if chunk.get("error"):
                yield {"error": chunk["error"], "done": True}
                return
            if chunk.get("delta"):
                final_text += chunk["delta"]
                yield {"delta": chunk["delta"], "done": False}
            if chunk.get("done"):
                break
        judge_step = _step_from_output(
            role="judge",
            requested_model_id=judge_model,
            selection_reason=judge_selection_reason,
            started_at=stream_started,
            output_text=final_text,
        )
        steps.append(judge_step)
        complete_event = _trace_for_step("step_complete", judge_step, {"status": "judging"})
        trace.append(complete_event)
        yield complete_event
        disagreements = []
        for line in final_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("-") and "agreement" not in stripped.lower():
                disagreements.append(stripped.lstrip("- ").strip())

    elif pipeline == PipelineType.code:
        code_msgs = [
            {"role": "system", "content": CODE_GEN_SYSTEM_PROMPT},
            {"role": "user", "content": f"{task_text}\n\n--- CONTEXT ---\n{context}"},
        ]
        code_model, code_reason = get_model_for_role("code_gen", models, role_overrides)
        start_event = _step_start_event("code_gen", code_model, code_reason, "generating_code")
        trace.append(start_event)
        yield start_event
        code_step = await _call_model("code_gen", code_msgs, models, role_overrides)
        steps.append(code_step)
        complete_event = _trace_for_step("step_complete", code_step, {"status": "generating_code"})
        trace.append(complete_event)
        yield complete_event

        validator_start = _make_trace_event(
            "step_start",
            role="validator",
            model_id="local/python-validator",
            provider="local",
            requested_model_id="local/python-validator",
            requested_provider="local",
            selection_reason="local:validation",
            extra={"status": "validating_code"},
        )
        trace.append(validator_start)
        yield validator_start
        validation_started = time.monotonic()
        code_validation = _validate_python_code(code_step.output_full)
        validator_step = PipelineStep(
            role="validator",
            model_id="local/python-validator",
            provider="local",
            requested_provider="local",
            requested_model_id="local/python-validator",
            duration_ms=int((time.monotonic() - validation_started) * 1000),
            selection_reason="local:validation",
            output_preview=_short_preview(", ".join(code_validation.errors) if code_validation.errors else code_validation.method),
            output_full=code_validation.to_dict().__repr__(),
        )
        steps.append(validator_step)
        validator_complete = _trace_for_step("step_complete", validator_step, {"status": "validating_code"})
        trace.append(validator_complete)
        yield validator_complete

        explainer_msgs = [
            {"role": "system", "content": CODE_EXPLAINER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Explain this code/change:\n\n{code_step.output_full}"},
        ]
        explainer_model, explainer_reason = get_model_for_role("explainer", models, role_overrides)
        start_event = _step_start_event("explainer", explainer_model, explainer_reason, "explaining")
        trace.append(start_event)
        yield start_event
        stream_started = time.monotonic()
        async for chunk in stream_chat(explainer_msgs, model=explainer_model):
            if chunk.get("error"):
                yield {"error": chunk["error"], "done": True}
                return
            if chunk.get("delta"):
                final_text += chunk["delta"]
                yield {"delta": chunk["delta"], "done": False}
            if chunk.get("done"):
                break
        code_suffix = f"\n\n---\n\n**Generated Code:**\n\n{code_step.output_full}"
        final_text += code_suffix
        yield {"delta": code_suffix, "done": False}
        explainer_step = _step_from_output(
            role="explainer",
            requested_model_id=explainer_model,
            selection_reason=explainer_reason,
            started_at=stream_started,
            output_text=final_text,
        )
        steps.append(explainer_step)
        complete_event = _trace_for_step("step_complete", explainer_step, {"status": "explaining"})
        trace.append(complete_event)
        yield complete_event

    elif pipeline == PipelineType.tool:
        tool_msgs = [
            {"role": "system", "content": TOOL_CALLER_SYSTEM_PROMPT},
            {"role": "user", "content": f"{task_text}\n\n--- CONTEXT ---\n{context}"},
        ]
        tool_model, tool_reason = get_model_for_role("tool_caller", models, role_overrides)
        start_event = _step_start_event("tool_caller", tool_model, tool_reason, "planning_tools")
        trace.append(start_event)
        yield start_event
        tool_step = await _call_model("tool_caller", tool_msgs, models, role_overrides)
        steps.append(tool_step)
        complete_event = _trace_for_step("step_complete", tool_step, {"status": "planning_tools"})
        trace.append(complete_event)
        yield complete_event

        reasoner_msgs = _build_reasoner_msgs(
            f"Tool plan:\n{tool_step.output_full}\n\nOriginal request: {task_text}",
            context,
            goal_id,
            has_strategy_source,
        )
        reasoner_model, reasoner_reason = get_model_for_role("reasoner", models, role_overrides)
        start_event = _step_start_event("reasoner", reasoner_model, reasoner_reason, "reasoning")
        trace.append(start_event)
        yield start_event
        reasoner_step = await _call_model("reasoner", reasoner_msgs, models, role_overrides)
        steps.append(reasoner_step)
        complete_event = _trace_for_step("step_complete", reasoner_step, {"status": "reasoning"})
        trace.append(complete_event)
        yield complete_event

        composer_msgs = [
            {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Tool execution result:\n{tool_step.output_full}\n\nReasoning analysis:\n{reasoner_step.output_full}\n\nOriginal request: {task_text}"},
        ]
        composer_model, composer_reason = get_model_for_role("composer", models, role_overrides)
        start_event = _step_start_event("composer", composer_model, composer_reason, "composing")
        trace.append(start_event)
        yield start_event
        stream_started = time.monotonic()
        async for chunk in stream_chat(composer_msgs, model=composer_model):
            if chunk.get("error"):
                yield {"error": chunk["error"], "done": True}
                return
            if chunk.get("delta"):
                final_text += chunk["delta"]
                yield {"delta": chunk["delta"], "done": False}
            if chunk.get("done"):
                break
        composer_step = _step_from_output(
            role="composer",
            requested_model_id=composer_model,
            selection_reason=composer_reason,
            started_at=stream_started,
            output_text=final_text,
        )
        steps.append(composer_step)
        complete_event = _trace_for_step("step_complete", composer_step, {"status": "composing"})
        trace.append(complete_event)
        yield complete_event

    else:
        structured_msgs = [
            {"role": "system", "content": STRUCTURED_OUTPUT_SYSTEM_PROMPT},
            {"role": "user", "content": f"{task_text}\n\n--- CONTEXT ---\n{context}"},
        ]
        structured_model, structured_reason = get_model_for_role("structured_output", models, role_overrides)
        start_event = _step_start_event("structured_output", structured_model, structured_reason, "structured_output")
        trace.append(start_event)
        yield start_event
        structured_step = await _call_model("structured_output", structured_msgs, models, role_overrides)
        steps.append(structured_step)
        complete_event = _trace_for_step("step_complete", structured_step, {"status": "structured_output"})
        trace.append(complete_event)
        yield complete_event
        final_text = structured_step.output_full
        yield {"delta": final_text, "done": False}

    trace.append({
        "event_type": "final",
        "pipeline_type": pipeline.value,
        "duration_ms": int((time.monotonic() - started_at) * 1000),
        "output_preview": _short_preview(final_text),
    })

    result = PipelineResult(
        final_text=final_text,
        pipeline_type=pipeline.value,
        steps=steps,
        trace=trace,
        total_duration_ms=int((time.monotonic() - started_at) * 1000),
        confidence=confidence,
        consensus=consensus,
        disagreements=disagreements,
        judge_activated=judge_activated,
        judge_reason=judge_reason,
        classification=classification,
        run_id=str(uuid.uuid4()),
        code_validation=code_validation,
        context_metadata=context_metadata,
    )
    _save_log(result)
    pipeline_info = result.to_dict()
    pipeline_info.pop("final_text", None)
    final_event = {
        "event_type": "final",
        "done": True,
        "fullText": final_text,
        "pipeline": pipeline_info,
    }
    yield final_event
