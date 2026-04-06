from __future__ import annotations

import subprocess
import unittest
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

try:
    from app.ai.models import provider_dispatch
    from app.ai.evolution import strategy_editor
    from app.ai.pipelines.orchestrator import _call_model, _validate_python_code
    from app.ai.tools import deep_analysis
    _IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - environment guard for missing deps
    provider_dispatch = None
    strategy_editor = None
    _validate_python_code = None
    deep_analysis = None
    _IMPORT_ERROR = exc


@unittest.skipIf(_IMPORT_ERROR is not None, f"App AI dependencies unavailable: {_IMPORT_ERROR}")
class DeepAnalysisReliabilityTest(unittest.TestCase):
    def test_narrative_fallback_does_not_reference_undefined_health_variable(self) -> None:
        narrative = deep_analysis._compute_narrative_fallback(
            n=12,
            total=47,
            comps={
                "profitability": 10,
                "risk_control": 7,
                "consistency": 8,
                "trade_quality": 9,
                "stability": 7,
                "edge_quality": 6,
            },
            win_rate=41.7,
            total_profit_pct=-3.2,
            profit_factor=0.94,
            max_drawdown=22.5,
            total_profit=-32.0,
            avg_profit=-2.7,
            strengths=[],
            weaknesses=[],
            analysis={},
            strategy_name="TestStrategy",
            low_data=True,
            am={},
            max_total=120,
        )

        self.assertIn("overall health score is 47/120", narrative["summary"])
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


@unittest.skipIf(_IMPORT_ERROR is not None, f"App AI dependencies unavailable: {_IMPORT_ERROR}")
class OrchestratorModelFallbackReliabilityTest(unittest.IsolatedAsyncioTestCase):
    async def test_code_gen_model_outage_returns_fenced_source_fallback(self) -> None:
        messages = [
            {
                "role": "user",
                "content": "STRATEGY SOURCE:\n```python\nclass DemoStrategy:\n    pass\n```",
            }
        ]

        with patch("app.ai.pipelines.orchestrator.chat_complete", new=AsyncMock(side_effect=RuntimeError("provider outage"))):
            step = await _call_model(
                "code_gen",
                messages,
                models=[],
                role_overrides={"code_gen": "meta-llama/llama-3.2-1b-instruct:free"},
            )

        self.assertIn("[Error: model unavailable for code_gen]", step.output_full)
        self.assertIn("```python", step.output_full)
        self.assertIn("class DemoStrategy", step.output_full)
        self.assertIn("# CHANGES:", step.output_full)


@unittest.skipIf(_IMPORT_ERROR is not None, f"App AI dependencies unavailable: {_IMPORT_ERROR}")
class EvolutionMutationReliabilityTest(unittest.IsolatedAsyncioTestCase):
    async def test_mutate_strategy_recovers_from_model_outage_with_source_fallback(self) -> None:
        source_code = (
            "class DemoStrategy(object):\n"
            "    timeframe = '5m'\n"
            "    startup_candle_count = 1\n"
        )

        fitness = type("Fitness", (), {"value": 42.0, "breakdown": {"profitability": 7}})()

        with patch(
            "app.ai.evolution.strategy_editor.fetch_free_models",
            new=AsyncMock(return_value=[]),
        ), patch(
            "app.ai.pipelines.orchestrator.chat_complete",
            new=AsyncMock(side_effect=RuntimeError("provider outage")),
        ), patch(
            "app.ai.evolution.strategy_editor.create_version",
            return_value="DemoStrategy_evo_g1",
        ):
            result = await strategy_editor.mutate_strategy(
                strategy_name="DemoStrategy",
                source_code=source_code,
                analysis={},
                fitness=fitness,
                goal_id=None,
                provider="openrouter",
                model=None,
                generation=1,
                feedback_history=[],
                regime_context=None,
            )

        self.assertTrue(result.success)
        self.assertEqual(result.version_name, "DemoStrategy_evo_g1")
        self.assertIn("class DemoStrategy", result.new_code)
        self.assertFalse(result.validation_errors)


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


@unittest.skipIf(_IMPORT_ERROR is not None, f"App AI dependencies unavailable: {_IMPORT_ERROR}")
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


