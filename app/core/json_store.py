"""
Compatibility exports for legacy imports.

Use app.core.json_io for new code.
"""

from app.core.json_io import ensure_dir, read_json, write_json

__all__ = ["ensure_dir", "write_json", "read_json"]
