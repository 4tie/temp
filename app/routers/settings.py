"""
Settings router — read and write the .env file.

GET  /settings        → current values (secrets masked)
POST /settings        → write new values to .env and reload os.environ
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["settings"])

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Keys we expose to the frontend (order preserved in UI)
_KEYS: list[tuple[str, str]] = [
    ("OPENROUTER_API_KEYS", "openrouter_api_keys"),
    ("OLLAMA_BASE_URL",     "ollama_base_url"),
    ("FREQTRADE_PATH",      "freqtrade_path"),
    ("USER_DATA_DIR",       "user_data_dir"),
    ("BACKTEST_API_PORT",   "backtest_api_port"),
    ("FREQTRADE_EXCHANGE",  "freqtrade_exchange"),
]

_SECRET_KEYS = {"OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"}


class SettingsSaveRequest(BaseModel):
    # New primary field: accepts comma/newline-separated OpenRouter keys.
    openrouter_api_keys: Optional[str] = None
    # Backward-compatible alias: single key input.
    openrouter_api_key: Optional[str] = None
    ollama_base_url:    Optional[str] = None
    freqtrade_path:     Optional[str] = None
    user_data_dir:      Optional[str] = None
    backtest_api_port:  Optional[str] = None
    freqtrade_exchange: Optional[str] = None


def _mask_secret(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    keys = [k.strip() for k in value.split(",") if k.strip()]
    if not keys:
        return ""
    masked = [("•" * max(0, len(k) - 4)) + k[-4:] for k in keys]
    return ", ".join(masked)


def _is_masked_secret_input(value: str) -> bool:
    if not value:
        return False
    compact = re.sub(r"[\s,]", "", value)
    return bool(compact) and set(compact) == {"•"}


def _normalize_openrouter_keys(raw: str) -> str:
    parts = [p.strip() for p in re.split(r"[\n,]+", raw or "") if p.strip()]
    unique: list[str] = []
    seen: set[str] = set()
    for key in parts:
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    return ",".join(unique)


def _read_env_file() -> dict[str, str]:
    """Parse .env into {KEY: value} preserving only known keys."""
    result: dict[str, str] = {}
    if not _ENV_FILE.exists():
        return result
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip()
    return result


def _write_env_file(values: dict[str, str]) -> None:
    """
    Rewrite .env preserving comments and unknown keys,
    updating only the keys we manage.
    """
    lines: list[str] = []
    if _ENV_FILE.exists():
        lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()

    updated: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped or "=" not in stripped:
            new_lines.append(line)
            continue
        k, _, _ = stripped.partition("=")
        k = k.strip()
        if k in values:
            new_lines.append(f"{k}={values[k]}")
            updated.add(k)
        else:
            new_lines.append(line)

    # Append any keys not already in the file
    for k, v in values.items():
        if k not in updated:
            new_lines.append(f"{k}={v}")

    _ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Reload into os.environ immediately so the running process picks them up
    for k, v in values.items():
        if v:
            os.environ[k] = v
        elif k in os.environ:
            del os.environ[k]


@router.get("")
async def get_settings():
    env = _read_env_file()
    result: dict[str, str] = {}
    for env_key, field_name in _KEYS:
        raw = env.get(env_key, os.environ.get(env_key, ""))
        if env_key == "OPENROUTER_API_KEYS" and not raw:
            raw = env.get("OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
        if env_key in _SECRET_KEYS and raw:
            result[field_name] = _mask_secret(raw)
        else:
            result[field_name] = raw

    # Backward-compatible alias for older frontend code.
    result["openrouter_api_key"] = result.get("openrouter_api_keys", "")
    return result


@router.post("")
async def save_settings(req: SettingsSaveRequest):
    env = _read_env_file()

    field_to_env = {field: env_key for env_key, field in _KEYS}

    openrouter_value = req.openrouter_api_keys
    if openrouter_value is None and req.openrouter_api_key is not None:
        openrouter_value = req.openrouter_api_key
    if openrouter_value is not None:
        # If secret value is masked bullets only, skip (unchanged).
        if not _is_masked_secret_input(openrouter_value):
            normalized = _normalize_openrouter_keys(openrouter_value)
            env["OPENROUTER_API_KEYS"] = normalized
            # Keep single-key env var synced for compatibility with older codepaths.
            first_key = normalized.split(",", 1)[0] if normalized else ""
            env["OPENROUTER_API_KEY"] = first_key

    for field_name, env_key in field_to_env.items():
        value = getattr(req, field_name, None)
        if value is None:
            continue
        # If the field is a secret and the value is all bullets, skip (unchanged)
        if env_key in _SECRET_KEYS and _is_masked_secret_input(value):
            continue
        if env_key == "OPENROUTER_API_KEYS":
            # Handled above (also syncs OPENROUTER_API_KEY)
            continue
        env[env_key] = value.strip() if value else ""

    _write_env_file(env)
    return {"saved": True}
