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


async def _simple_stream(*args, **kwargs):
    yield {"delta": "ok", "done": False}
    yield {"done": True}


class OrchestratorTraceTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_run_emits_required_trace_events(self) -> None:
        classification = Classification(
            task_types=[TaskType.explanation],
            complexity=ComplexityLevel.low,
            requires_code=False,
            requires_structured_out=False,
            confidence=0.9,
            recommended_pipeline=PipelineType.simple,
            classifier_model_id="openrouter/classifier:free",
            classifier_selection_reason="test",
            classifier_duration_ms=3,
            classifier_fallback_used=False,
            classifier_fallback_reason=None,
        )

        with (
            patch.object(orchestrator, "classify", new=AsyncMock(return_value=classification)),
            patch.object(orchestrator, "fetch_free_models", new=AsyncMock(return_value=[])),
            patch.object(orchestrator, "get_model_for_role", return_value=("openrouter/model:free", "test")),
            patch.object(orchestrator, "stream_chat", side_effect=_simple_stream),
        ):
            events = [
                event
                async for event in orchestrator.stream_run(
                    task_text="hello",
                    context="",
                    provider="openrouter",
                )
            ]

        event_types = [event.get("event_type") for event in events if event.get("event_type")]
        self.assertIn("classifier_decision", event_types)
        self.assertIn("pipeline_selected", event_types)
        self.assertIn("step_start", event_types)
        self.assertIn("step_complete", event_types)
        self.assertIn("final", event_types)

        final = events[-1]
        self.assertTrue(final.get("done"))
        self.assertEqual(final.get("event_type"), "final")
        self.assertEqual(final.get("pipeline", {}).get("pipeline_type"), "simple")

    def test_judge_prompt_has_required_sections(self) -> None:
        prompt = orchestrator._judge_system_prompt("balanced")
        self.assertIn("## Agreement Points", prompt)
        self.assertIn("## Disagreement Points", prompt)
        self.assertIn("## Final Recommendation", prompt)
        self.assertIn("Analyst A", prompt)
        self.assertIn("Analyst B", prompt)


if __name__ == "__main__":
    unittest.main()
