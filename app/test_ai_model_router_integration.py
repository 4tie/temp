from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.ai.pipelines.classifier import (
    Classification,
    ComplexityLevel,
    PipelineType,
    TaskType,
)
from app.ai.pipelines import orchestrator


def _mk_classification(pipeline: PipelineType) -> Classification:
    return Classification(
        task_types=[TaskType.explanation],
        complexity=ComplexityLevel.medium,
        requires_code=(pipeline == PipelineType.code),
        requires_structured_out=False,
        confidence=0.9,
        recommended_pipeline=pipeline,
        classifier_model_id="openrouter/classifier:free",
        classifier_selection_reason="test",
        classifier_duration_ms=2,
        classifier_fallback_used=False,
        classifier_fallback_reason=None,
    )


async def _stream_ok(*args, **kwargs):
    yield {"delta": "ok", "done": False}
    yield {"done": True}


class ModelRouterIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_simple_pipeline_uses_explainer_role(self) -> None:
        calls: list[str] = []

        def _fake_get(role, models, overrides=None):
            calls.append(role)
            return "openrouter/model:free", f"role={role}"

        with (
            patch.object(orchestrator, "classify", new=AsyncMock(return_value=_mk_classification(PipelineType.simple))),
            patch.object(orchestrator, "fetch_free_models", new=AsyncMock(return_value=[{"id": "openrouter/model:free"}])),
            patch.object(orchestrator, "get_model_for_role", side_effect=_fake_get),
            patch.object(orchestrator, "stream_chat", side_effect=_stream_ok),
        ):
            _ = [e async for e in orchestrator.stream_run(task_text="hello", context="", provider="openrouter")]

        self.assertEqual(calls, ["explainer"])

    async def test_analysis_pipeline_uses_reasoner_and_composer_roles(self) -> None:
        calls: list[str] = []

        def _fake_get(role, models, overrides=None):
            calls.append(role)
            return "openrouter/model:free", f"role={role}"

        async def _fake_call_model(role, messages, models, role_overrides=None):
            return orchestrator.PipelineStep(
                role=role,
                model_id="openrouter/model:free",
                provider="openrouter",
                requested_provider="openrouter",
                requested_model_id="openrouter/model:free",
                duration_ms=1,
                selection_reason=f"role={role}",
                output_preview="ok",
                output_full="ok",
            )

        with (
            patch.object(orchestrator, "classify", new=AsyncMock(return_value=_mk_classification(PipelineType.analysis))),
            patch.object(orchestrator, "fetch_free_models", new=AsyncMock(return_value=[{"id": "openrouter/model:free"}])),
            patch.object(orchestrator, "get_model_for_role", side_effect=_fake_get),
            patch.object(orchestrator, "_call_model", side_effect=_fake_call_model),
            patch.object(orchestrator, "stream_chat", side_effect=_stream_ok),
        ):
            _ = [e async for e in orchestrator.stream_run(task_text="hello", context="", provider="openrouter")]

        self.assertEqual(calls, ["reasoner", "composer"])

    async def test_debate_pipeline_uses_analyst_and_judge_roles(self) -> None:
        calls: list[str] = []

        def _fake_get(role, models, overrides=None):
            calls.append(role)
            return "openrouter/model:free", f"role={role}"

        async def _fake_call_model(role, messages, models, role_overrides=None):
            return orchestrator.PipelineStep(
                role=role,
                model_id="openrouter/model:free",
                provider="openrouter",
                requested_provider="openrouter",
                requested_model_id="openrouter/model:free",
                duration_ms=1,
                selection_reason=f"role={role}",
                output_preview="ok",
                output_full="ok",
            )

        with (
            patch.object(orchestrator, "classify", new=AsyncMock(return_value=_mk_classification(PipelineType.debate))),
            patch.object(orchestrator, "fetch_free_models", new=AsyncMock(return_value=[{"id": "openrouter/model:free"}])),
            patch.object(orchestrator, "get_model_for_role", side_effect=_fake_get),
            patch.object(orchestrator, "_call_model", side_effect=_fake_call_model),
            patch.object(orchestrator, "stream_chat", side_effect=_stream_ok),
        ):
            _ = [e async for e in orchestrator.stream_run(task_text="hello", context="", provider="openrouter")]

        self.assertEqual(calls, ["analyst_a", "analyst_b", "judge"])

    async def test_code_pipeline_uses_code_and_explainer_roles(self) -> None:
        calls: list[str] = []

        def _fake_get(role, models, overrides=None):
            calls.append(role)
            return "openrouter/model:free", f"role={role}"

        async def _fake_call_model(role, messages, models, role_overrides=None):
            return orchestrator.PipelineStep(
                role=role,
                model_id="openrouter/model:free",
                provider="openrouter",
                requested_provider="openrouter",
                requested_model_id="openrouter/model:free",
                duration_ms=1,
                selection_reason=f"role={role}",
                output_preview="ok",
                output_full="print('ok')",
            )

        with (
            patch.object(orchestrator, "classify", new=AsyncMock(return_value=_mk_classification(PipelineType.code))),
            patch.object(orchestrator, "fetch_free_models", new=AsyncMock(return_value=[{"id": "openrouter/model:free"}])),
            patch.object(orchestrator, "get_model_for_role", side_effect=_fake_get),
            patch.object(orchestrator, "_call_model", side_effect=_fake_call_model),
            patch.object(orchestrator, "stream_chat", side_effect=_stream_ok),
            patch.object(orchestrator, "_validate_python_code", return_value=orchestrator.CodeValidation(valid=True, errors=[], method="test")),
        ):
            _ = [e async for e in orchestrator.stream_run(task_text="hello", context="", provider="openrouter")]

        self.assertEqual(calls, ["code_gen", "explainer"])


if __name__ == "__main__":
    unittest.main()
