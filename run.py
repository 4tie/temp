import os
import uvicorn
from pathlib import Path

# Load .env before anything else so all os.environ reads pick it up
_env_file = Path(__file__).resolve().parent / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file, override=False)
    except ImportError:
        # dotenv not installed — parse manually (key=value, skip comments)
        for _line in _env_file.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            _k = _k.strip()
            _v = _v.strip()
            if _k and _k not in os.environ:
                os.environ[_k] = _v

if __name__ == "__main__":
    from app.core.config import HOST, PORT

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        reload_dirs=["app", "templates", "static"],
    )
