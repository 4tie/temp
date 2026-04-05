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

from ..models.provider_dispatch import chat_complete, get_last_dispatch_meta
from ..models.registry import fetch_free_models, get_model_for_role
from ..prompts.trading import CLASSIFIER_SYSTEM_PROMPT

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
        raw = await chat_complete(messages, model=model_id, provider=provider)
        dispatch_meta = get_last_dispatch_meta()
        if dispatch_meta:
            used_model = dispatch_meta.get("model") or used_model
            actual_provider = dispatch_meta.get("provider")
            key_slot = dispatch_meta.get("key_slot")
            attempt_count = dispatch_meta.get("attempt_count")
            fallback_chain = dispatch_meta.get("fallback_chain") or []
            meta_bits = [selection_reason]
            if actual_provider:
                meta_bits.append(f"actual_provider={actual_provider}")
            if key_slot:
                meta_bits.append(f"key_slot={key_slot}")
            if attempt_count:
                meta_bits.append(f"attempts={attempt_count}")
            if fallback_chain:
                meta_bits.append(f"chain={' -> '.join(fallback_chain)}")
            selection_reason = " | ".join(meta_bits)
            fallback_used = bool(dispatch_meta.get("fallback_used"))
            if fallback_used and not fallback_reason:
                provider_attempts = dispatch_meta.get("provider_attempts") or []
                if provider_attempts:
                    fallback_reason = provider_attempts[-1].get("error")
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
