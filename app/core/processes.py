import asyncio
import subprocess
from typing import Optional

_active_processes: dict[str, subprocess.Popen] = {}
_process_logs: dict[str, list[str]] = {}
_process_status: dict[str, str] = {}


def get_process(run_id: str) -> Optional[subprocess.Popen]:
    return _active_processes.get(run_id)


def set_process(run_id: str, proc: subprocess.Popen):
    _active_processes[run_id] = proc
    if run_id not in _process_logs:
        _process_logs[run_id] = []
    _process_status[run_id] = "running"


def remove_process(run_id: str):
    _active_processes.pop(run_id, None)


def append_log(run_id: str, line: str):
    if run_id not in _process_logs:
        _process_logs[run_id] = []
    _process_logs[run_id].append(line)


def get_logs(run_id: str) -> list[str]:
    return _process_logs.get(run_id, [])


def set_status(run_id: str, status: str):
    _process_status[run_id] = status


def get_status(run_id: str) -> str:
    return _process_status.get(run_id, "unknown")


def clear_process_data(run_id: str):
    _active_processes.pop(run_id, None)
    _process_logs.pop(run_id, None)
    _process_status.pop(run_id, None)
