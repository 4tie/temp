from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_node(script: str) -> None:
    subprocess.run(
        ["node", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_inventory_builder_captures_known_controls() -> None:
    _run_node("scripts/build_ui_workflow_inventory.js")
    inventory_path = ROOT / "docs" / "qa" / "ui-workflow-inventory-latest.json"
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    actions = payload.get("actions", [])
    selectors = {row.get("control_selector") for row in actions}
    pages = {row.get("page") for row in actions}

    assert "#bt-run-btn" in selectors
    assert "#ho-run-btn" in selectors
    assert "ai-diagnosis" in pages


def test_report_generator_writes_dual_markdown_files() -> None:
    _run_node("scripts/generate_ui_workflow_reports.js")
    qa_dir = ROOT / "docs" / "qa"
    pass_latest = qa_dir / "ui-workflow-validation-pass-latest.md"
    issues_latest = qa_dir / "ui-workflow-validation-issues-latest.md"
    summary_latest = qa_dir / "ui-workflow-summary-latest.json"

    assert pass_latest.exists()
    assert issues_latest.exists()
    assert summary_latest.exists()
