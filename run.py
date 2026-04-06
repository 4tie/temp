from __future__ import annotations

import os
import sys
import argparse
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
    import uvicorn
    from app.core.config import HOST, PORT
except ImportError as e:
    print(f"Error: {e}")
    sys.exit(1)


def start_server(foreground: bool = False, reload: bool = True, host: str = None, port: int = None):
    """Start the FastAPI server."""
    server_host = host or HOST
    server_port = port or PORT

    if foreground:
        print(f"Starting server on http://{server_host}:{server_port}")
        uvicorn.run(
            "app.main:app",
            host=server_host,
            port=server_port,
            reload=reload,
            log_level="info"
        )
    else:
        # Background mode - for now just run in foreground since we don't have daemon support
        print(f"Starting server in foreground mode on http://{server_host}:{server_port}")
        uvicorn.run(
            "app.main:app",
            host=server_host,
            port=server_port,
            reload=reload,
            log_level="info"
        )


def status():
    """Check server status."""
    import httpx
    try:
        with httpx.Client() as client:
            response = client.get(f"http://{HOST}:{PORT}/healthz", timeout=5)
            if response.status_code == 200:
                print("✓ Server is running")
                return True
            else:
                print(f"✗ Server responded with status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Server is not running: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="4tie Trading App")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the server")
    start_parser.add_argument("--foreground", action="store_true", help="Run in foreground")
    start_parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    start_parser.add_argument("--host", help="Server host")
    start_parser.add_argument("--port", type=int, help="Server port")

    # Status command
    subparsers.add_parser("status", help="Check server status")

    args = parser.parse_args()

    if args.command == "start":
        reload_enabled = not args.no_reload
        start_server(
            foreground=args.foreground,
            reload=reload_enabled,
            host=args.host,
            port=args.port
        )
    elif args.command == "status":
        status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
