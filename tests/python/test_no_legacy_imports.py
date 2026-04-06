from __future__ import annotations

import ast
import unittest
from pathlib import Path

FORBIDDEN_MODULES = {
    "app.services.result_parser",
    "app.services.result_normalizer",
    "app.ai.conversation_store",
    "app.ai.orchestrator",
    "app.core.json_store",
    "app.services.strategy_scanner",
}


class NoLegacyImportsTest(unittest.TestCase):
    def test_runtime_modules_do_not_import_removed_legacy_modules(self) -> None:
        offenders: list[str] = []
        for path in sorted(Path("app").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module in FORBIDDEN_MODULES:
                        offenders.append(f"{path}:{node.lineno}:from {module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in FORBIDDEN_MODULES:
                            offenders.append(f"{path}:{node.lineno}:import {alias.name}")
        self.assertEqual(offenders, [], msg="\n".join(offenders))
