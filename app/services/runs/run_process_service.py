from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable

from app.core.processes import append_log, get_process, get_status, remove_process, set_process, set_status


def start_daemon(target, *args) -> None:
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()


def mark_running(run_id: str) -> None:
    set_status(run_id, "running")
    set_process(run_id, None)


def status_of(run_id: str) -> str:
    return get_status(run_id)


def stop_process(run_id: str) -> bool:
    proc = get_process(run_id)
    if proc is None:
        return False
    try:
        proc.terminate()
    except Exception:
        return False
    finally:
        remove_process(run_id)
    return True


def spawn_and_stream(run_id: str, cmd: list[str], on_line: Callable[[str], None] | None = None) -> int:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    set_process(run_id, proc)

    for line in proc.stdout:
        text = line.rstrip()
        append_log(run_id, text)
        if on_line:
            on_line(text)

    proc.wait()
    return proc.returncode
