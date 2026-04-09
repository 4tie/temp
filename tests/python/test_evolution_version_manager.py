from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    _FASTAPI_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - environment guard
    TestClient = None
    _FASTAPI_IMPORT_ERROR = exc


class EvolutionVersionManagerRegressionTest(unittest.TestCase):
    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_list_versions_ignores_sidecars_and_malformed_payloads(self) -> None:
        from app.ai.evolution.version_manager import list_versions

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategies = root / "strategies"
            evo_dir = root / "ai_evolution"
            strategies.mkdir(parents=True, exist_ok=True)
            evo_dir.mkdir(parents=True, exist_ok=True)

            strategy = "MultiMa_evo_g3"
            version_one = f"{strategy}_evo_g1_loopcase"
            version_two = f"{strategy}_evo_g2_loopcase"
            (strategies / f"{version_one}.py").write_text("class Strategy(object):\n    pass\n", encoding="utf-8")
            (strategies / f"{version_two}.py").write_text("class Strategy(object):\n    pass\n", encoding="utf-8")

            self._write_json(
                evo_dir / "loopcase.json",
                {
                    "loop_id": "loopcase",
                    "generations": [
                        "skip-me",
                        {
                            "version_id": version_one,
                            "fitness_summary": {"after": {"score": 12.34}},
                        },
                        {
                            "version_name": version_two,
                            "fitness_after": 44.5,
                            "new_run_id": "bt_child2",
                        },
                    ],
                },
            )
            self._write_json(evo_dir / f"{strategy}_candidates.json", [{"version_name": version_one}])
            self._write_json(evo_dir / f"{strategy}_feedback.json", [{"note": "ignore me"}])
            self._write_json(evo_dir / "not-a-run-log.json", [{"unexpected": True}])
            self._write_json(evo_dir / "bad-generations.json", {"generations": {"not": "a list"}})

            with patch("app.ai.evolution.version_manager.STRATEGIES_DIR", strategies), patch(
                "app.ai.evolution.version_manager.AI_EVOLUTION_DIR", evo_dir
            ):
                versions = list_versions(strategy)

            self.assertEqual([item.version_name for item in versions], [version_one, version_two])
            lookup = {item.version_name: item for item in versions}
            self.assertEqual(lookup[version_one].generation, 1)
            self.assertEqual(lookup[version_one].fitness, 12.34)
            self.assertIsNone(lookup[version_one].run_id)
            self.assertEqual(lookup[version_two].generation, 2)
            self.assertEqual(lookup[version_two].fitness, 44.5)
            self.assertEqual(lookup[version_two].run_id, "bt_child2")


@unittest.skipIf(_FASTAPI_IMPORT_ERROR is not None, f"FastAPI unavailable: {_FASTAPI_IMPORT_ERROR}")
class EvolutionVersionsRouteRegressionTest(unittest.TestCase):
    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_versions_route_returns_200_with_mixed_json_files(self) -> None:
        from app import main as app_main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategies = root / "strategies"
            evo_dir = root / "ai_evolution"
            strategies.mkdir(parents=True, exist_ok=True)
            evo_dir.mkdir(parents=True, exist_ok=True)

            strategy = "MultiMa_evo_g3"
            version_id = f"{strategy}_evo_g1_looproute"
            (strategies / f"{version_id}.py").write_text("class Strategy(object):\n    pass\n", encoding="utf-8")

            self._write_json(
                evo_dir / "looproute.json",
                {
                    "loop_id": "looproute",
                    "generations": [
                        {
                            "version_name": version_id,
                            "fitness_after": 21.0,
                            "new_run_id": "bt_route_1",
                        }
                    ],
                },
            )
            self._write_json(evo_dir / f"{strategy}_candidates.json", [{"version_name": version_id}])
            self._write_json(evo_dir / f"{strategy}_feedback.json", [{"feedback": "ignore me"}])
            self._write_json(evo_dir / "junk.json", [{"unexpected": True}])

            with patch("app.ai.evolution.version_manager.STRATEGIES_DIR", strategies), patch(
                "app.ai.evolution.version_manager.AI_EVOLUTION_DIR", evo_dir
            ), patch("app.main.load_loop_state"):
                with TestClient(app_main.app) as client:
                    response = client.get(f"/evolution/versions/{strategy}")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["version_id"], version_id)
            self.assertEqual(payload[0]["version_name"], version_id)
            self.assertEqual(payload[0]["base_strategy"], strategy)
            self.assertEqual(payload[0]["generation"], 1)
            self.assertEqual(payload[0]["generation_index"], 1)
            self.assertEqual(payload[0]["fitness"], 21.0)
            self.assertEqual(payload[0]["run_id"], "bt_route_1")
