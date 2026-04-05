from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.routers import ai_chat
from app.schemas.ai_chat import (
    ChatRequest,
    ThreadMessageAppendRequest,
    ApplyCodeRequest,
    LoopStartRequest,
    LoopConfirmRequest,
)


async def _fake_stream_run(*args, **kwargs):
    yield {
        "event_type": "classifier_decision",
        "pipeline_type": "simple",
        "role": "classifier",
    }
    yield {"delta": "hello ", "done": False}
    yield {
        "done": True,
        "fullText": "hello world",
        "pipeline": {
            "pipeline_type": "simple",
            "total_duration_ms": 42,
            "trace": [{"event_type": "classifier_decision"}],
            "steps": [
                {"role": "classifier", "model_id": "openrouter/classifier:free"},
                {
                    "role": "explainer",
                    "model_id": "openrouter/model:free",
                    "provider": "openrouter",
                },
            ],
        },
    }


class AIChatRouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        ai_chat._LOOP_SESSIONS.clear()
        ai_chat._LOOP_EVENTS.clear()

    async def test_chat_sse_stream_includes_trace_and_final_chunk(self) -> None:
        thread = {
            "thread_id": "thread-1",
            "goal_id": "balanced",
            "provider": "openrouter",
            "model": "openrouter/model:free",
            "context_mode": "auto",
            "messages": [{"role": "user", "content": "previous"}],
        }

        context_bundle = SimpleNamespace(
            snapshot={"strategy_config": {"enabled": True}},
            context_text="Context text",
            context_hint="goal=balanced",
            metadata={"context_run_id": "run-1", "context_mode": "auto"},
        )

        with (
            patch("app.routers.ai_chat.load_thread", return_value=thread),
            patch("app.routers.ai_chat.build_context_bundle", return_value=context_bundle),
            patch("app.routers.ai_chat.stream_run", side_effect=_fake_stream_run),
            patch("app.routers.ai_chat.append_message") as mock_append,
        ):
            response = await ai_chat.chat(
                ChatRequest(
                    thread_id="thread-1",
                    message="hello",
                    provider="openrouter",
                    model="openrouter/model:free",
                    goal_id="balanced",
                )
            )
            raw = []
            async for chunk in response.body_iterator:
                raw.append(chunk.decode() if isinstance(chunk, (bytes, bytearray)) else str(chunk))

        self.assertEqual(response.media_type, "text/event-stream")
        text = "".join(raw)

        events = []
        for block in text.split("\n\n"):
            if not block.startswith("data: "):
                continue
            payload = block[len("data: ") :].strip()
            if payload:
                events.append(json.loads(payload))

        self.assertTrue(any(evt.get("event_type") == "classifier_decision" for evt in events))
        final_evt = next(evt for evt in events if evt.get("done") is True)
        self.assertEqual(final_evt.get("thread_id"), "thread-1")
        self.assertEqual(final_evt.get("conversation_id"), "thread-1")
        self.assertEqual(final_evt.get("fullText"), "hello world")
        self.assertEqual(final_evt.get("pipeline", {}).get("pipeline_type"), "simple")
        self.assertIn("assistant_message_id", final_evt)

        self.assertEqual(mock_append.call_count, 2)
        first_call = mock_append.call_args_list[0]
        second_call = mock_append.call_args_list[1]
        self.assertEqual(first_call.args[0], "thread-1")
        self.assertEqual(first_call.args[1], "user")
        self.assertEqual(second_call.args[0], "thread-1")
        self.assertEqual(second_call.args[1], "assistant")

    async def test_list_threads_returns_summary_shape(self) -> None:
        thread = {
            "thread_id": "thread-2",
            "title": "Test",
            "preview": "hello",
            "created_at": "2026-04-06T00:00:00Z",
            "updated_at": "2026-04-06T00:00:01Z",
            "messages": [{"role": "user", "content": "x"}],
            "provider": "openrouter",
            "model": "openrouter/model:free",
            "goal_id": "balanced",
            "context_run_id": "run-2",
            "context_mode": "auto",
        }
        with patch("app.routers.ai_chat.list_threads", return_value=[thread]):
            data = await ai_chat.list_threads_endpoint()

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0].thread_id, "thread-2")
        self.assertEqual(data[0].conversation_id, "thread-2")
        self.assertEqual(data[0].message_count, 1)

    async def test_get_thread_404_when_missing(self) -> None:
        with (
            patch("app.routers.ai_chat.validate_thread_id", return_value="thread-missing"),
            patch("app.routers.ai_chat.load_thread", return_value=None),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await ai_chat.get_thread("thread-missing")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Thread not found")

    async def test_append_thread_message_endpoint_forwards_payload(self) -> None:
        returned = {"thread_id": "thread-3", "messages": [{"role": "user", "content": "hello"}]}
        with (
            patch("app.routers.ai_chat.validate_thread_id", return_value="thread-3"),
            patch("app.routers.ai_chat.append_message", return_value=returned) as mock_append,
        ):
            result = await ai_chat.append_thread_message(
                "thread-3",
                ThreadMessageAppendRequest(
                    role="user",
                    content="hello",
                    goal_id="balanced",
                    provider="openrouter",
                ),
            )

        self.assertEqual(result["thread_id"], "thread-3")
        mock_append.assert_called_once()
        self.assertEqual(mock_append.call_args.args[0], "thread-3")
        self.assertEqual(mock_append.call_args.args[1], "user")
        self.assertEqual(mock_append.call_args.args[2], "hello")

    async def test_providers_endpoint_combines_openrouter_and_ollama(self) -> None:
        with (
            patch("app.routers.ai_chat.has_api_keys", return_value=True),
            patch(
                "app.routers.ai_chat.or_list_models",
                new=AsyncMock(return_value=[{"id": "openrouter/model:free", "name": "Model"}]),
            ),
            patch("app.routers.ai_chat.is_available", new=AsyncMock(return_value=True)),
            patch("app.routers.ai_chat.oll_list_models", new=AsyncMock(return_value=["llama3:8b"])),
        ):
            body = await ai_chat.get_providers()

        self.assertTrue(body["openrouter"]["available"])
        self.assertEqual(body["openrouter"]["models"][0]["id"], "openrouter/model:free")
        self.assertTrue(body["ollama"]["available"])
        self.assertEqual(body["ollama"]["models"][0]["id"], "ollama/llama3:8b")

    async def test_apply_code_resolves_filename_hint_and_writes(self) -> None:
        final_source = ""
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_dir = Path(tmpdir)
            source_path = strategy_dir / "MultiMa.py"
            source_path.write_text("class MultiMa:\n    pass\n", encoding="utf-8")
            thread = {
                "thread_id": "thread-1",
                "messages": [
                    {
                        "id": "a1",
                        "role": "assistant",
                        "content": "1. Python strategy (MultiMa.py)\n```python\nclass MultiMa:\n    def run(self):\n        return 1\n```",
                    }
                ],
            }
            with (
                patch("app.routers.ai_chat.validate_thread_id", return_value="thread-1"),
                patch("app.routers.ai_chat.load_thread", return_value=thread),
                patch("app.routers.ai_chat.STRATEGIES_DIR", strategy_dir),
            ):
                body = await ai_chat.apply_code(
                    ApplyCodeRequest(
                        thread_id="thread-1",
                        assistant_message_id="a1",
                        code_block_index=0,
                    )
                )
            final_source = source_path.read_text(encoding="utf-8")
        self.assertTrue(body["ok"])
        self.assertEqual(body["strategy"], "MultiMa")
        self.assertIn("diff_summary", body)
        self.assertIn("class MultiMa", final_source)

    async def test_apply_code_uses_fallback_strategy_when_filename_missing(self) -> None:
        final_source = ""
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_dir = Path(tmpdir)
            source_path = strategy_dir / "Fallback.py"
            source_path.write_text("class Fallback:\n    pass\n", encoding="utf-8")
            thread = {
                "thread_id": "thread-1",
                "messages": [
                    {
                        "id": "a2",
                        "role": "assistant",
                        "content": "```python\nclass Fallback:\n    x = 1\n```",
                    }
                ],
            }
            with (
                patch("app.routers.ai_chat.validate_thread_id", return_value="thread-1"),
                patch("app.routers.ai_chat.load_thread", return_value=thread),
                patch("app.routers.ai_chat.STRATEGIES_DIR", strategy_dir),
            ):
                body = await ai_chat.apply_code(
                    ApplyCodeRequest(
                        thread_id="thread-1",
                        assistant_message_id="a2",
                        code_block_index=0,
                        fallback_strategy="Fallback",
                    )
                )
            final_source = source_path.read_text(encoding="utf-8")
        self.assertTrue(body["ok"])
        self.assertEqual(body["strategy"], "Fallback")
        self.assertIn("x = 1", final_source)

    async def test_apply_code_invalid_python_rejected(self) -> None:
        final_source = ""
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_dir = Path(tmpdir)
            source_path = strategy_dir / "Broken.py"
            original = "class Broken:\n    pass\n"
            source_path.write_text(original, encoding="utf-8")
            thread = {
                "thread_id": "thread-1",
                "messages": [
                    {
                        "id": "a3",
                        "role": "assistant",
                        "content": "1. Python strategy (Broken.py)\n```python\nclass Broken(\n    pass\n```",
                    }
                ],
            }
            with (
                patch("app.routers.ai_chat.validate_thread_id", return_value="thread-1"),
                patch("app.routers.ai_chat.load_thread", return_value=thread),
                patch("app.routers.ai_chat.STRATEGIES_DIR", strategy_dir),
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await ai_chat.apply_code(
                        ApplyCodeRequest(
                            thread_id="thread-1",
                            assistant_message_id="a3",
                            code_block_index=0,
                        )
                    )
            final_source = source_path.read_text(encoding="utf-8")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Python syntax error", str(ctx.exception.detail))
        self.assertEqual(final_source, original)

    async def test_apply_code_without_filename_or_fallback_rejected(self) -> None:
        thread = {
            "thread_id": "thread-1",
            "messages": [
                {
                    "id": "a4",
                    "role": "assistant",
                    "content": "```python\nclass AnyName:\n    pass\n```",
                }
            ],
        }
        with (
            patch("app.routers.ai_chat.validate_thread_id", return_value="thread-1"),
            patch("app.routers.ai_chat.load_thread", return_value=thread),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await ai_chat.apply_code(
                    ApplyCodeRequest(
                        thread_id="thread-1",
                        assistant_message_id="a4",
                        code_block_index=0,
                    )
                )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Could not resolve strategy target", str(ctx.exception.detail))

    async def test_loop_start_creates_session_and_report_path(self) -> None:
        class _FakeThread:
            def __init__(self, target=None, args=None, daemon=None):
                self.target = target
                self.args = args or ()
                self.daemon = daemon

            def start(self):
                return None

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)
            with (
                patch("app.routers.ai_chat.validate_thread_id", return_value="thread-loop"),
                patch("app.routers.ai_chat.AI_LOOP_REPORTS_DIR", reports_dir),
                patch("app.routers.ai_chat.threading.Thread", _FakeThread),
            ):
                body = await ai_chat.loop_start(
                    LoopStartRequest(
                        thread_id="thread-loop",
                        assistant_message_id="assistant-1",
                        code_block_index=0,
                        context_run_id="run-ctx",
                        provider="openrouter",
                    )
                )
        self.assertEqual(body["status"], "running")
        self.assertIn("loop_id", body)
        loop_id = body["loop_id"]
        self.assertIn(loop_id, ai_chat._LOOP_SESSIONS)
        self.assertTrue(str(body["md_report_path"]).endswith(f"{loop_id}.md"))

    async def test_loop_start_idempotency_returns_same_payload(self) -> None:
        class _FakeThread:
            def __init__(self, target=None, args=None, daemon=None):
                self.target = target
                self.args = args or ()
                self.daemon = daemon

            def start(self):
                return None

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)
            state_dir = reports_dir / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            state_file = state_dir / "sessions.json"
            with (
                patch("app.routers.ai_chat.validate_thread_id", return_value="thread-loop"),
                patch("app.routers.ai_chat.AI_LOOP_REPORTS_DIR", reports_dir),
                patch("app.routers.ai_chat._LOOP_STATE_DIR", state_dir),
                patch("app.routers.ai_chat._LOOP_STATE_FILE", state_file),
                patch("app.routers.ai_chat.threading.Thread", _FakeThread),
            ):
                req = LoopStartRequest(
                    thread_id="thread-loop",
                    assistant_message_id="assistant-1",
                    code_block_index=0,
                    context_run_id="run-ctx",
                    provider="openrouter",
                    idempotency_key="same-key",
                )
                first = await ai_chat.loop_start(req)
                second = await ai_chat.loop_start(req)

        self.assertEqual(first["loop_id"], second["loop_id"])
        self.assertEqual(first["status"], second["status"])

    async def test_loop_confirm_and_report_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)
            loop_id = "loop-test-1"
            report_path = reports_dir / f"{loop_id}.md"
            report_path.write_text("# Report\n\nok", encoding="utf-8")
            ai_chat._LOOP_SESSIONS[loop_id] = {
                "loop_id": loop_id,
                "thread_id": "thread-1",
                "status": "running",
                "started_at": "2026-04-06T00:00:00Z",
                "updated_at": "2026-04-06T00:00:00Z",
                "steps": [],
                "table_rows": [],
                "test_results": [],
                "file_changes": {},
                "validation_text": "",
                "strategy": "MultiMa",
                "baseline_run_id": "base-run",
                "new_run_id": None,
                "request": {},
                "rerun_confirmed": None,
                "stop_requested": False,
                "md_report_path": str(report_path),
            }
            with patch("app.routers.ai_chat.AI_LOOP_REPORTS_DIR", reports_dir):
                confirmed = await ai_chat.loop_confirm_rerun(loop_id, LoopConfirmRequest(confirm=True))
                report = await ai_chat.loop_report(loop_id)

        self.assertEqual(confirmed["loop_id"], loop_id)
        self.assertTrue(confirmed["confirm"])
        self.assertTrue(ai_chat._LOOP_SESSIONS[loop_id]["rerun_confirmed"])
        self.assertTrue(report["exists"])
        self.assertEqual(report["loop_id"], loop_id)
        self.assertIn("# AI Loop Report", report["preview"])
        self.assertIn("download_url", report)

    async def test_loop_metrics_endpoint_returns_step_summary(self) -> None:
        loop_id = "loop-metrics-1"
        ai_chat._LOOP_SESSIONS[loop_id] = {
            "loop_id": loop_id,
            "thread_id": "thread-1",
            "status": "running",
            "new_run_id": "run-xyz",
            "step_metrics": [
                {"ts": "x", "step": "apply_done", "duration_ms": 100},
                {"ts": "x", "step": "apply_done", "duration_ms": 200},
                {"ts": "x", "step": "tests_done", "duration_ms": 300},
            ],
        }
        body = await ai_chat.loop_metrics(loop_id)
        self.assertEqual(body["loop_id"], loop_id)
        self.assertEqual(body["run_id"], "run-xyz")
        self.assertIn("apply_done", body["metrics"]["summary"])


if __name__ == "__main__":
    unittest.main()
