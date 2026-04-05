from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai import model_metrics_store
from app.ai.model_router import select_model_for_role


class ModelRouterTests(unittest.TestCase):
    def test_override_wins(self) -> None:
        models = [{"id": "meta-llama/llama-3.2-1b-instruct:free"}]
        decision = select_model_for_role(
            role="classifier",
            models=models,
            overrides={"classifier": "meta-llama/llama-3.2-1b-instruct:free"},
        )
        self.assertEqual(decision.model_id, "meta-llama/llama-3.2-1b-instruct:free")
        self.assertIn("override:classifier", decision.reason)

    def test_prefers_ranked_candidate_when_available(self) -> None:
        models = [
            {"id": "mistralai/mistral-7b-instruct:free"},
            {"id": "meta-llama/llama-3.2-1b-instruct:free"},
        ]
        decision = select_model_for_role(role="classifier", models=models)
        self.assertEqual(decision.model_id, "meta-llama/llama-3.2-1b-instruct:free")

    def test_metrics_penalize_rate_limited_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_file = Path(tmpdir) / "metrics.json"
            with (
                patch.object(model_metrics_store, "_METRICS_FILE", metrics_file),
                patch.object(model_metrics_store, "_CACHE", None),
            ):
                for _ in range(20):
                    model_metrics_store.record_observation(
                        role="classifier",
                        model_id="meta-llama/llama-3.2-1b-instruct:free",
                        success=True,
                        latency_ms=200,
                        rate_limited=True,
                    )
                for _ in range(20):
                    model_metrics_store.record_observation(
                        role="classifier",
                        model_id="meta-llama/llama-3.2-3b-instruct:free",
                        success=True,
                        latency_ms=200,
                        rate_limited=False,
                    )

                models = [
                    {"id": "meta-llama/llama-3.2-1b-instruct:free"},
                    {"id": "meta-llama/llama-3.2-3b-instruct:free"},
                ]
                decision = select_model_for_role(role="classifier", models=models)

        self.assertEqual(decision.model_id, "meta-llama/llama-3.2-3b-instruct:free")

    def test_cooldown_filters_model_and_uses_fallback_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_file = Path(tmpdir) / "metrics.json"
            with (
                patch.object(model_metrics_store, "_METRICS_FILE", metrics_file),
                patch.object(model_metrics_store, "_CACHE", None),
            ):
                # Trigger cooldown on top-ranked classifier model.
                model_metrics_store.record_observation(
                    role="classifier",
                    model_id="meta-llama/llama-3.2-1b-instruct:free",
                    success=True,
                    latency_ms=150,
                    rate_limited=True,
                )
                models = [
                    {"id": "meta-llama/llama-3.2-1b-instruct:free"},
                    {"id": "meta-llama/llama-3.2-3b-instruct:free"},
                    {"id": "google/gemma-2-2b-it:free"},
                ]
                decision = select_model_for_role(role="classifier", models=models)

        self.assertEqual(decision.model_id, "meta-llama/llama-3.2-3b-instruct:free")
        self.assertTrue(decision.fallback_chain)

    def test_invalid_override_is_rejected(self) -> None:
        models = [{"id": "meta-llama/llama-3.2-1b-instruct:free"}]
        decision = select_model_for_role(
            role="classifier",
            models=models,
            overrides={"classifier": "not-allowed/model:free"},
        )
        self.assertEqual(decision.model_id, "meta-llama/llama-3.2-1b-instruct:free")
        self.assertIn("invalid_override", decision.reason)


if __name__ == "__main__":
    unittest.main()
