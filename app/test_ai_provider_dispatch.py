from __future__ import annotations

import unittest
from unittest.mock import patch

from app.ai.models import provider_dispatch


class ProviderDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_complete_falls_back_openrouter_to_ollama(self) -> None:
        async def fake_retry(
            provider_name: str,
            requested_model: str,
            actual_model: str,
            caller,
            *,
            caller_kwargs=None,
        ):
            if provider_name == "openrouter":
                raise RuntimeError("openrouter failed")
            return "fallback-ok", {
                "provider": "ollama",
                "model": actual_model,
                "attempt_count": 1,
                "attempts": [],
            }

        with (
            patch.object(provider_dispatch, "_ensure_free_model", return_value="deepseek/free:free"),
            patch.object(provider_dispatch, "_dispatch_ollama_model_v2", return_value="llama3:8b"),
            patch.object(provider_dispatch, "_retry_call_v2", side_effect=fake_retry),
        ):
            text = await provider_dispatch.chat_complete(
                messages=[{"role": "user", "content": "hello"}],
                model="deepseek/free",
                provider="openrouter",
            )

        self.assertEqual(text, "fallback-ok")
        meta = provider_dispatch.get_last_dispatch_meta()
        self.assertEqual(meta.get("provider"), "ollama")
        self.assertTrue(meta.get("fallback_used"))
        self.assertTrue(any(str(x).startswith("openrouter:") for x in meta.get("fallback_chain", [])))


if __name__ == "__main__":
    unittest.main()
