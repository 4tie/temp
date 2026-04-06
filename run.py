from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"

if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

try:
    import httpx
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG as UVICORN_LOGGING_CONFIG

    from app.core.config import HOST, PORT
except ImportError as e:
    print(f"Error: {e}")
    sys.exit(1)


def _resolve_log_file(log_file: str | None = None) -> Path:
    if log_file:
        return Path(log_file).expanduser()

    env_log_file = os.getenv("APP_LOG_FILE", "").strip()
    if env_log_file:
        return Path(env_log_file).expanduser()

    return PROJECT_ROOT / "user_data" / "runtime" / "server.log"


def _build_uvicorn_log_config(log_file: Path) -> dict:
    log_config = deepcopy(UVICORN_LOGGING_CONFIG)

    log_config.setdefault("handlers", {})
    log_config.setdefault("loggers", {})

    log_config["handlers"]["file_default"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "default",
        "filename": str(log_file),
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 3,
        "encoding": "utf-8",
    }

    log_config["handlers"]["file_access"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "access",
        "filename": str(log_file),
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 3,
        "encoding": "utf-8",
    }

    for logger_name in ("uvicorn", "uvicorn.error"):
        logger_cfg = log_config["loggers"].get(logger_name, {})
        handlers = list(logger_cfg.get("handlers", []))
        if "file_default" not in handlers:
            handlers.append("file_default")
        logger_cfg["handlers"] = handlers
        log_config["loggers"][logger_name] = logger_cfg

    access_cfg = log_config["loggers"].get("uvicorn.access", {})
    access_handlers = list(access_cfg.get("handlers", []))
    if "file_access" not in access_handlers:
        access_handlers.append("file_access")
    access_cfg["handlers"] = access_handlers
    log_config["loggers"]["uvicorn.access"] = access_cfg

    return log_config


def start_server(
    foreground: bool = False,
    reload: bool = True,
    host: str | None = None,
    port: int | None = None,
    log_file: str | None = None,
):
    """Start the FastAPI server."""
    server_host = host or HOST
    server_port = port or PORT

    resolved_log_file = _resolve_log_file(log_file)
    resolved_log_file.parent.mkdir(parents=True, exist_ok=True)
    log_config = _build_uvicorn_log_config(resolved_log_file)

    mode = "foreground" if foreground else "foreground"
    print(f"Starting server in {mode} mode on http://{server_host}:{server_port}")
    print(f"Logging to: {resolved_log_file}")

    uvicorn.run(
        "app.main:app",
        host=server_host,
        port=server_port,
        reload=reload,
        log_level="info",
        log_config=log_config,
    )


def status() -> bool:
    """Check server status."""
    try:
        with httpx.Client() as client:
            response = client.get(f"http://{HOST}:{PORT}/healthz", timeout=5)
            if response.status_code == 200:
                print("OK: Server is running")
                return True

            print(f"ERR: Server responded with status {response.status_code}")
            return False
    except Exception as e:
        print(f"ERR: Server is not running: {e}")
        return False


def show_logs(lines: int = 100, log_file: str | None = None):
    """Print the last N lines from the server log file."""
    resolved_log_file = _resolve_log_file(log_file)
    if not resolved_log_file.exists():
        print(f"Log file not found: {resolved_log_file}")
        return

    content = resolved_log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = content[-max(1, lines) :]

    print(f"Showing last {len(tail)} lines from: {resolved_log_file}")
    for line in tail:
        print(line)


def main():
    parser = argparse.ArgumentParser(description="4tie Trading App")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the server")
    start_parser.add_argument("--foreground", action="store_true", help="Run in foreground")
    start_parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    start_parser.add_argument("--host", help="Server host")
    start_parser.add_argument("--port", type=int, help="Server port")
    start_parser.add_argument("--log-file", help="Path to server log file")

    # Status command
    subparsers.add_parser("status", help="Check server status")

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show recent server logs")
    logs_parser.add_argument("--lines", type=int, default=100, help="Number of log lines to show")
    logs_parser.add_argument("--log-file", help="Path to server log file")

    args = parser.parse_args()

    if args.command == "start":
        reload_enabled = not args.no_reload
        start_server(
            foreground=args.foreground,
            reload=reload_enabled,
            host=args.host,
            port=args.port,
            log_file=args.log_file,
        )
    elif args.command == "status":
        status()
    elif args.command == "logs":
        show_logs(lines=args.lines, log_file=args.log_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
