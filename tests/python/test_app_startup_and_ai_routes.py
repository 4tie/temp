from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch


class AppStartupAndAiRoutesTest(unittest.TestCase):
    def test_ai_routes_are_mounted_and_startup_runs(self) -> None:
        from app import main as app_main

        async def _exercise_lifespan() -> set[str]:
            async with app_main.app.router.lifespan_context(app_main.app):
                return {route.path for route in app_main.app.routes}

        with patch("app.main.load_loop_state") as mocked:
            paths = asyncio.run(_exercise_lifespan())

        mocked.assert_called_once()
        self.assertIn("/ai/threads", paths)
        self.assertIn("/ai/conversations", paths)
