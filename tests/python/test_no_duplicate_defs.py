from __future__ import annotations

import ast
import unittest
from pathlib import Path


class NoDuplicateDefsTest(unittest.TestCase):
    def test_selected_evolution_modules_have_no_duplicate_top_level_defs(self) -> None:
        files = [
            Path("app/ai/evolution/evolver.py"),
            Path("app/ai/evolution/fitness.py"),
            Path("app/ai/evolution/strategy_editor.py"),
        ]
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
