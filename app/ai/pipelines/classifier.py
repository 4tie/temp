"""
Task Classifier — classifies every request into task type, complexity, and pipeline.
Uses a fast model (classifier role) with structured JSON output.
Falls back to 'simple' pipeline on any failure.
"""
from __future__ import annotations

import json
import logging
from enum import Enum

from pydantic import BaseModel

from ..models.provider_dispatch import chat_complete
from ..models.registry import fetch_free_models, get_model_for_role

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    casual_chat = "casual_chat"
    explanation = "explanation"
    deep_reasoning = "deep_reasoning"
    code_generation = "code_generation"
    structured_output = "structured_output"
    tool_calling = "tool_calling"
    comparison = "comparison"


class ComplexityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class PipelineType(str, Enum):
    simple = "simple"
    analysis = "analysis"
    debate = "debate"
    code = "code"
    structured = "structured"
    tool = "tool"


class Classification(BaseModel):
    task_types: list[TaskType]
    complexity: ComplexityLevel
    requires_code: bool
    requires_structured_out: bool
    confidence: float
    recommended_pipeline: PipelineType
    classifier_model_id: str = ""
    classifier_selection_reason: str = ""
    classifier_duration_ms: int = 0
    classifier_fallback_used: bool = False
    classifier_fallback_reason: str | None = None


CLASSIFIER_SYSTEM_PROMPT = """You are a task classifier for a trading strategy analysis system.
Analyze the user request and return ONLY a JSON object (no markdown, no explanation).

Task types (pick 1-3 that apply):
- casual_chat: greetings, small talk, simple questions
- explanation: asking for explanations, definitions, summaries
- deep_reasoning: strategy analysis, optimization logic, metric interpretation, trade analysis
- code_generation: writing/modifying code, parameters, config
- structured_output: needs strict JSON, tables, schemas
- tool_calling: executing tools, running backtests, calling APIs
- comparison: comparing strategies, models, approaches, pairs

Complexity levels:
- low: simple conversational response, single model sufficient
- medium: needs analysis + clean presentation (2-step)
- high: complex analysis that benefits from multiple perspectives (debate mode)

Pipeline types:
- simple: quick conversational response
- analysis: deep reasoning then composed output
- debate: two parallel analyses then judge then compose (for high-stakes decisions)
- code: code generation then explanation
- structured: strict JSON output
- tool: tool execution then analysis

Return exactly:
{"task_types":["..."],"complexity":"low|medium|high","requires_code":false,"requires_structured_out":false,"confidence":0.9,"recommended_pipeline":"simple|analysis|debate|code|structured|tool"}"""


DEFAULT_CLASSIFICATION = Classification(
    task_types=[TaskType.casual_chat],
    complexity=ComplexityLevel.low,
    requires_code=False,
    requires_structured_out=False,
    confidence=0.5,
    recommended_pipeline=PipelineType.simple,
)


async def classify(
    text: str,
    context_hint: str | None = None,
    role_overrides: dict[str, str] | None = None,
    provider: str = "openrouter",
) -> Classification:
    import time as _time

    models = await fetch_free_models(provider)
    model_id, selection_reason = get_model_for_role("classifier", models, role_overrides)

    user_content = text
    if context_hint:
        user_content = f"{text}\n\n[Context: {context_hint}]"

    messages = [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    t0 = _time.monotonic()
    fallback_used = False
    fallback_reason: str | None = None
    used_model = model_id

    try:
        raw = await chat_complete(messages, model=model_id)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        json_start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if json_start >= 0 and end > json_start:
            cleaned = cleaned[json_start:end]

        parsed = json.loads(cleaned)

        task_types = []
        for tt in parsed.get("task_types", ["casual_chat"]):
            try:
                task_types.append(TaskType(tt))
            except ValueError:
                continue
        if not task_types:
            task_types = [TaskType.casual_chat]

        try:
            complexity = ComplexityLevel(parsed.get("complexity", "low"))
        except ValueError:
            complexity = ComplexityLevel.low

        try:
            pipeline = PipelineType(parsed.get("recommended_pipeline", "simple"))
        except ValueError:
            pipeline = PipelineType.simple

        duration_ms = int((_time.monotonic() - t0) * 1000)
        return Classification(
            task_types=task_types,
            complexity=complexity,
            requires_code=bool(parsed.get("requires_code", False)),
            requires_structured_out=bool(parsed.get("requires_structured_out", False)),
            confidence=min(1.0, max(0.0, float(parsed.get("confidence", 0.8)))),
            recommended_pipeline=pipeline,
            classifier_model_id=used_model,
            classifier_selection_reason=selection_reason,
            classifier_duration_ms=duration_ms,
            classifier_fallback_used=fallback_used,
            classifier_fallback_reason=fallback_reason,
        )

    except Exception as e:
        duration_ms = int((_time.monotonic() - t0) * 1000)
        logger.warning("Classification failed: %s — defaulting to simple pipeline", e)
        fallback = DEFAULT_CLASSIFICATION.model_copy()
        fallback.classifier_model_id = used_model
        fallback.classifier_selection_reason = selection_reason
        fallback.classifier_duration_ms = duration_ms
        fallback.classifier_fallback_used = True
        fallback.classifier_fallback_reason = str(e)
        return fallback
