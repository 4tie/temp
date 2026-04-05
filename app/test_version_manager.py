from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai.evolution import version_manager


class VersionManagerTests(unittest.TestCase):
    def test_create_list_and_accept_version_with_neutral_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            strategies_dir = tmp_path / "strategies"
            evolution_dir = tmp_path / "ai_evolution"
            strategies_dir.mkdir()
            evolution_dir.mkdir()

            (strategies_dir / "MultiMa.py").write_text("class MultiMa:\n    pass\n", encoding="utf-8")
            (strategies_dir / "MultiMa.json").write_text(
                json.dumps({"strategy_name": "MultiMa", "params": {"buy": {"buy_ma_count": 4}}}, indent=2),
                encoding="utf-8",
            )
            (evolution_dir / "loop-1.json").write_text(
                json.dumps(
                    {
                        "loop_id": "loop-1",
                        "session": {"loop_id": "loop-1"},
                        "generations": [
                            {
                                "generation": 1,
                                "version_name": "MultiMa_evo_g1",
                                "fitness_after": 61.3,
                                "new_run_id": "run-123",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch.object(version_manager, "STRATEGIES_DIR", strategies_dir), patch.object(
                version_manager, "AI_EVOLUTION_DIR", evolution_dir
            ):
                version_name = version_manager.create_version("MultiMa", "class MultiMa:\n    value = 1\n", 1)
                self.assertEqual(version_name, "MultiMa_evo_g1")

                version_json = json.loads((strategies_dir / "MultiMa_evo_g1.json").read_text(encoding="utf-8"))
                self.assertEqual(version_json["strategy_name"], "MultiMa")
                self.assertEqual(version_json["params"], {})

                versions = version_manager.list_versions("MultiMa")
                self.assertEqual(len(versions), 1)
                self.assertEqual(versions[0].fitness, 61.3)
                self.assertEqual(versions[0].run_id, "run-123")

                workspace = version_manager.create_backtest_workspace(
                    "MultiMa",
                    "MultiMa_evo_g1",
                    "class MultiMa:\n    value = 2\n",
                    "loop-1",
                    1,
                )
                self.assertTrue((workspace / "MultiMa.py").exists())
                self.assertTrue((workspace / "MultiMa.json").exists())

                accepted = version_manager.accept_version("MultiMa_evo_g1", "MultiMa")
                self.assertTrue(accepted)
                self.assertIn("value = 1", (strategies_dir / "MultiMa.py").read_text(encoding="utf-8"))
                accepted_json = json.loads((strategies_dir / "MultiMa.json").read_text(encoding="utf-8"))
                self.assertEqual(accepted_json["params"], {})


if __name__ == "__main__":
    unittest.main()
