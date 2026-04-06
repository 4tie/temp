from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import AI_LOOP_REPORTS_DIR, BASE_DIR, STRATEGIES_DIR
from app.services.results.metric_registry import AI_LOOP_REPORT_METRICS, build_metric_delta_rows


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_delta(before: Any, after: Any) -> str:
    try:
        b = float(before)
        a = float(after)
        return f"{a - b:+.4f}"
    except Exception:
        return "n/a"


def summarize_step_metrics(session: dict[str, Any]) -> dict[str, Any]:
    step_metrics = session.get("step_metrics") or []
    by_step: dict[str, list[float]] = defaultdict(list)
    for row in step_metrics:
        by_step[str(row.get("step"))].append(float(row.get("duration_ms") or 0))
    summary = {}
    for step, arr in by_step.items():
        summary[step] = {
            "count": len(arr),
            "avg_ms": round(sum(arr) / len(arr), 2) if arr else 0,
            "max_ms": round(max(arr), 2) if arr else 0,
            "min_ms": round(min(arr), 2) if arr else 0,
        }
    return {"steps": step_metrics, "summary": summary}


def result_delta_rows(before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[dict[str, Any]]:
    b = before or {}
    a = after or {}
    rows = build_metric_delta_rows(b, a, AI_LOOP_REPORT_METRICS, section="core")
    sections = [
        ("summary_metrics", sorted(set((a.get("summary_metrics") or {}).keys()) | set((b.get("summary_metrics") or {}).keys()))),
        ("balance_metrics", sorted(set((a.get("balance_metrics") or {}).keys()) | set((b.get("balance_metrics") or {}).keys()))),
        ("risk_metrics", sorted(set((a.get("risk_metrics") or {}).keys()) | set((b.get("risk_metrics") or {}).keys()))),
    ]
    for section, keys in sections:
        sec_b = b.get(section) or {}
        sec_a = a.get(section) or {}
        for key in keys:
            if key not in sec_a and key not in sec_b:
                continue
            before_v = sec_b.get(key)
            after_v = sec_a.get(key)
            rows.append(
                {
                    "section": section,
                    "metric": key,
                    "label": key,
                    "before": before_v,
                    "after": after_v,
                    "delta": safe_delta(before_v, after_v),
                }
            )
    return rows


def run_validation_tests(strategy_name: str) -> list[dict[str, Any]]:
    py = os.environ.get("FREQTRADE_PYTHON") or os.environ.get("PYTHON") or "python"
    commands: list[tuple[str, list[str]]] = [
        (
            "Python syntax compile",
            [
                py,
                "-m",
                "py_compile",
                str(STRATEGIES_DIR / f"{strategy_name}.py"),
                "app/routers/ai_chat/__init__.py",
                "app/services/strategies/strategy_snapshot_service.py",
            ],
        ),
        ("AI chat router tests", [py, "-m", "unittest", "-q", "app.test_ai_chat_router"]),
        ("JS chat page syntax", ["node", "--check", "static/js/pages/ai-diagnosis.js"]),
    ]
    results: list[dict[str, Any]] = []
    for label, cmd in commands:
        started = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(Path(BASE_DIR).parent),
                capture_output=True,
                text=True,
                timeout=180,
            )
            elapsed = round((time.time() - started) * 1000)
            results.append(
                {
                    "name": label,
                    "command": " ".join(cmd),
                    "ok": proc.returncode == 0,
                    "code": proc.returncode,
                    "duration_ms": elapsed,
                    "stdout": (proc.stdout or "").strip()[:2000],
                    "stderr": (proc.stderr or "").strip()[:2000],
                }
            )
        except Exception as exc:
            elapsed = round((time.time() - started) * 1000)
            results.append(
                {
                    "name": label,
                    "command": " ".join(cmd),
                    "ok": False,
                    "code": -1,
                    "duration_ms": elapsed,
                    "stdout": "",
                    "stderr": str(exc),
                }
            )
    return results


def render_loop_markdown(session: dict[str, Any]) -> str:
    rows = session.get("table_rows") or []
    tests = session.get("test_results") or []
    file_changes = session.get("file_changes") or {}
    lines = [
        f"# AI Loop Report: {session.get('loop_id')}",
        "",
        f"- Thread: `{session.get('thread_id')}`",
        f"- Strategy: `{session.get('strategy')}`",
        f"- Baseline run: `{session.get('baseline_run_id')}`",
        f"- New run: `{session.get('new_run_id')}`",
        f"- Status: `{session.get('status')}`",
        f"- Started: `{session.get('started_at')}`",
        f"- Updated: `{session.get('updated_at')}`",
        f"- Rollback On Regression: `{bool(session.get('request', {}).get('rollback_on_regression'))}`",
        "",
        "## Step Timeline",
    ]
    for step in session.get("steps", []):
        lines.append(f"- `{step.get('ts')}` **{step.get('step')}**: {step.get('message')}")
    lines.extend(["", "## Result Deltas (Full Summary Table)", "", "| Section | Metric | Before | After | Delta |", "|---|---|---:|---:|---:|"])
    for row in rows:
        lines.append(
            f"| {row.get('section')} | {row.get('label') or row.get('metric')} | {row.get('before')} | {row.get('after')} | {row.get('delta')} |"
        )
    lines.extend(["", "## File Changes"])
    py_change = (file_changes.get("strategy_py") or {}).get("changed")
    json_change = (file_changes.get("strategy_json") or {}).get("changed")
    lines.append(f"- Strategy `.py`: {'changed' if py_change else 'unchanged'}")
    lines.append(f"- Strategy `.json`: {'changed' if json_change else 'unchanged'}")
    lines.extend(["", "## Test Results", "", "| Test | OK | Code | Duration (ms) |", "|---|---|---:|---:|"])
    for tr in tests:
        lines.append(f"| {tr.get('name')} | {'yes' if tr.get('ok') else 'no'} | {tr.get('code')} | {tr.get('duration_ms')} |")
    lines.extend(["", "## Test Output Snippets"])
    for tr in tests:
        lines.append(f"### {tr.get('name')}")
        lines.append("")
        lines.append("```text")
        snippet = tr.get("stderr") or tr.get("stdout") or "(no output)"
        lines.append(snippet[:1200])
        lines.append("```")
        lines.append("")
    if session.get("validation_text"):
        lines.extend(["## AI Validation", "", session.get("validation_text"), ""])
    metrics = summarize_step_metrics(session)
    lines.extend(["## Step Latency Metrics", "", "| Step | Count | Avg ms | Min ms | Max ms |", "|---|---:|---:|---:|---:|"])
    for step, row in (metrics.get("summary") or {}).items():
        lines.append(f"| {step} | {row.get('count')} | {row.get('avg_ms')} | {row.get('min_ms')} | {row.get('max_ms')} |")
    violations = session.get("stop_rule_violations") or []
    if violations:
        lines.extend(["", "## Stop Rule Violations"])
        for violation in violations:
            lines.append(f"- {violation}")
    if session.get("rollback_applied"):
        lines.extend(["", "## Rollback", "", "- Regression detected; strategy source was rolled back to pre-loop state."])
    return "\n".join(lines)


def write_loop_report(session: dict[str, Any], reports_dir: Path | None = None) -> str:
    root = reports_dir or AI_LOOP_REPORTS_DIR
    root.mkdir(parents=True, exist_ok=True)
    loop_id = session["loop_id"]
    path = root / f"{loop_id}.md"
    payload = render_loop_markdown(session)
    fd, tmp_path = tempfile.mkstemp(prefix=f"{loop_id}.", suffix=".tmp", dir=str(root))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return str(path)
