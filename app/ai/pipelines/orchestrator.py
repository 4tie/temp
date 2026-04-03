"""
AI Pipeline Orchestrator — multi-model pipeline engine.
Supports 6 pipeline types: simple, analysis, debate, code, structured, tool.
Supports true streaming for the final pipeline step.
Logs every run to user_data/ai_pipeline_logs/.
"""
from __future__ import annotations

import ast
import asyncio
import contextvars
import json
import logging
import tempfile
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, AsyncGenerator

from ...core.storage import write_json, _ensure
import app.ai.models.provider_dispatch as _dispatch
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

PIPELINE_LOG_DIR = Path("user_data/ai_pipeline_logs")


@dataclass
class PipelineStep:
    role: str
    model_id: str
    duration_ms: int = 0
    fallback_used: bool = False
    fallback_reason: str | None = None
    selection_reason: str = ""
    output_preview: str = ""
    output_full: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("output_full", None)
        return d


@dataclass
class CodeValidation:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    method: str = "ast_parse"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PipelineResult:
    final_text: str
    pipeline_type: str
    steps: list[PipelineStep] = field(default_factory=list)
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

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "final_text": self.final_text,
            "pipeline_type": self.pipeline_type,
            "steps": [s.to_dict() for s in self.steps],
            "total_duration_ms": self.total_duration_ms,
            "confidence": self.confidence,
            "consensus": self.consensus,
            "disagreements": self.disagreements,
            "judge_activated": self.judge_activated,
            "judge_reason": self.judge_reason,
            "run_id": self.run_id,
        }
        if self.classification:
            d["classification"] = self.classification.model_dump()
        if self.code_validation:
            d["code_validation"] = self.code_validation.to_dict()
        if self.context_metadata:
            d["context_metadata"] = self.context_metadata
        return d


LAST_RESORT_MODEL = "openrouter/free"


async def _call_model(
    role: str,
    messages: list[dict],
    models: list,
    role_overrides: dict[str, str] | None = None,
) -> PipelineStep:
    model_id, reason = get_model_for_role(role, models, role_overrides)
    start = time.monotonic()
    fallback_used = False
    fallback_reason = None
    selection_reason = reason

    try:
        result = await chat_complete(messages, model=model_id)
    except Exception as e:
        logger.warning("Model %s failed for role %s: %s — trying fallback", model_id, role, e)
        fallback_used = True
        fallback_reason = str(e)
        selection_reason = f"fallback:{reason}→{LAST_RESORT_MODEL}"
        try:
            result = await chat_complete(messages, model=LAST_RESORT_MODEL)
            model_id = LAST_RESORT_MODEL
        except Exception as e2:
            logger.error("Fallback also failed for role %s: %s", role, e2)
            result = f"[Error: model unavailable for {role}]"

    duration = int((time.monotonic() - start) * 1000)
    return PipelineStep(
        role=role,
        model_id=model_id,
        duration_ms=duration,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        selection_reason=selection_reason,
        output_preview=result[:200],
        output_full=result,
    )


def _save_log(result: PipelineResult) -> None:
    _ensure(PIPELINE_LOG_DIR)
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
            ["python", "-c", f"import ast; ast.parse(open('{tmp_path}').read())"],
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
            import os
            os.unlink(tmp_path)
        except Exception:
            pass

    if errors:
        return CodeValidation(valid=False, errors=errors, method=method)
    return CodeValidation(valid=True, errors=[], method=method)


async def run_simple(
    messages: list[dict],
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> PipelineResult:
    models = await fetch_free_models(_current_provider.get())
    start = time.monotonic()

    step = await _call_model("explainer", messages, models, role_overrides)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=step.output_full,
        pipeline_type="simple",
        steps=[step],
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


async def stream_simple(
    messages: list[dict],
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> AsyncGenerator[dict, None]:
    models = await fetch_free_models(_current_provider.get())
    model_id, reason = get_model_for_role("explainer", models, role_overrides)
    start = time.monotonic()

    full_text = ""
    async for chunk in stream_chat(messages, model=model_id):
        if chunk.get("error"):
            yield {"error": chunk["error"], "done": True}
            return
        if chunk.get("delta"):
            full_text += chunk["delta"]
            yield {"delta": chunk["delta"], "done": False}
        if chunk.get("done"):
            break

    duration = int((time.monotonic() - start) * 1000)
    step = PipelineStep(
        role="explainer", model_id=model_id, duration_ms=duration,
        selection_reason=reason, output_preview=full_text[:200], output_full=full_text,
    )
    result = PipelineResult(
        final_text=full_text, pipeline_type="simple", steps=[step],
        total_duration_ms=duration, classification=classification,
        run_id=str(uuid.uuid4()),
    )
    _save_log(result)
    pipeline_info = result.to_dict()
    pipeline_info.pop("final_text", None)
    yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


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


async def run_analysis(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> PipelineResult:
    models = await fetch_free_models(_current_provider.get())
    start = time.monotonic()
    steps: list[PipelineStep] = []

    reasoner_msgs = _build_reasoner_msgs(task_prompt, context, goal_id, has_strategy_source)
    reasoner_step = await _call_model("reasoner", reasoner_msgs, models, role_overrides)
    steps.append(reasoner_step)

    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Rewrite this analysis for the user:\n\n{reasoner_step.output_full}"},
    ]
    composer_step = await _call_model("composer", composer_msgs, models, role_overrides)
    steps.append(composer_step)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=composer_step.output_full,
        pipeline_type="analysis",
        steps=steps,
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


async def stream_analysis(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> AsyncGenerator[dict, None]:
    models = await fetch_free_models(_current_provider.get())
    start = time.monotonic()
    steps: list[PipelineStep] = []

    yield {"status": "reasoning", "done": False}

    reasoner_msgs = _build_reasoner_msgs(task_prompt, context, goal_id, has_strategy_source)
    reasoner_step = await _call_model("reasoner", reasoner_msgs, models, role_overrides)
    steps.append(reasoner_step)

    yield {"status": "composing", "done": False}

    model_id, reason = get_model_for_role("composer", models, role_overrides)
    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Rewrite this analysis for the user:\n\n{reasoner_step.output_full}"},
    ]

    full_text = ""
    async for chunk in stream_chat(composer_msgs, model=model_id):
        if chunk.get("error"):
            yield {"error": chunk["error"], "done": True}
            return
        if chunk.get("delta"):
            full_text += chunk["delta"]
            yield {"delta": chunk["delta"], "done": False}
        if chunk.get("done"):
            break

    composer_duration = int((time.monotonic() - start) * 1000) - sum(s.duration_ms for s in steps)
    steps.append(PipelineStep(
        role="composer", model_id=model_id, duration_ms=composer_duration,
        selection_reason=reason, output_preview=full_text[:200], output_full=full_text,
    ))

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=full_text, pipeline_type="analysis", steps=steps,
        total_duration_ms=total_ms, classification=classification,
        run_id=str(uuid.uuid4()),
    )
    _save_log(result)
    pipeline_info = result.to_dict()
    pipeline_info.pop("final_text", None)
    yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


async def run_debate(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> PipelineResult:
    models = await fetch_free_models(_current_provider.get())
    start = time.monotonic()
    steps: list[PipelineStep] = []

    analyst_system = ANALYST_SYSTEM_PROMPT
    if goal_id and goal_id in GOAL_DIRECTIVES:
        analyst_system = f"{GOAL_DIRECTIVES[goal_id]}\n\n---\n\n{analyst_system}"
    if has_strategy_source:
        analyst_system = f"{CODE_AWARE_ADVISOR_SYSTEM_PROMPT}\n\n---\n\n{analyst_system}"
    analyst_msgs = [
        {"role": "system", "content": analyst_system},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]

    analyst_a_task = _call_model("analyst_a", analyst_msgs, models, role_overrides)
    analyst_b_task = _call_model("analyst_b", analyst_msgs, models, role_overrides)
    analyst_a_step, analyst_b_step = await asyncio.gather(analyst_a_task, analyst_b_task)
    steps.extend([analyst_a_step, analyst_b_step])

    should_judge = True
    judge_reason = "complexity=high"
    if classification and classification.complexity != ComplexityLevel.high:
        len_a = len(analyst_a_step.output_full)
        len_b = len(analyst_b_step.output_full)
        ratio = max(len_a, len_b) / max(min(len_a, len_b), 1)
        should_judge = ratio > 1.4
        judge_reason = f"output_ratio={ratio:.2f}>1.4" if should_judge else f"output_ratio={ratio:.2f}<=1.4 (skipped)"

    if should_judge:
        judge_msgs = [
            {"role": "system", "content": """You are a senior analyst judge. Compare two independent analyses of the same trading strategy.
Return ONLY valid JSON (no markdown):
{
  "shared_conclusions": ["conclusion 1", "conclusion 2"],
  "disagreements": ["point of disagreement 1"],
  "confidence": 0.85,
  "best_recommendation": "The strongest recommendation from either analysis",
  "weak_points": ["weak point 1"]
}"""},
            {"role": "user", "content": f"""Compare these two analyses:

=== ANALYST A ===
{analyst_a_step.output_full}

=== ANALYST B ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""},
        ]
        judge_step = await _call_model("judge", judge_msgs, models, role_overrides)
        steps.append(judge_step)

        confidence = None
        consensus = None
        disagreements: list[str] = []

        try:
            judge_text = judge_step.output_full.strip()
            js = judge_text.find("{")
            je = judge_text.rfind("}") + 1
            if js >= 0 and je > js:
                judge_data = json.loads(judge_text[js:je])
                confidence = float(judge_data.get("confidence", 0.7))
                disagreements = judge_data.get("disagreements", [])
                shared = judge_data.get("shared_conclusions", [])
                consensus = len(disagreements) <= len(shared)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Judge output parse error: %s", e)
            confidence = 0.6

        composer_input = f"""Based on two independent analyses and a judge review, compose the final answer.

Judge summary: {judge_step.output_full}

=== FULL ANALYST A OUTPUT ===
{analyst_a_step.output_full}

=== FULL ANALYST B OUTPUT ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""
    else:
        confidence = 0.75
        consensus = True
        disagreements = []
        composer_input = f"""Compose a clear final answer from these analyses:

=== ANALYST A ===
{analyst_a_step.output_full}

=== ANALYST B ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""

    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": composer_input},
    ]
    composer_step = await _call_model("composer", composer_msgs, models, role_overrides)
    steps.append(composer_step)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=composer_step.output_full,
        pipeline_type="debate",
        steps=steps,
        total_duration_ms=total_ms,
        confidence=confidence,
        consensus=consensus,
        disagreements=disagreements,
        judge_activated=should_judge,
        judge_reason=judge_reason,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


async def stream_debate(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> AsyncGenerator[dict, None]:
    models = await fetch_free_models(_current_provider.get())
    start = time.monotonic()
    steps: list[PipelineStep] = []

    yield {"status": "analyzing", "done": False}

    analyst_system = ANALYST_SYSTEM_PROMPT
    if goal_id and goal_id in GOAL_DIRECTIVES:
        analyst_system = f"{GOAL_DIRECTIVES[goal_id]}\n\n---\n\n{analyst_system}"
    if has_strategy_source:
        analyst_system = f"{CODE_AWARE_ADVISOR_SYSTEM_PROMPT}\n\n---\n\n{analyst_system}"
    analyst_msgs = [
        {"role": "system", "content": analyst_system},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]

    analyst_a_task = _call_model("analyst_a", analyst_msgs, models, role_overrides)
    analyst_b_task = _call_model("analyst_b", analyst_msgs, models, role_overrides)
    analyst_a_step, analyst_b_step = await asyncio.gather(analyst_a_task, analyst_b_task)
    steps.extend([analyst_a_step, analyst_b_step])

    should_judge = True
    judge_reason = "complexity=high"
    if classification and classification.complexity != ComplexityLevel.high:
        len_a = len(analyst_a_step.output_full)
        len_b = len(analyst_b_step.output_full)
        ratio = max(len_a, len_b) / max(min(len_a, len_b), 1)
        should_judge = ratio > 1.4
        judge_reason = f"output_ratio={ratio:.2f}>1.4" if should_judge else f"output_ratio={ratio:.2f}<=1.4 (skipped)"

    confidence = 0.75
    consensus = True
    disagreements: list[str] = []

    if should_judge:
        yield {"status": "judging", "done": False}
        judge_msgs = [
            {"role": "system", "content": """You are a senior analyst judge. Compare two independent analyses of the same trading strategy.
Return ONLY valid JSON (no markdown):
{
  "shared_conclusions": ["conclusion 1", "conclusion 2"],
  "disagreements": ["point of disagreement 1"],
  "confidence": 0.85,
  "best_recommendation": "The strongest recommendation from either analysis",
  "weak_points": ["weak point 1"]
}"""},
            {"role": "user", "content": f"""Compare these two analyses:

=== ANALYST A ===
{analyst_a_step.output_full}

=== ANALYST B ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""},
        ]
        judge_step = await _call_model("judge", judge_msgs, models, role_overrides)
        steps.append(judge_step)

        try:
            judge_text = judge_step.output_full.strip()
            js = judge_text.find("{")
            je = judge_text.rfind("}") + 1
            if js >= 0 and je > js:
                judge_data = json.loads(judge_text[js:je])
                confidence = float(judge_data.get("confidence", 0.7))
                disagreements = judge_data.get("disagreements", [])
                shared = judge_data.get("shared_conclusions", [])
                consensus = len(disagreements) <= len(shared)
        except (json.JSONDecodeError, ValueError):
            confidence = 0.6

        composer_input = f"""Based on two independent analyses and a judge review, compose the final answer.

Judge summary: {judge_step.output_full}

=== FULL ANALYST A OUTPUT ===
{analyst_a_step.output_full}

=== FULL ANALYST B OUTPUT ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""
    else:
        composer_input = f"""Compose a clear final answer from these analyses:

=== ANALYST A ===
{analyst_a_step.output_full}

=== ANALYST B ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""

    yield {"status": "composing", "done": False}

    model_id, reason = get_model_for_role("composer", models, role_overrides)
    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": composer_input},
    ]

    full_text = ""
    async for chunk in stream_chat(composer_msgs, model=model_id):
        if chunk.get("error"):
            yield {"error": chunk["error"], "done": True}
            return
        if chunk.get("delta"):
            full_text += chunk["delta"]
            yield {"delta": chunk["delta"], "done": False}
        if chunk.get("done"):
            break

    composer_duration = int((time.monotonic() - start) * 1000) - sum(s.duration_ms for s in steps)
    steps.append(PipelineStep(
        role="composer", model_id=model_id, duration_ms=composer_duration,
        selection_reason=reason, output_preview=full_text[:200], output_full=full_text,
    ))

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=full_text, pipeline_type="debate", steps=steps,
        total_duration_ms=total_ms, confidence=confidence, consensus=consensus,
        disagreements=disagreements, judge_activated=should_judge, judge_reason=judge_reason,
        classification=classification, run_id=str(uuid.uuid4()),
    )
    _save_log(result)
    pipeline_info = result.to_dict()
    pipeline_info.pop("final_text", None)
    yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


async def run_code(
    context: str,
    code_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> PipelineResult:
    models = await fetch_free_models(_current_provider.get())
    start = time.monotonic()
    steps: list[PipelineStep] = []

    code_msgs = [
        {"role": "system", "content": CODE_GEN_SYSTEM_PROMPT},
        {"role": "user", "content": f"{code_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]
    code_step = await _call_model("code_gen", code_msgs, models, role_overrides)
    steps.append(code_step)

    validation = _validate_python_code(code_step.output_full)

    explainer_msgs = [
        {"role": "system", "content": CODE_EXPLAINER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Explain this code/change:\n\n{code_step.output_full}"},
    ]
    explainer_step = await _call_model("explainer", explainer_msgs, models, role_overrides)
    steps.append(explainer_step)

    final_text = f"{explainer_step.output_full}\n\n---\n\n**Generated Code:**\n\n{code_step.output_full}"

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=final_text,
        pipeline_type="code",
        steps=steps,
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
        code_validation=validation,
    )
    return result


async def stream_code(
    context: str,
    code_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> AsyncGenerator[dict, None]:
    models = await fetch_free_models(_current_provider.get())
    start = time.monotonic()
    steps: list[PipelineStep] = []

    yield {"status": "generating_code", "done": False}

    code_msgs = [
        {"role": "system", "content": CODE_GEN_SYSTEM_PROMPT},
        {"role": "user", "content": f"{code_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]
    code_step = await _call_model("code_gen", code_msgs, models, role_overrides)
    steps.append(code_step)

    yield {"status": "validating_code", "done": False}
    validation = _validate_python_code(code_step.output_full)

    yield {"status": "explaining", "done": False}

    model_id, reason = get_model_for_role("explainer", models, role_overrides)
    explainer_msgs = [
        {"role": "system", "content": CODE_EXPLAINER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Explain this code/change:\n\n{code_step.output_full}"},
    ]

    full_text = ""
    async for chunk in stream_chat(explainer_msgs, model=model_id):
        if chunk.get("error"):
            yield {"error": chunk["error"], "done": True}
            return
        if chunk.get("delta"):
            full_text += chunk["delta"]
            yield {"delta": chunk["delta"], "done": False}
        if chunk.get("done"):
            break

    full_text += f"\n\n---\n\n**Generated Code:**\n\n{code_step.output_full}"
    yield {"delta": f"\n\n---\n\n**Generated Code:**\n\n{code_step.output_full}", "done": False}

    explainer_duration = int((time.monotonic() - start) * 1000) - sum(s.duration_ms for s in steps)
    steps.append(PipelineStep(
        role="explainer", model_id=model_id, duration_ms=explainer_duration,
        selection_reason=reason, output_preview=full_text[:200], output_full=full_text,
    ))

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=full_text, pipeline_type="code", steps=steps,
        total_duration_ms=total_ms, classification=classification,
        run_id=str(uuid.uuid4()), code_validation=validation,
    )
    _save_log(result)
    pipeline_info = result.to_dict()
    pipeline_info.pop("final_text", None)
    yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


async def run_structured(
    context: str,
    task_prompt: str,
    schema_hint: str | None = None,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> PipelineResult:
    models = await fetch_free_models(_current_provider.get())
    start = time.monotonic()

    system = "You are a structured data generator. Return ONLY valid JSON — no markdown, no explanation, no text outside the JSON object."
    if schema_hint:
        system += f"\n\nExpected JSON schema:\n{schema_hint}"

    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]
    step = await _call_model("structured_output", msgs, models, role_overrides)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=step.output_full,
        pipeline_type="structured",
        steps=[step],
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


async def run_tool(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> PipelineResult:
    models = await fetch_free_models(_current_provider.get())
    start = time.monotonic()
    steps: list[PipelineStep] = []

    tool_msgs = [
        {"role": "system", "content": "You are a tool-calling assistant for a trading platform. Analyze the request and describe what tools/actions should be executed, with specific parameters and expected outcomes."},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]
    tool_step = await _call_model("tool_caller", tool_msgs, models, role_overrides)
    steps.append(tool_step)

    reasoner_msgs = [
        {"role": "system", "content": REASONER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Tool output:\n{tool_step.output_full}\n\nOriginal request: {task_prompt}\n\nContext:\n{context}"},
    ]
    reasoner_step = await _call_model("reasoner", reasoner_msgs, models, role_overrides)
    steps.append(reasoner_step)

    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Tool execution result:\n{tool_step.output_full}\n\nReasoning analysis:\n{reasoner_step.output_full}\n\nOriginal request: {task_prompt}"},
    ]
    composer_step = await _call_model("composer", composer_msgs, models, role_overrides)
    steps.append(composer_step)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=composer_step.output_full,
        pipeline_type="tool",
        steps=steps,
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


PIPELINE_RUNNERS = {
    PipelineType.simple: "simple",
    PipelineType.analysis: "analysis",
    PipelineType.debate: "debate",
    PipelineType.code: "code",
    PipelineType.structured: "structured",
    PipelineType.tool: "tool",
}


def _classifier_step(classification: Classification) -> PipelineStep:
    return PipelineStep(
        role="classifier",
        model_id=classification.classifier_model_id,
        duration_ms=classification.classifier_duration_ms,
        fallback_used=classification.classifier_fallback_used,
        fallback_reason=classification.classifier_fallback_reason,
        selection_reason=classification.classifier_selection_reason,
        output_preview=f"pipeline={classification.recommended_pipeline.value} complexity={classification.complexity.value}",
        output_full=classification.model_dump_json(),
    )


async def run(
    task_text: str,
    context: str = "",
    role_overrides: dict[str, str] | None = None,
    context_hint: str | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
    provider: str = "openrouter",
) -> PipelineResult:
    _current_provider.set(provider)
    classification = await classify(task_text, context_hint=context_hint, role_overrides=role_overrides, provider=_current_provider.get())
    pipeline = classification.recommended_pipeline
    cls_step = _classifier_step(classification)

    logger.info(
        "Orchestrator: classified as %s/%s → pipeline=%s",
        [t.value for t in classification.task_types],
        classification.complexity.value,
        pipeline.value,
    )

    if pipeline == PipelineType.simple:
        messages = [{"role": "user", "content": task_text}]
        if context:
            messages = [
                {"role": "system", "content": f"Context:\n{context}"},
                {"role": "user", "content": task_text},
            ]
        result = await run_simple(messages, role_overrides, classification)

    elif pipeline == PipelineType.analysis:
        result = await run_analysis(context, task_text, role_overrides, classification, goal_id, has_strategy_source)

    elif pipeline == PipelineType.debate:
        result = await run_debate(context, task_text, role_overrides, classification, goal_id, has_strategy_source)

    elif pipeline == PipelineType.code:
        result = await run_code(context, task_text, role_overrides, classification)

    elif pipeline == PipelineType.structured:
        result = await run_structured(context, task_text, role_overrides=role_overrides, classification=classification)

    elif pipeline == PipelineType.tool:
        result = await run_tool(context, task_text, role_overrides, classification)

    else:
        messages = [{"role": "user", "content": task_text}]
        result = await run_simple(messages, role_overrides, classification)

    result.steps.insert(0, cls_step)
    result.total_duration_ms += cls_step.duration_ms
    _save_log(result)
    return result


async def stream_run(
    task_text: str,
    context: str = "",
    role_overrides: dict[str, str] | None = None,
    context_hint: str | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
    provider: str = "openrouter",
) -> AsyncGenerator[dict, None]:
    _current_provider.set(provider)
    classification = await classify(task_text, context_hint=context_hint, role_overrides=role_overrides, provider=_current_provider.get())
    pipeline = classification.recommended_pipeline
    cls_step = _classifier_step(classification)

    logger.info(
        "Orchestrator stream: classified as %s/%s → pipeline=%s",
        [t.value for t in classification.task_types],
        classification.complexity.value,
        pipeline.value,
    )

    yield {"status": "classified", "pipeline_type": pipeline.value, "done": False}

    if pipeline == PipelineType.simple:
        messages = [{"role": "user", "content": task_text}]
        if context:
            messages = [
                {"role": "system", "content": f"Context:\n{context}"},
                {"role": "user", "content": task_text},
            ]
        async for chunk in stream_simple(messages, role_overrides, classification):
            yield chunk

    elif pipeline == PipelineType.analysis:
        async for chunk in stream_analysis(context, task_text, role_overrides, classification, goal_id, has_strategy_source):
            yield chunk

    elif pipeline == PipelineType.debate:
        async for chunk in stream_debate(context, task_text, role_overrides, classification, goal_id, has_strategy_source):
            yield chunk

    elif pipeline == PipelineType.code:
        async for chunk in stream_code(context, task_text, role_overrides, classification):
            yield chunk

    else:
        result = await run(task_text, context, role_overrides, context_hint, goal_id, has_strategy_source, provider=provider)
        pipeline_info = result.to_dict()
        pipeline_info.pop("final_text", None)

        full_text = result.final_text
        yield {"delta": full_text, "done": False}
        yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


def list_pipeline_logs(limit: int = 50) -> list[dict]:
    _ensure(PIPELINE_LOG_DIR)
    logs = []
    for f in sorted(PIPELINE_LOG_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        from ...core.storage import read_json
        data = read_json(f, None)
        if data:
            logs.append(data)
    return logs


def get_pipeline_log(run_id: str) -> dict | None:
    from ...core.storage import read_json
    return read_json(PIPELINE_LOG_DIR / f"{run_id}.json", None)
