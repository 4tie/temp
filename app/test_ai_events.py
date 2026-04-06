from __future__ import annotations

import unittest

from app.ai.events import (
    LoopEventStatus,
    LoopEventType,
    LoopStream,
    coerce_loop_event_type,
    serialize_ai_loop_event,
    serialize_evolution_event,
    sse_event_line,
)


class AiEventsTests(unittest.TestCase):
    def test_serialize_ai_loop_event_builds_canonical_envelope(self) -> None:
        event = serialize_ai_loop_event(
            "loop-1",
            LoopEventType.APPLY_DONE,
            status=LoopEventStatus.OK,
            message="Applied code",
            payload={"strategy": "MultiMa", "duration_ms": 42},
        )

        self.assertEqual(event["event_type"], "apply_done")
        self.assertEqual(event["step"], "apply_done")
        self.assertEqual(event["stream"], LoopStream.AI_LOOP.value)
        self.assertEqual(event["status"], "ok")
        self.assertEqual(event["strategy"], "MultiMa")
        self.assertEqual(event["payload"]["duration_ms"], 42)
        self.assertFalse(event["done"])

    def test_evolution_event_normalizes_legacy_step_alias(self) -> None:
        self.assertEqual(coerce_loop_event_type("analyzing"), LoopEventType.ANALYSIS_STARTED)

        event = serialize_evolution_event(
            "loop-2",
            "analyzing",
            generation=3,
            message="Running analysis",
        )

        self.assertEqual(event["event_type"], "analysis_started")
        self.assertEqual(event["step"], "analysis_started")
        self.assertEqual(event["cycle_index"], 3)
        self.assertEqual(event["generation"], 3)
        self.assertEqual(event["stream"], LoopStream.EVOLUTION.value)

    def test_sse_event_line_wraps_json_payload(self) -> None:
        line = sse_event_line({"event_type": "loop_started", "loop_id": "loop-3"})
        self.assertTrue(line.startswith("data: "))
        self.assertTrue(line.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
