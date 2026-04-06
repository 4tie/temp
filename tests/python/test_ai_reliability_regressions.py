from __future__ import annotations

import subprocess
import sys
import types
import unittest
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")

    class _HTTPStatusError(Exception):
        def __init__(self, *args, response=None, **kwargs):
            super().__init__(*args)
            self.response = response

    class _AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

    class _Timeout:
        def __init__(self, *args, **kwargs):
            pass

    httpx_stub.HTTPStatusError = _HTTPStatusError
    httpx_stub.AsyncClient = _AsyncClient
    httpx_stub.Timeout = _Timeout
    httpx_stub.Response = object
    sys.modules["httpx"] = httpx_stub

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class _BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_copy(self):
            return self.__class__(**self.__dict__)

        def model_dump_json(self):
            import json

            return json.dumps(self.__dict__)

    pydantic_stub.BaseModel = _BaseModel
    sys.modules["pydantic"] = pydantic_stub

from app.ai.models import provider_dispatch
from app.ai.pipelines.orchestrator import _validate_python_code
from app.ai.tools import deep_analysis


class DeepAnalysisReliabilityTest(unittest.TestCase):
    def test_ai_narrative_fallback_emits_no_unawaited_coroutine_warning(self) -> None:
        async def _fail(messages: list[dict]) -> str:
            raise RuntimeError("provider unavailable")

        with patch("app.ai.tools.deep_analysis._chat_complete_with_timeout", new=_fail):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                narrative = deep_analysis._try_ai_narrative(
                    run_id="",
                    run={},
                    summary={},
                    strategy_name="TestStrategy",
                    trades=[],
                    advanced_metrics=None,
                    root_cause_diagnosis={},
                    loss_patterns={},
                    signal_frequency={},
                    exit_quality={},
                    overfitting={},
                    strengths=[],
                    weaknesses=[],
                    deterministic_narrative={"summary": "fallback"},
                )

        self.assertEqual(narrative["summary"], "fallback")
        self.assertFalse(any("was never awaited" in str(item.message) for item in caught))

    def test_openrouter_narrative_failure_emits_no_unawaited_coroutine_warning(self) -> None:
        mocked_chat = AsyncMock(side_effect=RuntimeError("provider unavailable"))

        with patch("app.ai.models.openrouter_client.has_api_keys", return_value=True), patch(
            "app.ai.models.openrouter_client.chat_complete",
            new=mocked_chat,
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                narrative = deep_analysis._call_openrouter_narrative(
                    strategy_name="TestStrategy",
                    summary={},
                    health={"components": {}},
                    strengths=[],
                    weaknesses=[],
                    analysis={},
                    advanced_metrics={},
                    root_cause_diagnosis={},
                    loss_patterns={},
                    signal_frequency={},
                    exit_quality={},
                    overfitting={},
                    n_trades=0,
                )

        self.assertIsNone(narrative)
        self.assertEqual(mocked_chat.await_count, 1)
        self.assertFalse(any("was never awaited" in str(item.message) for item in caught))


class OrchestratorValidationReliabilityTest(unittest.TestCase):
    def test_windows_temp_path_is_passed_as_subprocess_argument(self) -> None:
        fake_tmp = MagicMock()
        fake_tmp.name = r"C:\Users\M4tie\AppData\Local\Temp\ft_code_123.py"
        fake_tmp.write = MagicMock()
        fake_context = MagicMock()
        fake_context.__enter__.return_value = fake_tmp
        fake_context.__exit__.return_value = False

        def _fake_run(cmd: list[str], **kwargs):
            self.assertEqual(cmd[0:2], ["python", "-c"])
            self.assertEqual(cmd[3], fake_tmp.name)
            self.assertNotIn(fake_tmp.name, cmd[2])
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("tempfile.NamedTemporaryFile", return_value=fake_context), patch(
            "subprocess.run",
            side_effect=_fake_run,
        ), patch("os.unlink"):
            validation = _validate_python_code("```python\nprint('ok')\n```")

        self.assertTrue(validation.valid)
        self.assertEqual(validation.method, "subprocess_ast")

    def test_invalid_python_reports_subprocess_syntax_error(self) -> None:
        fake_tmp = MagicMock()
        fake_tmp.name = r"C:\Users\M4tie\AppData\Local\Temp\ft_code_bad.py"
        fake_tmp.write = MagicMock()
        fake_context = MagicMock()
        fake_context.__enter__.return_value = fake_tmp
        fake_context.__exit__.return_value = False

        stderr = "SyntaxError: invalid syntax\n"
        with patch("tempfile.NamedTemporaryFile", return_value=fake_context), patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(["python"], 1, stdout="", stderr=stderr),
        ), patch("os.unlink"):
            validation = _validate_python_code("```python\nif True print('bad')\n```")

        self.assertFalse(validation.valid)
        self.assertIn("SyntaxError: invalid syntax", validation.errors[0])


class ProviderDispatchReliabilityTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        provider_dispatch._last_dispatch_meta.set(None)

    async def test_openrouter_auth_failure_does_not_retry_and_attempts_single_fallback(self) -> None:
        mocked_or = AsyncMock(side_effect=RuntimeError("OpenRouter chat_complete failed (status=401): User not found."))
        mocked_fallback_model = AsyncMock(side_effect=RuntimeError("No Ollama models available for fallback"))

        with patch("app.ai.models.provider_dispatch._get_openrouter_api_keys", return_value=["key-1"]), patch(
            "app.ai.models.openrouter_client.chat_complete",
            new=mocked_or,
        ), patch(
            "app.ai.models.provider_dispatch._dispatch_ollama_model_v2",
            new=mocked_fallback_model,
        ):
            with self.assertRaisesRegex(RuntimeError, "Ollama fallback unavailable"):
                await provider_dispatch.chat_complete(
                    [{"role": "user", "content": "hi"}],
                    model="qwen/qwen3.6-plus:free",
                    provider="openrouter",
                )

        self.assertEqual(mocked_or.await_count, 1)
        self.assertEqual(mocked_fallback_model.await_count, 1)

    async def test_openrouter_malformed_payload_is_non_retryable(self) -> None:
        mocked_or = AsyncMock(side_effect=RuntimeError("OpenRouter chat_complete returned malformed payload: missing choices"))
        mocked_fallback_model = AsyncMock(side_effect=RuntimeError("No Ollama models available for fallback"))

        with patch("app.ai.models.provider_dispatch._get_openrouter_api_keys", return_value=["key-1"]), patch(
            "app.ai.models.openrouter_client.chat_complete",
            new=mocked_or,
        ), patch(
            "app.ai.models.provider_dispatch._dispatch_ollama_model_v2",
            new=mocked_fallback_model,
        ):
            with self.assertRaisesRegex(RuntimeError, "missing choices"):
                await provider_dispatch.chat_complete(
                    [{"role": "user", "content": "hi"}],
                    model="qwen/qwen3.6-plus:free",
                    provider="openrouter",
                )

        self.assertEqual(mocked_or.await_count, 1)
        self.assertEqual(mocked_fallback_model.await_count, 1)

    async def test_openrouter_rate_limit_retries_are_bounded(self) -> None:
        mocked_or = AsyncMock(side_effect=RuntimeError("OpenRouter chat_complete failed (status=429): Provider returned error"))
        mocked_fallback_model = AsyncMock(side_effect=RuntimeError("No Ollama models available for fallback"))

        with patch("app.ai.models.provider_dispatch._get_openrouter_api_keys", return_value=["key-1"]), patch(
            "app.ai.models.openrouter_client.chat_complete",
            new=mocked_or,
        ), patch(
            "app.ai.models.provider_dispatch._dispatch_ollama_model_v2",
            new=mocked_fallback_model,
        ), patch("app.ai.models.provider_dispatch._asyncio.sleep", new=AsyncMock()):
            with self.assertRaisesRegex(RuntimeError, "Ollama fallback unavailable"):
                await provider_dispatch.chat_complete(
                    [{"role": "user", "content": "hi"}],
                    model="qwen/qwen3.6-plus:free",
                    provider="openrouter",
                )

        self.assertEqual(mocked_or.await_count, 3)
        self.assertEqual(mocked_fallback_model.await_count, 1)

    async def test_successful_ollama_fallback_records_metadata(self) -> None:
        mocked_or = AsyncMock(side_effect=RuntimeError("OpenRouter chat_complete failed (status=401): User not found."))
        mocked_fallback_model = AsyncMock(return_value="llama3")
        mocked_ollama = AsyncMock(return_value="fallback ok")

        with patch("app.ai.models.provider_dispatch._get_openrouter_api_keys", return_value=["key-1"]), patch(
            "app.ai.models.openrouter_client.chat_complete",
            new=mocked_or,
        ), patch(
            "app.ai.models.provider_dispatch._dispatch_ollama_model_v2",
            new=mocked_fallback_model,
        ), patch("app.ai.models.ollama_client.chat_complete", new=mocked_ollama):
            text = await provider_dispatch.chat_complete(
                [{"role": "user", "content": "hi"}],
                model="qwen/qwen3.6-plus:free",
                provider="openrouter",
            )

        meta = provider_dispatch.get_last_dispatch_meta()
        self.assertEqual(text, "fallback ok")
        self.assertTrue(meta.get("fallback_used"))
        self.assertEqual(meta.get("provider"), "ollama")
        self.assertEqual(meta.get("model"), "llama3")
        self.assertIn("openrouter:qwen/qwen3.6-plus:free", meta.get("fallback_chain", []))
