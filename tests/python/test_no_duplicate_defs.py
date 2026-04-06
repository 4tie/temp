from __future__ import annotations

import ast
import unittest
from pathlib import Path


class NoDuplicateDefsTest(unittest.TestCase):
    def test_structured_runtime_modules_have_no_duplicate_top_level_defs(self) -> None:
        files = sorted(
            path
            for pattern in (
                "app/ai/evolution/*.py",
                "app/services/results/*.py",
                "app/services/strategies/*.py",
                "app/services/ai_chat/*.py",
                "app/routers/ai_chat/*.py",
            )
            for path in Path().glob(pattern)
            if path.name != "__init__.py"
        )
        for path in files:
            with self.subTest(path=str(path)):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                seen: dict[str, int] = {}
                duplicates: list[str] = []
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if node.name in seen:
                            duplicates.append(f"{node.name}@{seen[node.name]}->{node.lineno}")
                        else:
                            seen[node.name] = node.lineno
                self.assertEqual(duplicates, [], msg=f"duplicate defs in {path}: {duplicates}")
