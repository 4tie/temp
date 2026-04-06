from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"
RUN_FILE = PROJECT_ROOT / "run.py"
DEFAULT_LOG_TAIL_LINES = 20
HEALTH_ENDPOINTS = ("/health", "/healthz")


def print_color(message: str, color: str = Colors.WHITE, *, bold: bool = False) -> None:
    prefix = f"{Colors.BOLD}{color}" if bold else color
    print(f"{prefix}{message}{Colors.RESET}")


def quoted_command(command: list[str]) -> str:
    return " ".join(json.dumps(part) for part in command)


def normalize_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def command_examples() -> list[str]:
    return [
        "python run.py           - Run the server in this terminal",
        "python run.py --detach  - Run the server in background",
        "python run.py stop      - Stop the server",
        "python run.py status    - Check server status",
        "python run.py logs      - Follow logs with colors",
    ]


def load_project_env() -> None:
    if not ENV_FILE.exists():
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_FILE, override=False)
        return
    except ImportError:
        pass

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = normalize_env_value(value)
        if key and key not in os.environ:
            os.environ[key] = value


def project_venv_python() -> Path | None:
    candidates = (
        PROJECT_ROOT / "4t" / "Scripts" / "python.exe",
        PROJECT_ROOT / "4t" / "bin" / "python",
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def server_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


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


def tail_log(log_file: Path, max_lines: int = DEFAULT_LOG_TAIL_LINES) -> str:
    if not log_file.exists():
        return ""
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def colorize_log_line(line: str) -> str:
    line_lower = line.lower()

    if any(x in line_lower for x in ["error", "exception", "traceback", "failed", "failure"]):
        return f"{Colors.RED}{line}{Colors.RESET}"

    if any(x in line_lower for x in ["warning", "warn"]):
        return f"{Colors.YELLOW}{line}{Colors.RESET}"

    if any(x in line_lower for x in ["success", "completed", "started", "listening"]):
        return f"{Colors.GREEN}{line}{Colors.RESET}"

    if "info" in line_lower:
        return f"{Colors.CYAN}{line}{Colors.RESET}"

    if " 200 " in line or " 201 " in line or " 204 " in line:
        return f"{Colors.GREEN}{line}{Colors.RESET}"
    if " 400 " in line or " 401 " in line or " 403 " in line or " 404 " in line:
        return f"{Colors.YELLOW}{line}{Colors.RESET}"
    if " 500 " in line or " 502 " in line or " 503 " in line:
        return f"{Colors.RED}{line}{Colors.RESET}"

    return line


def stream_logs_with_color(log_file: Path, stop_event: threading.Event) -> None:
    if not log_file.exists():
        time.sleep(0.5)
        if not log_file.exists():
            return

    with log_file.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)

        while not stop_event.is_set():
            line = f.readline()
            if line:
                print(colorize_log_line(line.rstrip()))
            else:
                time.sleep(0.1)


def check_server_health(host: str, port: int) -> tuple[bool, str]:
    try:
        import urllib.error
        import urllib.request

        for endpoint in HEALTH_ENDPOINTS:
            url = f"{server_url(host, port)}{endpoint}"
            req = urllib.request.Request(url, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=2) as response:
                    if response.status == 200:
                        return True, f"healthy via {endpoint}"
                    return False, f"{endpoint} returned status {response.status}"
            except urllib.error.URLError:
                continue
        return False, "not responding"
    except Exception as e:
        return False, str(e)


def build_background_command(python_exec: Path, *, reload: bool) -> list[str]:
    command = [str(python_exec), str(RUN_FILE), "start", "--foreground"]
    if not reload:
        command.append("--no-reload")
    return command


def validate_bind_target(host: str, port: int) -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        details = f"Could not bind dev server to {server_url(host, port)}"
        if getattr(exc, "winerror", None) == 10013:
            raise RuntimeError(
                f"{details}. Windows blocked access to that port. "
                "Set BACKTEST_API_PORT to an unreserved port such as 8000 in `.env` and retry."
            ) from exc
        raise RuntimeError(f"{details}: {exc}") from exc
    finally:
        probe.close()


def start_detached_process(command: list[str], log_file: Path, env: dict[str, str]) -> subprocess.Popen:
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

        return subprocess.Popen(command, **kwargs)


def print_recent_logs(log_file: Path) -> None:
    log_tail = tail_log(log_file)
    if not log_tail:
        return
    print_color("Recent logs:", Colors.RED)
    for line in log_tail.splitlines():
        print(colorize_log_line(line))


def print_server_summary(host: str, port: int, pid: int, log_file: Path) -> None:
    print()
    print_color("✓ Dev server started successfully", Colors.GREEN, bold=True)
    print(f"{Colors.CYAN}URL:{Colors.RESET} {Colors.BOLD}{server_url(host, port)}{Colors.RESET}")
    print(f"{Colors.CYAN}PID:{Colors.RESET} {pid}")
    print(f"{Colors.CYAN}Log:{Colors.RESET} {Colors.DIM}{log_file}{Colors.RESET}")
    print(f"\n{Colors.DIM}Commands:{Colors.RESET}")
    for example in command_examples():
        print(f"  {Colors.WHITE}{example}{Colors.RESET}")


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


def stop_registered_server(*, quiet: bool = False) -> int:
    host, port, pid_file, log_file = server_paths()
    record = cleanup_stale_pid(pid_file)
    if not record:
        if not quiet:
            print(f"{Colors.YELLOW}No background dev server is registered{Colors.RESET}")
            print(f"{Colors.DIM}Expected pid file: {pid_file}{Colors.RESET}")
        return 0

    pid = int(record.get("pid") or 0)
    if not quiet:
        print_color(f"Stopping dev server (pid {pid})...", Colors.BLUE)

    try:
        terminate_process_tree(pid)
    except ProcessLookupError:
        pass

    deadline = time.time() + 5.0
    while process_is_running(pid) and time.time() < deadline:
        time.sleep(0.2)

    if process_is_running(pid):
        if not quiet:
            print(f"{Colors.RED}{Colors.BOLD}✗ Failed to stop dev server pid {pid}{Colors.RESET}")
            print(f"{Colors.DIM}Check log: {record.get('log_file', str(log_file))}{Colors.RESET}")
        return 1

    remove_pid_record(pid_file)
    if not quiet:
        print(
            f"{Colors.GREEN}{Colors.BOLD}✓ Stopped dev server{Colors.RESET} "
            f"on {server_url(record.get('host', host), record.get('port', port))} (pid {pid})"
        )
    return 0


def ensure_no_registered_server() -> None:
    host, port, pid_file, _ = server_paths()
    record = cleanup_stale_pid(pid_file)
    if not record:
        return

    pid = int(record.get("pid") or 0)
    print(
        f"{Colors.YELLOW}Existing dev server detected on {Colors.BOLD}{server_url(record.get('host', host), record.get('port', port))}{Colors.RESET} "
        f"{Colors.YELLOW}(pid {pid}). Restarting...{Colors.RESET}"
    )
    result = stop_registered_server(quiet=False)
    if result != 0:
        raise RuntimeError(f"Could not stop existing dev server pid {pid}")


def spawn_detached_server(*, reload: bool = True, follow_logs: bool = False) -> int:
    host, port, pid_file, log_file = server_paths()
    ensure_no_registered_server()

    python_exec = resolve_server_python()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    command = build_background_command(python_exec, reload=reload)
    process = start_detached_process(command, log_file, env)

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

    print_color("Starting dev server...", Colors.BLUE)
    print(f"{Colors.DIM}{quoted_command(command)}{Colors.RESET}")
    time.sleep(1.5)

    if process.poll() is not None:
        remove_pid_record(pid_file)
        print_color("✗ Dev server exited immediately after launch", Colors.RED, bold=True)
        print(f"{Colors.DIM}Log: {log_file}{Colors.RESET}")
        print_recent_logs(log_file)
        raise RuntimeError("Dev server failed to start")

    print_color("Checking server health...", Colors.BLUE)
    for attempt in range(10):
        healthy, status = check_server_health(host, port)
        if healthy:
            print_color(f"✓ Server is healthy ({status})", Colors.GREEN, bold=True)
            break
        time.sleep(0.5)
    else:
        print(f"{Colors.YELLOW}⚠ Server started but health check failed: {status}{Colors.RESET}")

    print_server_summary(host, port, process.pid, log_file)

    if follow_logs:
        print(f"\n{Colors.CYAN}Following logs (Ctrl+C to exit):{Colors.RESET}\n")
        stop_event = threading.Event()
        try:
            stream_logs_with_color(log_file, stop_event)
        except KeyboardInterrupt:
            stop_event.set()
            print(f"\n{Colors.YELLOW}Stopped following logs. Server is still running.{Colors.RESET}")
    
    return 0


def stop_server() -> int:
    return stop_registered_server(quiet=False)


def status_server() -> int:
    host, port, pid_file, log_file = server_paths()
    record = cleanup_stale_pid(pid_file)
    if not record:
        print(f"{Colors.YELLOW}Dev server is not running{Colors.RESET}")
        print(f"{Colors.DIM}Start it with: python run.py{Colors.RESET}")
        print(f"{Colors.DIM}Expected log file: {log_file}{Colors.RESET}")
        return 1

    pid = int(record.get("pid") or 0)
    host_val = record.get("host", host)
    port_val = record.get("port", port)

    healthy, health_status = check_server_health(host_val, port_val)

    if healthy:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Dev server is running and healthy{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ Dev server is running but not responding{Colors.RESET}")
        print(f"{Colors.YELLOW}  Health status: {health_status}{Colors.RESET}")

    print(f"\n{Colors.CYAN}Server Details:{Colors.RESET}")
    print(f"  {Colors.WHITE}URL:{Colors.RESET}     {Colors.BOLD}{server_url(host_val, port_val)}{Colors.RESET}")
    print(f"  {Colors.WHITE}PID:{Colors.RESET}     {pid}")
    print(f"  {Colors.WHITE}Reload:{Colors.RESET}  {record.get('reload')}")
    print(f"  {Colors.WHITE}Started:{Colors.RESET} {record.get('started_at')}")
    print(f"  {Colors.WHITE}Health:{Colors.RESET}  {health_status}")
    print(f"  {Colors.WHITE}Log:{Colors.RESET}     {Colors.DIM}{record.get('log_file', str(log_file))}{Colors.RESET}")

    return 0


def run_foreground_server(*, reload: bool = True) -> None:
    ensure_no_registered_server()
    uvicorn = ensure_runtime_server()
    from app.core.config import HOST, PORT

    validate_bind_target(HOST, PORT)

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=reload,
        reload_dirs=["app", "templates", "static"] if reload else None,
    )


def follow_logs() -> int:
    host, port, pid_file, log_file = server_paths()
    record = cleanup_stale_pid(pid_file)

    if not record:
        print(f"{Colors.YELLOW}Dev server is not running{Colors.RESET}")
        return 1

    print(f"{Colors.CYAN}Following logs from: {Colors.DIM}{log_file}{Colors.RESET}")
    print(f"{Colors.DIM}Press Ctrl+C to exit{Colors.RESET}\n")

    stop_event = threading.Event()
    try:
        stream_logs_with_color(log_file, stop_event)
    except KeyboardInterrupt:
        stop_event.set()
        print(f"\n{Colors.YELLOW}Stopped following logs{Colors.RESET}")
    
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="4tie dev server launcher")
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=("start", "stop", "status", "logs"),
        help="`start` runs the dev server in the current terminal by default.",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run the dev server in the current terminal.",
    )
    parser.add_argument(
        "--detach",
        action="store_true",
        help="Run the dev server in background and write logs to the runtime log file.",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable uvicorn hot reload.",
    )
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Follow logs after starting server in background.",
    )
    return parser.parse_args(argv)


def dispatch_command(args: argparse.Namespace) -> int:
    if args.command == "stop":
        return stop_server()
    if args.command == "status":
        return status_server()
    if args.command == "logs":
        return follow_logs()

    detach = bool(args.detach and not args.foreground)
    if not detach:
        run_foreground_server(reload=not args.no_reload)
        return 0
    return spawn_detached_server(reload=not args.no_reload, follow_logs=args.follow)


def main(argv: list[str] | None = None) -> int:
    load_project_env()
    args = parse_args(argv or sys.argv[1:])
    return dispatch_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
