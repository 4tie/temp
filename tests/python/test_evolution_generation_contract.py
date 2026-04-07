from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from types import ModuleType, SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

try:
    import fastapi as _fastapi  # type: ignore
    _FASTAPI_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - environment guard
    _fastapi = None
    _FASTAPI_IMPORT_ERROR = exc


class _Fitness:
    def __init__(self, value: float, breakdown: dict | None = None) -> None:
        self.value = value
        self.breakdown = breakdown or {}


class EvolutionGenerationContractTest(unittest.TestCase):
    @staticmethod
    def _strategy_editor_stub(*, mutate_result: object | None = None) -> ModuleType:
        stub = ModuleType("app.ai.evolution.strategy_editor")

        async def _mutate_strategy(**_kwargs):
            if mutate_result is not None:
                return mutate_result
            return SimpleNamespace(
                success=False,
                new_code="",
                version_id="",
                version_name="",
                candidate_vector={},
                candidate_fingerprint="",
                changes_summary="",
                validation_errors=["stub"],
            )

        stub.mutate_strategy = _mutate_strategy  # type: ignore[attr-defined]
        return stub

    @staticmethod
    def _strategy_editor_stub_sequence(results: list[object]) -> ModuleType:
        stub = ModuleType("app.ai.evolution.strategy_editor")
        queue = list(results)

        async def _mutate_strategy(**_kwargs):
            if queue:
                return queue.pop(0)
            return SimpleNamespace(
                success=False,
                new_code="",
                version_id="",
                version_name="",
                candidate_vector={},
                candidate_fingerprint="",
                changes_summary="",
                validation_errors=["depleted"],
            )

        stub.mutate_strategy = _mutate_strategy  # type: ignore[attr-defined]
        return stub

    def test_missing_base_results_creates_placeholder_artifact_and_record(self) -> None:
        from app.ai.evolution import evolver

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategies = root / "strategies"
            evo_dir = root / "ai_evolution"
            strategies.mkdir(parents=True, exist_ok=True)
            evo_dir.mkdir(parents=True, exist_ok=True)

            (strategies / "DemoStrategy.py").write_text(
                "class DemoStrategy(object):\n    pass\n",
                encoding="utf-8",
            )

            initial_meta = {
                "base_strategy": "DemoStrategy",
                "strategy_source_name": "DemoStrategy",
                "pairs": ["BTC/USDT"],
                "timeframe": "5m",
                "exchange": "binance",
                "timerange": "20240101-20240201",
            }
            loop_id = "loopbase1x"
            expected_version_id = "DemoStrategy_evo_g1_loopbase"

            with patch.dict(
                "sys.modules",
                {"app.ai.evolution.strategy_editor": self._strategy_editor_stub()},
            ), patch("app.ai.evolution.evolver.STRATEGIES_DIR", strategies), patch(
                "app.ai.evolution.evolver.AI_EVOLUTION_DIR", evo_dir
            ), patch("app.ai.evolution.version_manager.STRATEGIES_DIR", strategies), patch(
                "app.ai.evolution.version_manager.AI_EVOLUTION_DIR", evo_dir
            ), patch("app.ai.evolution.evolver.load_run_meta", return_value=initial_meta), patch(
                "app.ai.evolution.evolver.load_run_results", return_value=None
            ), patch(
                "app.ai.evolution.evolver.append_app_event", return_value={}
            ):
                evolver._evolution_worker(
                    run_id="bt_base",
                    goal_id=None,
                    max_generations=1,
                    provider="openrouter",
                    model=None,
                    loop_id=loop_id,
                )

            version_file = strategies / f"{expected_version_id}.py"
            self.assertTrue(version_file.exists())
            patch_file = evo_dir / loop_id / "generation_1" / "mutation.patch"
            self.assertTrue(patch_file.exists())

            run_log = json.loads((evo_dir / f"{loop_id}.json").read_text(encoding="utf-8"))
            generation = run_log["generations"][0]
            self.assertEqual(generation["version_id"], expected_version_id)
            self.assertEqual(generation["generation_index"], 1)
            self.assertEqual(generation["parent_version_id"], "DemoStrategy")
            self.assertEqual(generation["status"], "aborted_pre_mutation")
            self.assertFalse(generation["mutation_summary"]["success"])
            self.assertIsNone(generation["fitness_summary"]["after"])
            self.assertTrue(generation["code_patch_ref"])

    def test_missing_source_file_creates_placeholder_artifact_and_record(self) -> None:
        from app.ai.evolution import evolver

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategies = root / "strategies"
            evo_dir = root / "ai_evolution"
            strategies.mkdir(parents=True, exist_ok=True)
            evo_dir.mkdir(parents=True, exist_ok=True)
            (strategies / "DemoStrategy.py").write_text(
                "class DemoStrategy(object):\n    pass\n",
                encoding="utf-8",
            )

            initial_meta = {
                "base_strategy": "DemoStrategy",
                "strategy_source_name": "MissingVersion",
                "pairs": ["BTC/USDT"],
                "timeframe": "5m",
                "exchange": "binance",
                "timerange": "20240101-20240201",
            }
            loop_id = "loopsrc11x"
            expected_version_id = "DemoStrategy_evo_g1_loopsrc1"

            with patch.dict(
                "sys.modules",
                {"app.ai.evolution.strategy_editor": self._strategy_editor_stub()},
            ), patch("app.ai.evolution.evolver.STRATEGIES_DIR", strategies), patch(
                "app.ai.evolution.evolver.AI_EVOLUTION_DIR", evo_dir
            ), patch("app.ai.evolution.version_manager.STRATEGIES_DIR", strategies), patch(
                "app.ai.evolution.version_manager.AI_EVOLUTION_DIR", evo_dir
            ), patch("app.ai.evolution.evolver.load_run_meta", return_value=initial_meta), patch(
                "app.ai.evolution.evolver.load_run_results", return_value={"dummy": True}
            ), patch(
                "app.ai.evolution.evolver.normalize_backtest_result",
                side_effect=lambda payload: payload,
            ), patch(
                "app.ai.evolution.evolver.analyze", return_value={}
            ), patch(
                "app.ai.evolution.evolver.compute_fitness", return_value=_Fitness(50.0, {"profitability": 10.0})
            ), patch(
                "app.ai.evolution.evolver.append_app_event", return_value={}
            ), patch(
                "app.ai.evolution.evolver._load_strategy_source",
                side_effect=[FileNotFoundError("missing"), "class DemoStrategy(object):\n    pass\n"],
            ):
                evolver._evolution_worker(
                    run_id="bt_base",
                    goal_id=None,
                    max_generations=1,
                    provider="openrouter",
                    model=None,
                    loop_id=loop_id,
                )

            version_file = strategies / f"{expected_version_id}.py"
            self.assertTrue(version_file.exists())
            patch_file = evo_dir / loop_id / "generation_1" / "mutation.patch"
            self.assertTrue(patch_file.exists())

            run_log = json.loads((evo_dir / f"{loop_id}.json").read_text(encoding="utf-8"))
            generation = run_log["generations"][0]
            self.assertEqual(generation["status"], "aborted_pre_mutation")
            self.assertEqual(generation["version_id"], expected_version_id)
            self.assertFalse(generation["mutation_summary"]["success"])
            self.assertIsNotNone(generation["fitness_summary"]["before"])
            self.assertIsNone(generation["fitness_summary"]["after"])

    def test_normal_generation_preserves_version_metadata_contract(self) -> None:
        from app.ai.evolution import evolver

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategies = root / "strategies"
            evo_dir = root / "ai_evolution"
            strategies.mkdir(parents=True, exist_ok=True)
            evo_dir.mkdir(parents=True, exist_ok=True)
            (strategies / "DemoStrategy.py").write_text(
                "class DemoStrategy(object):\n    pass\n",
                encoding="utf-8",
            )

            initial_meta = {
                "base_strategy": "DemoStrategy",
                "strategy_source_name": "DemoStrategy",
                "pairs": ["BTC/USDT"],
                "timeframe": "5m",
                "exchange": "binance",
                "timerange": "20240101-20240201",
            }
            loop_id = "loopnorm1x"
            expected_version_id = "DemoStrategy_evo_g1_loopnorm"

            mutation_result = SimpleNamespace(
                success=True,
                new_code="class DemoStrategy(object):\n    pass\n",
                version_id=expected_version_id,
                version_name=expected_version_id,
                candidate_vector={"stoploss": -0.1},
                candidate_fingerprint="abc123def4567890",
                changes_summary="tiny tweak",
                validation_errors=[],
            )

            start_backtest_calls: list[dict] = []

            def _fake_start_backtest(**kwargs):
                start_backtest_calls.append(kwargs)
                return "bt_child"

            with patch.dict(
                "sys.modules",
                {"app.ai.evolution.strategy_editor": self._strategy_editor_stub(mutate_result=mutation_result)},
            ), patch("app.ai.evolution.evolver.STRATEGIES_DIR", strategies), patch(
                "app.ai.evolution.evolver.AI_EVOLUTION_DIR", evo_dir
            ), patch("app.ai.evolution.version_manager.STRATEGIES_DIR", strategies), patch(
                "app.ai.evolution.version_manager.AI_EVOLUTION_DIR", evo_dir
            ), patch("app.ai.evolution.evolver.load_run_meta", side_effect=[initial_meta, {"status": "completed"}]), patch(
                "app.ai.evolution.evolver.load_run_results",
                side_effect=[{"base": True}, {"candidate": True}],
            ), patch(
                "app.ai.evolution.evolver.normalize_backtest_result",
                side_effect=lambda payload: payload,
            ), patch(
                "app.ai.evolution.evolver.analyze", return_value={}
            ), patch(
                "app.ai.evolution.evolver.compute_fitness",
                side_effect=[_Fitness(50.0, {"profitability": 10}), _Fitness(55.0, {"profitability": 12})],
            ), patch(
                "app.ai.evolution.version_manager.create_backtest_workspace",
                return_value=strategies,
            ), patch(
                "app.ai.evolution.evolver.start_backtest", side_effect=_fake_start_backtest
            ), patch(
                "app.ai.evolution.evolver.wait_for_run",
                return_value={"status": "completed", "version_id": expected_version_id},
            ), patch(
                "app.ai.evolution.evolver._evaluate_regime_robustness",
                return_value=(True, None, {}),
            ), patch(
                "app.ai.evolution.evolver.append_app_event", return_value={}
            ), patch(
                "app.ai.evolution.evolver.feedback_store.get_history", return_value=[]
            ), patch(
                "app.ai.evolution.evolver.feedback_store.record_pending", return_value=None
            ), patch(
                "app.ai.evolution.evolver.feedback_store.record", return_value=None
            ), patch(
                "app.ai.evolution.evolver.detect_regime",
                new=AsyncMock(side_effect=RuntimeError("skip regime")),
            ):
                evolver._evolution_worker(
                    run_id="bt_base",
                    goal_id=None,
                    max_generations=1,
                    provider="openrouter",
                    model=None,
                    loop_id=loop_id,
                )

            self.assertTrue(start_backtest_calls)
            extra_meta = start_backtest_calls[0]["extra_meta"]
            self.assertEqual(extra_meta["version_id"], expected_version_id)
            self.assertIn("parent_version_id", extra_meta)
            self.assertEqual(extra_meta["generation_index"], 1)

    def test_duplicate_candidate_triggers_retry_then_runs_novel_candidate(self) -> None:
        from app.ai.evolution import evolver

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategies = root / "strategies"
            evo_dir = root / "ai_evolution"
            strategies.mkdir(parents=True, exist_ok=True)
            evo_dir.mkdir(parents=True, exist_ok=True)
            (strategies / "DemoStrategy.py").write_text("class DemoStrategy(object):\n    pass\n", encoding="utf-8")

            initial_meta = {
                "base_strategy": "DemoStrategy",
                "strategy_source_name": "DemoStrategy",
                "pairs": ["BTC/USDT"],
                "timeframe": "5m",
                "exchange": "binance",
                "timerange": "20240101-20240201",
            }
            duplicate_result = SimpleNamespace(
                success=True,
                new_code="class DemoStrategy(object):\n    pass\n",
                version_id="DemoStrategy_evo_g1_loopdupe",
                version_name="DemoStrategy_evo_g1_loopdupe",
                candidate_vector={"stoploss": -0.1},
                candidate_fingerprint="dupdupdupdup0001",
                changes_summary="dup candidate",
                validation_errors=[],
            )
            novel_result = SimpleNamespace(
                success=True,
                new_code="class DemoStrategy(object):\n    pass\n",
                version_id="DemoStrategy_evo_g1_loopdupe",
                version_name="DemoStrategy_evo_g1_loopdupe",
                candidate_vector={"stoploss": -0.08},
                candidate_fingerprint="novelnovelnovel1",
                changes_summary="novel candidate",
                validation_errors=[],
            )
            match = {"candidate_fingerprint": "dupdupdupdup0001", "version_id": "old_v1"}
            start_backtest_calls: list[dict] = []

            def _fake_start_backtest(**kwargs):
                start_backtest_calls.append(kwargs)
                return "bt_child"

            with ExitStack() as stack:
                stack.enter_context(
                    patch.dict(
                        "sys.modules",
                        {"app.ai.evolution.strategy_editor": self._strategy_editor_stub_sequence([duplicate_result, novel_result])},
                    )
                )
                stack.enter_context(patch("app.ai.evolution.evolver.STRATEGIES_DIR", strategies))
                stack.enter_context(patch("app.ai.evolution.evolver.AI_EVOLUTION_DIR", evo_dir))
                stack.enter_context(patch("app.ai.evolution.version_manager.STRATEGIES_DIR", strategies))
                stack.enter_context(patch("app.ai.evolution.version_manager.AI_EVOLUTION_DIR", evo_dir))
                stack.enter_context(patch("app.ai.evolution.evolver.load_run_meta", side_effect=[initial_meta, {"status": "completed"}]))
                stack.enter_context(patch("app.ai.evolution.evolver.load_run_results", side_effect=[{"base": True}, {"candidate": True}]))
                stack.enter_context(patch("app.ai.evolution.evolver.normalize_backtest_result", side_effect=lambda payload: payload))
                stack.enter_context(patch("app.ai.evolution.evolver.analyze", return_value={}))
                stack.enter_context(
                    patch(
                        "app.ai.evolution.evolver.compute_fitness",
                        side_effect=[_Fitness(50.0, {"profitability": 10}), _Fitness(52.0, {"profitability": 11})],
                    )
                )
                stack.enter_context(patch("app.ai.evolution.evolver.start_backtest", side_effect=_fake_start_backtest))
                stack.enter_context(
                    patch(
                        "app.ai.evolution.evolver.wait_for_run",
                        return_value={"status": "completed", "version_id": "DemoStrategy_evo_g1_loopdupe"},
                    )
                )
                stack.enter_context(patch("app.ai.evolution.evolver._evaluate_regime_robustness", return_value=(True, None, {})))
                stack.enter_context(patch("app.ai.evolution.evolver.append_app_event", return_value={}))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.get_history", return_value=[]))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.list_candidate_attempts", return_value=[]))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.find_candidate", side_effect=[match, None]))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.record_candidate_attempt", return_value=None))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.record_pending", return_value=None))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.record", return_value=None))
                stack.enter_context(
                    patch(
                        "app.ai.evolution.evolver.detect_regime",
                        new=AsyncMock(side_effect=RuntimeError("skip regime")),
                    )
                )
                stack.enter_context(
                    patch("app.ai.evolution.version_manager.create_backtest_workspace", return_value=strategies)
                )
                evolver._evolution_worker(
                    run_id="bt_base",
                    goal_id=None,
                    max_generations=1,
                    provider="openrouter",
                    model=None,
                    loop_id="loopdupe1",
                )

            self.assertEqual(len(start_backtest_calls), 1)
            run_log = json.loads((evo_dir / "loopdupe1.json").read_text(encoding="utf-8"))
            generation = run_log["generations"][0]
            self.assertEqual(generation["retry_attempt"], 2)
            self.assertEqual(generation["candidate_fingerprint"], "novelnovelnovel1")

    def test_duplicate_exhaustion_marks_generation_duplicate_rejected_without_backtest(self) -> None:
        from app.ai.evolution import evolver

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategies = root / "strategies"
            evo_dir = root / "ai_evolution"
            strategies.mkdir(parents=True, exist_ok=True)
            evo_dir.mkdir(parents=True, exist_ok=True)
            (strategies / "DemoStrategy.py").write_text("class DemoStrategy(object):\n    pass\n", encoding="utf-8")

            initial_meta = {
                "base_strategy": "DemoStrategy",
                "strategy_source_name": "DemoStrategy",
                "pairs": ["BTC/USDT"],
                "timeframe": "5m",
                "exchange": "binance",
                "timerange": "20240101-20240201",
            }
            duplicate_result = SimpleNamespace(
                success=True,
                new_code="class DemoStrategy(object):\n    pass\n",
                version_id="DemoStrategy_evo_g1_loopexhs",
                version_name="DemoStrategy_evo_g1_loopexhs",
                candidate_vector={"stoploss": -0.1},
                candidate_fingerprint="dupe_always_0001",
                changes_summary="same again",
                validation_errors=[],
            )
            match = {"candidate_fingerprint": "dupe_always_0001", "version_id": "old_v2"}
            start_backtest_calls: list[dict] = []

            def _fake_start_backtest(**kwargs):
                start_backtest_calls.append(kwargs)
                return "bt_child"

            with ExitStack() as stack:
                stack.enter_context(
                    patch.dict(
                        "sys.modules",
                        {
                            "app.ai.evolution.strategy_editor": self._strategy_editor_stub_sequence(
                                [duplicate_result, duplicate_result, duplicate_result]
                            )
                        },
                    )
                )
                stack.enter_context(patch("app.ai.evolution.evolver.STRATEGIES_DIR", strategies))
                stack.enter_context(patch("app.ai.evolution.evolver.AI_EVOLUTION_DIR", evo_dir))
                stack.enter_context(patch("app.ai.evolution.version_manager.STRATEGIES_DIR", strategies))
                stack.enter_context(patch("app.ai.evolution.version_manager.AI_EVOLUTION_DIR", evo_dir))
                stack.enter_context(patch("app.ai.evolution.evolver.load_run_meta", return_value=initial_meta))
                stack.enter_context(patch("app.ai.evolution.evolver.load_run_results", return_value={"base": True}))
                stack.enter_context(patch("app.ai.evolution.evolver.normalize_backtest_result", side_effect=lambda payload: payload))
                stack.enter_context(patch("app.ai.evolution.evolver.analyze", return_value={}))
                stack.enter_context(
                    patch("app.ai.evolution.evolver.compute_fitness", return_value=_Fitness(50.0, {"profitability": 10}))
                )
                stack.enter_context(patch("app.ai.evolution.evolver.start_backtest", side_effect=_fake_start_backtest))
                stack.enter_context(patch("app.ai.evolution.evolver.append_app_event", return_value={}))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.get_history", return_value=[]))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.list_candidate_attempts", return_value=[]))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.find_candidate", side_effect=[match, match, match]))
                stack.enter_context(patch("app.ai.evolution.evolver.feedback_store.record_candidate_attempt", return_value=None))
                evolver._evolution_worker(
                    run_id="bt_base",
                    goal_id=None,
                    max_generations=1,
                    provider="openrouter",
                    model=None,
                    loop_id="loopexhs1",
                )

            self.assertEqual(len(start_backtest_calls), 0)
            run_log = json.loads((evo_dir / "loopexhs1.json").read_text(encoding="utf-8"))
            generation = run_log["generations"][0]
            self.assertEqual(generation["status"], "duplicate_rejected")
            self.assertEqual(generation["retry_attempt"], 3)


@unittest.skipIf(_FASTAPI_IMPORT_ERROR is not None, f"FastAPI unavailable: {_FASTAPI_IMPORT_ERROR}")
class EvolutionRouterNormalizationTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_detail_normalizes_legacy_generation_fields(self) -> None:
        from app.routers.evolution import evolution_run_detail

        legacy_payload = {
            "loop_id": "legacy",
            "session": {"best_version": "DemoStrategy_evo_g1"},
            "generations": [
                {
                    "generation": 1,
                    "version_name": "DemoStrategy_evo_g1",
                }
            ],
        }
        with patch("app.routers.evolution.get_run_detail", return_value=legacy_payload):
            detail = await evolution_run_detail("legacy")

        gen = detail["generations"][0]
        self.assertEqual(gen["version_id"], "DemoStrategy_evo_g1")
        self.assertEqual(gen["generation_index"], 1)
        self.assertIn("parent_version_id", gen)
        self.assertIn("mutation_summary", gen)
        self.assertIn("fitness_summary", gen)
        self.assertIn("code_patch_ref", gen)
