from __future__ import annotations

import ast
import unittest
from pathlib import Path


def _import_map(path: Path) -> dict[str, set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            imports.setdefault(node.module or "", set()).update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.setdefault(alias.name, set())
    return imports


def _top_level_defs(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


class ServiceOwnershipBoundariesTest(unittest.TestCase):
    def test_runner_uses_run_services_instead_of_local_forwarding_wrappers(self) -> None:
        path = Path("app/services/runner.py")
        imports = _import_map(path)
        defs = _top_level_defs(path)

        self.assertNotIn("subprocess", imports, msg="runner.py should use run_process_service.spawn_and_stream")
        self.assertIn("app.services.runs.run_process_service", imports)
        self.assertIn("spawn_and_stream", imports["app.services.runs.run_process_service"])
        self.assertIn("collect_backtest_run_results", imports["app.services.runs.backtest_run_service"])
        self.assertIn("load_hyperopt_run_results", imports["app.services.runs.hyperopt_run_service"])
        self.assertTrue(
            {
                "_normalized_command",
                "_read_runtime_config",
                "_ensure_valid_strategy_json",
                "_spawn_and_stream",
                "_try_import_fresh_global_result",
                "_run_subprocess",
            }.isdisjoint(defs)
        )

    def test_storage_delegates_result_policy_to_results_layer(self) -> None:
        path = Path("app/services/storage.py")
        imports = _import_map(path)
        defs = _top_level_defs(path)

        result_service_imports = imports.get("app.services.results.result_service", set())
        self.assertIn("load_stored_backtest_results", result_service_imports)
        self.assertIn("build_compact_backtest_result", result_service_imports)
        self.assertNotIn("parse_backtest_results", result_service_imports)
        self.assertNotIn("build_metric_snapshot", imports.get("app.services.results.metric_registry", set()))
        self.assertNotIn("_results_need_rehydrate", defs)
