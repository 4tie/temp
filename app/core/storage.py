"""
Compatibility exports for legacy imports.

Use app.core.json_store for new code.
"""

from app.core.json_store import ensure_dir as _ensure, read_json, write_json

__all__ = ["_ensure", "write_json", "read_json"]
