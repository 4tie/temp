from __future__ import annotations

import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.config import PARSED_RESULTS_FILENAME, RUN_LOGS_FILENAME, RUN_META_FILENAME


def build_run_id(prefix: str = "") -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}{stamp}_{suffix}"


def normalize_command(default_cmd: list[str], command_override: Optional[list[str]]) -> list[str]:
    if not command_override:
        return default_cmd

    cmd = [str(token) for token in command_override]
    if not cmd:
        return default_cmd

    if (
        cmd[0].lower() in {"python", "python3"}
        and "-m" in cmd
        and "freqtrade" in cmd
        and default_cmd
    ):
        cmd[0] = default_cmd[0]

    return cmd


def wait_for_meta_completion(
    run_id: str,
    load_meta: Callable[[str], dict[str, Any] | None],
    get_status: Callable[[str], str],
    timeout_s: int = 600,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        meta = load_meta(run_id)
        if meta and meta.get("status") not in ("running", None):
            return meta
        status = get_status(run_id)
        if status not in ("running", "unknown"):
            return load_meta(run_id) or {"run_id": run_id, "status": status}
        time.sleep(5)
    return load_meta(run_id) or {"run_id": run_id, "status": "timeout"}


def run_meta_path(run_dir: Path) -> Path:
    return run_dir / RUN_META_FILENAME


def run_logs_path(run_dir: Path) -> Path:
    return run_dir / RUN_LOGS_FILENAME


def run_results_path(run_dir: Path) -> Path:
    return run_dir / PARSED_RESULTS_FILENAME
