from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env() -> None:
    # Load .env before config import so env-backed defaults are available.
    if not ENV_FILE.exists():
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_FILE, override=False)
        return
    except ImportError:
        pass

    # Fallback parser when python-dotenv is unavailable on the current interpreter.
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def project_venv_python() -> Path | None:
    candidates = (
        PROJECT_ROOT / ".venv" / "bin" / "python",
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_runtime_server():
    try:
        import fastapi  # noqa: F401
        import uvicorn
    except ModuleNotFoundError as exc:
        if exc.name not in {"fastapi", "uvicorn"}:
            raise
        return exc
    return uvicorn


def resolve_server_python() -> Path:
    runtime = load_runtime_server()
    if not isinstance(runtime, ModuleNotFoundError):
        return Path(sys.executable).absolute()

    venv_python = project_venv_python()
    if venv_python is not None:
        return venv_python.absolute()

    missing_pkg = runtime.name or "runtime dependency"
    raise RuntimeError(
        f"Missing `{missing_pkg}` on interpreter `{sys.executable}` and no project `.venv` was found."
    ) from runtime


def ensure_runtime_server():
    runtime = load_runtime_server()
    if not isinstance(runtime, ModuleNotFoundError):
        return runtime

    venv_python = project_venv_python()
    current_python = Path(sys.executable).absolute()

    if venv_python is not None and venv_python.absolute() != current_python:
        os.execv(str(venv_python), [str(venv_python), str(PROJECT_ROOT / "run.py"), *sys.argv[1:]])

    missing_pkg = runtime.name or "runtime dependency"
    hint = f" Activate the project virtualenv or run `{venv_python} run.py`." if venv_python else ""
    raise RuntimeError(f"Missing `{missing_pkg}` on interpreter `{sys.executable}`.{hint}") from runtime


def server_paths() -> tuple[str, int, Path, Path]:
    from app.core.config import HOST, PORT, DEV_SERVER_LOG_FILE, DEV_SERVER_PID_FILE

    return HOST, PORT, DEV_SERVER_PID_FILE, DEV_SERVER_LOG_FILE


def read_pid_record(pid_file: Path) -> dict[str, Any] | None:
    if not pid_file.exists():
        return None
    try:
        data = json.loads(pid_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def write_pid_record(pid_file: Path, payload: dict[str, Any]) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_pid_record(pid_file: Path) -> None:
    try:
        pid_file.unlink()
    except FileNotFoundError:
        return


def process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def cleanup_stale_pid(pid_file: Path) -> dict[str, Any] | None:
    record = read_pid_record(pid_file)
    if not record:
        return None
    pid = int(record.get("pid") or 0)
    if process_is_running(pid):
        return record
    remove_pid_record(pid_file)
    return None


def tail_log(log_file: Path, max_lines: int = 20) -> str:
    if not log_file.exists():
        return ""
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    os.killpg(pid, signal.SIGTERM)


def spawn_detached_server(*, reload: bool = True) -> int:
    host, port, pid_file, log_file = server_paths()
    record = cleanup_stale_pid(pid_file)
    if record:
        pid = int(record["pid"])
        print(
            f"Dev server is already running on http://{record.get('host', host)}:{record.get('port', port)} "
            f"(pid {pid})."
        )
        print(f"Log: {record.get('log_file', str(log_file))}")
        return 0

    python_exec = resolve_server_python()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"

    command = [str(python_exec), str(PROJECT_ROOT / "run.py"), "start", "--foreground"]
    if not reload:
        command.append("--no-reload")

    with log_file.open("ab") as handle:
        kwargs: dict[str, Any] = {
            "cwd": str(PROJECT_ROOT),
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": handle,
            "stderr": subprocess.STDOUT,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        else:
            kwargs["start_new_session"] = True

        process = subprocess.Popen(command, **kwargs)

    record = {
        "pid": process.pid,
        "host": host,
        "port": port,
        "reload": bool(reload),
        "started_at": utc_now(),
        "python": str(python_exec),
        "log_file": str(log_file),
        "command": command,
    }
    write_pid_record(pid_file, record)
    time.sleep(1.0)

    if process.poll() is not None:
        remove_pid_record(pid_file)
        log_tail = tail_log(log_file)
        raise RuntimeError(
            "Dev server exited immediately after launch.\n"
            f"Log: {log_file}\n"
            f"{log_tail or '(no log output)'}"
        )

    print(f"Dev server started in background on http://{host}:{port}")
    print(f"PID: {process.pid}")
    print(f"Log: {log_file}")
    print("Use `python run.py stop` to stop it or `python run.py --foreground` for inline logs.")
    return 0


def stop_server() -> int:
    host, port, pid_file, log_file = server_paths()
    record = cleanup_stale_pid(pid_file)
    if not record:
        print(f"No background dev server is registered. Expected pid file: {pid_file}")
        return 0

    pid = int(record.get("pid") or 0)
    try:
        terminate_process_tree(pid)
    except ProcessLookupError:
        pass

    deadline = time.time() + 5.0
    while process_is_running(pid) and time.time() < deadline:
        time.sleep(0.2)

    if process_is_running(pid):
        print(f"Failed to stop dev server pid {pid}. Check log: {record.get('log_file', str(log_file))}")
        return 1

    remove_pid_record(pid_file)
    print(f"Stopped dev server on http://{record.get('host', host)}:{record.get('port', port)} (pid {pid}).")
    return 0


def status_server() -> int:
    host, port, pid_file, log_file = server_paths()
    record = cleanup_stale_pid(pid_file)
    if not record:
        print(f"Dev server is not running. Start it with `python run.py`.")
        print(f"Expected log file: {log_file}")
        return 1

    pid = int(record.get("pid") or 0)
    print(f"Dev server is running on http://{record.get('host', host)}:{record.get('port', port)}")
    print(f"PID: {pid}")
    print(f"Reload: {record.get('reload')}")
    print(f"Started: {record.get('started_at')}")
    print(f"Log: {record.get('log_file', str(log_file))}")
    return 0


def run_foreground_server(*, reload: bool = True) -> None:
    uvicorn = ensure_runtime_server()
    from app.core.config import HOST, PORT

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=reload,
        reload_dirs=["app", "templates", "static"] if reload else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="4tie dev server launcher")
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=("start", "stop", "status"),
        help="`start` launches the server in background by default.",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run the dev server in the current terminal instead of detaching.",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable uvicorn hot reload.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_project_env()
    args = parse_args(argv or sys.argv[1:])

    if args.command == "stop":
        return stop_server()
    if args.command == "status":
        return status_server()
    if args.foreground:
        run_foreground_server(reload=not args.no_reload)
        return 0
    return spawn_detached_server(reload=not args.no_reload)


if __name__ == "__main__":
    raise SystemExit(main())
