from __future__ import annotations

from app.core.processes import append_log, get_logs


def log_command_start(run_id: str, cmd: list[str]) -> None:
    append_log(run_id, f"$ {' '.join(cmd)}")
    append_log(run_id, "")


def log_process_exit(run_id: str, code: int) -> None:
    append_log(run_id, f"Process exited with code {code}")


def persist_logs(run_id: str, save_logs_fn) -> None:
    save_logs_fn(run_id, get_logs(run_id))
