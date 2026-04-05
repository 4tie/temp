from __future__ import annotations

import unittest
from pathlib import Path


class ModelRouterRegressionTests(unittest.TestCase):
    def test_orchestrator_and_classifier_do_not_embed_role_policy(self) -> None:
        root = Path(__file__).resolve().parent
        orchestrator_text = (root / "ai" / "pipelines" / "orchestrator.py").read_text(encoding="utf-8")
        classifier_text = (root / "ai" / "pipelines" / "classifier.py").read_text(encoding="utf-8")
        self.assertNotIn("ROLE_CANDIDATES", orchestrator_text)
        self.assertNotIn("ROLE_CANDIDATES", classifier_text)
        self.assertNotIn("ROLE_PREFERENCES", orchestrator_text)
        self.assertNotIn("ROLE_PREFERENCES", classifier_text)

    def test_registry_uses_central_router(self) -> None:
        root = Path(__file__).resolve().parent
        registry_text = (root / "ai" / "models" / "registry.py").read_text(encoding="utf-8")
        self.assertIn("select_model_for_role", registry_text)


if __name__ == "__main__":
    unittest.main()
