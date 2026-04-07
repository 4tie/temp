from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.ai_chat.apply_code_service import apply_code_impl
from app.services.strategies import promote_staged_strategy_version
from app.services.strategies import stage_strategy_source_change


class StrategyStagedChangeContractTest(unittest.TestCase):
    def _seed_strategy(self, root: Path, strategy_name: str = "DemoStrategy") -> None:
        (root / f"{strategy_name}.py").write_text(
            "class DemoStrategy:\n"
            "    timeframe = '5m'\n",
            encoding="utf-8",
        )
        (root / f"{strategy_name}.json").write_text(
            '{"strategy_name":"DemoStrategy","params":{"buy":{},"sell":{}}}',
            encoding="utf-8",
        )

    def test_apply_code_endpoint_contract_stages_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_strategy(root)

            thread = {
                "messages": [
                    {
                        "id": "assistant-1",
                        "role": "assistant",
                        "content": "Use DemoStrategy.py\n```python\nclass DemoStrategy:\n    timeframe = '15m'\n```",
                    }
                ]
            }

            with patch("app.services.ai_chat.apply_code_service.STRATEGIES_DIR", root), patch(
                "app.services.ai_chat.apply_code_service.load_thread",
                return_value=thread,
            ):
                result = apply_code_impl(
                    thread_id="thread-1",
                    assistant_message_id="assistant-1",
                    code_block_index=0,
                    fallback_strategy="DemoStrategy",
                    direct_apply=False,
                )

            self.assertTrue(result["staged"])
            self.assertTrue(result["requires_manual_promotion"])
            self.assertEqual(result["version_name"], "DemoStrategy_evo_g1")
            self.assertTrue((root / "DemoStrategy_evo_g1.py").exists())
            # Base strategy source must remain unchanged until manual promotion.
            self.assertIn("timeframe = '5m'", (root / "DemoStrategy.py").read_text(encoding="utf-8"))

    def test_promote_staged_version_replaces_base_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_strategy(root)
            staged = stage_strategy_source_change(
                strategy_name="DemoStrategy",
                source="class DemoStrategy:\n    timeframe = '1h'\n",
                strategies_dir=root,
                reason="test",
                actor="test",
            )

            promote_staged_strategy_version(
                strategy_name="DemoStrategy",
                version_name=staged["version_name"],
                strategies_dir=root,
            )

            self.assertIn("timeframe = '1h'", (root / "DemoStrategy.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
