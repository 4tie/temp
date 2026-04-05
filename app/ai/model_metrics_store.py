"""
Persistent model performance metrics used by the model router.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR

_LOCK = threading.Lock()
_METRICS_FILE = Path(BASE_DIR) / "ai_model_metrics.json"
_CACHE: dict[str, Any] | None = None


def _default_payload() -> dict[str, Any]:
    return {"updated_at": time.time(), "roles": {}}


def _load_locked() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not _METRICS_FILE.exists():
        _CACHE = _default_payload()
        return _CACHE
    try:
        _CACHE = json.loads(_METRICS_FILE.read_text(encoding="utf-8"))
    except Exception:
        _CACHE = _default_payload()
    return _CACHE


def _save_locked(payload: dict[str, Any]) -> None:
    _METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _METRICS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_METRICS_FILE)


def get_role_metrics(role: str) -> dict[str, dict[str, float]]:
    with _LOCK:
        payload = _load_locked()
        return dict(payload.get("roles", {}).get(role, {}))


def record_observation(
    *,
    role: str,
    model_id: str,
    success: bool,
    latency_ms: float | None = None,
    rate_limited: bool = False,
) -> None:
    with _LOCK:
        payload = _load_locked()
        roles = payload.setdefault("roles", {})
        role_bucket = roles.setdefault(role, {})
        m = role_bucket.setdefault(
            model_id,
            {
                "requests": 0.0,
                "successes": 0.0,
                "rate_limits": 0.0,
                "latency_sum_ms": 0.0,
                "latency_samples": 0.0,
                "cooldown_until": 0.0,
                "updated_at": time.time(),
            },
        )
        m["requests"] += 1.0
        if success:
            m["successes"] += 1.0
        if rate_limited:
            m["rate_limits"] += 1.0
            m["cooldown_until"] = max(float(m.get("cooldown_until") or 0.0), time.time() + 60.0)
        if latency_ms is not None and latency_ms >= 0:
            m["latency_sum_ms"] += float(latency_ms)
            m["latency_samples"] += 1.0
        m["updated_at"] = time.time()
        payload["updated_at"] = time.time()
        _save_locked(payload)


def get_model_stats(role: str, model_id: str) -> dict[str, float]:
    metrics = get_role_metrics(role).get(model_id) or {}
    requests = float(metrics.get("requests") or 0.0)
    successes = float(metrics.get("successes") or 0.0)
    rate_limits = float(metrics.get("rate_limits") or 0.0)
    latency_sum = float(metrics.get("latency_sum_ms") or 0.0)
    latency_samples = float(metrics.get("latency_samples") or 0.0)
    success_rate = (successes / requests) if requests > 0 else 0.75
    rate_limit_rate = (rate_limits / requests) if requests > 0 else 0.0
    avg_latency = (latency_sum / latency_samples) if latency_samples > 0 else 2000.0
    return {
        "requests": requests,
        "success_rate": success_rate,
        "rate_limit_rate": rate_limit_rate,
        "avg_latency_ms": avg_latency,
        "cooldown_until": float(metrics.get("cooldown_until") or 0.0),
    }
