from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.routers import ai_chat
from app.schemas.ai_chat import ChatRequest, ThreadMessageAppendRequest


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


if __name__ == "__main__":
    unittest.main()
