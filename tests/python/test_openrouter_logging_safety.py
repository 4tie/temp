import unittest
from unittest import mock
import sys
import types


if "httpx" not in sys.modules:
    class _DummyResponse:
        status_code = 500
        headers = {}

        def json(self):
            return {}

        @property
        def text(self):
            return ""

    class _DummyHTTPStatusError(Exception):
        def __init__(self, *args, response=None, **kwargs):
            super().__init__(*args)
            self.response = response or _DummyResponse()

    class _DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    sys.modules["httpx"] = types.SimpleNamespace(
        Response=_DummyResponse,
        HTTPStatusError=_DummyHTTPStatusError,
        AsyncClient=_DummyAsyncClient,
        Timeout=lambda *args, **kwargs: None,
    )

from app.ai.models import openrouter_client
from app.services.ai_chat import provider_service


ARROW = chr(0x2192)
ARABIC = "".join(chr(cp) for cp in (1605, 1585, 1581, 1576, 1575))


class OpenRouterLoggingSafetyTests(unittest.IsolatedAsyncioTestCase):
    def test_safe_log_text_ascii_normalizes_unicode(self):
        text = f"bad {ARROW} value"
        self.assertEqual(
            provider_service._safe_log_text(text),
            r"bad \u2192 value",
        )
        self.assertEqual(
            openrouter_client._safe_log_text(text),
            r"bad \u2192 value",
        )

    async def test_provider_payload_degrades_safely_when_model_list_fails(self):
        text = f"bad {ARROW} value"
        with mock.patch.object(provider_service, "has_api_keys", return_value=True), \
             mock.patch.object(provider_service, "or_list_models", side_effect=RuntimeError(text)), \
             mock.patch.object(provider_service, "is_available", return_value=False):
            payload = await provider_service.get_providers_payload()

        self.assertFalse(payload["openrouter"]["available"])
        self.assertEqual(payload["openrouter"]["models"], [])

    def test_model_list_warning_is_deduped(self):
        text = f"bad {ARROW} value"
        with mock.patch.object(openrouter_client.logger, "warning") as warning:
            openrouter_client._LAST_MODELS_WARNING = ("", 0.0)
            openrouter_client._warn_models_issue("OpenRouter model list failed", text, dedupe_window=60.0)
            openrouter_client._warn_models_issue("OpenRouter model list failed", text, dedupe_window=60.0)

        self.assertEqual(warning.call_count, 1)

    def test_unicode_encode_issue_is_suppressed_to_debug(self):
        text = f"bad {ARROW} value"
        detail = UnicodeEncodeError("ascii", text, 4, 5, "ordinal not in range(128)")
        with mock.patch.object(openrouter_client.logger, "warning") as warning, \
             mock.patch.object(openrouter_client.logger, "debug") as debug:
            openrouter_client._warn_models_issue("OpenRouter model list failed", detail)

        warning.assert_not_called()
        debug.assert_called_once()

    def test_headers_are_ascii_safe(self):
        with mock.patch.object(openrouter_client, "_DEFAULT_HTTP_REFERER", f"https://4tie.local/{ARABIC}"), \
             mock.patch.object(openrouter_client, "_DEFAULT_APP_TITLE", f"4tie {ARABIC}"):
            headers = openrouter_client._headers_for("token")

        headers["HTTP-Referer"].encode("ascii")
        headers["X-Title"].encode("ascii")
        self.assertTrue(headers["HTTP-Referer"].startswith("https://4tie.local/"))


if __name__ == "__main__":
    unittest.main()
