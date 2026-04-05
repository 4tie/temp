"""
Central model router used by all pipelines/classifier through registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .model_metrics_store import get_model_stats
from .model_routing_policy import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_ROLE,
    MAX_RATE_LIMIT_RATE,
    MIN_AVAILABILITY_SAMPLES,
    MIN_SUCCESS_RATE,
    ROLE_FALLBACK_LIMIT,
    ROLE_REQUIRED_CAPABILITIES,
    ROLE_CANDIDATES,
    ROLE_WEIGHTS,
)


@dataclass(frozen=True)
class ModelDecision:
    model_id: str
    reason: str
    score: float
    fallback_chain: list[str]


def _norm_latency(avg_latency_ms: float) -> float:
    # Map roughly [0..8000+] ms to [0..1] penalty.
    if avg_latency_ms <= 0:
        return 0.0
    if avg_latency_ms >= 8000:
        return 1.0
    return avg_latency_ms / 8000.0


def _candidate_score(
    *,
    role: str,
    model_id: str,
    rank_index: int,
) -> tuple[float, dict[str, float]]:
    weights = ROLE_WEIGHTS.get(role) or ROLE_WEIGHTS.get(DEFAULT_ROLE)
    assert weights is not None
    stats = get_model_stats(role, model_id)
    success_rate = stats["success_rate"]
    error_rate = max(0.0, min(1.0, 1.0 - success_rate))
    rate_limit_rate = stats["rate_limit_rate"]
    latency_penalty = _norm_latency(stats["avg_latency_ms"])

    # Preference rank converted to quality baseline.
    # rank 0 -> 1.0, rank 1 -> 0.95, etc.
    quality = max(0.0, 1.0 - (rank_index * 0.05))

    score = (
        weights.w_quality * quality
        - weights.w_latency * latency_penalty
        - weights.w_error * error_rate
        - weights.w_429 * rate_limit_rate
    )
    return score, {
        "quality": quality,
        "success_rate": success_rate,
        "error_rate": error_rate,
        "rate_limit_rate": rate_limit_rate,
        "latency_penalty": latency_penalty,
    }


def _infer_model_capabilities(model_id: str) -> set[str]:
    mid = str(model_id).lower()
    caps = {"general", "structured"}
    if "vision" not in mid:
        caps.add("code")
    if "vision" in mid:
        caps.add("vision")
    return caps


def _passes_hard_filters(role: str, model_id: str) -> tuple[bool, str]:
    required = ROLE_REQUIRED_CAPABILITIES.get(role, {"general"})
    capabilities = _infer_model_capabilities(model_id)
    if not required.issubset(capabilities):
        return False, f"capability_mismatch(required={sorted(required)},have={sorted(capabilities)})"

    stats = get_model_stats(role, model_id)
    requests = float(stats["requests"])
    if requests >= MIN_AVAILABILITY_SAMPLES:
        if float(stats["success_rate"]) < MIN_SUCCESS_RATE:
            return False, f"availability_fail(success_rate={stats['success_rate']:.3f})"
        if float(stats["rate_limit_rate"]) > MAX_RATE_LIMIT_RATE:
            return False, f"availability_fail(rate_limit_rate={stats['rate_limit_rate']:.3f})"
    cooldown_until = float(stats.get("cooldown_until") or 0.0)
    import time
    if cooldown_until > time.time():
        return False, f"cooldown_until={cooldown_until}"
    return True, "ok"


def _build_fallback_chain(role: str, available_ids: set[str]) -> list[str]:
    candidates = ROLE_CANDIDATES.get(role) or ROLE_CANDIDATES.get(DEFAULT_ROLE, [])
    limit = ROLE_FALLBACK_LIMIT.get(role, 2)
    chain: list[str] = []
    for candidate in candidates:
        if candidate in available_ids:
            ok, _ = _passes_hard_filters(role, candidate)
            if ok:
                chain.append(candidate)
        if len(chain) >= limit:
            break
    return chain


def select_model_for_role(
    role: str,
    models: list[dict[str, Any]],
    overrides: dict[str, str] | None = None,
) -> ModelDecision:
    role_candidates = ROLE_CANDIDATES.get(role) or ROLE_CANDIDATES.get(DEFAULT_ROLE, [])
    available_ids = {m.get("id") for m in models if m.get("id")}
    fallback_chain = _build_fallback_chain(role, available_ids)

    if overrides and role in overrides:
        override_id = overrides[role]
        if override_id in role_candidates and override_id in available_ids:
            ok, why = _passes_hard_filters(role, override_id)
            if ok:
                return ModelDecision(model_id=override_id, reason=f"override:{role}", score=1.0, fallback_chain=fallback_chain)
            return ModelDecision(
                model_id=fallback_chain[0] if fallback_chain else DEFAULT_FALLBACK_MODEL,
                reason=f"invalid_override_filtered:{role}:{why}",
                score=0.0,
                fallback_chain=fallback_chain,
            )
        return ModelDecision(
            model_id=fallback_chain[0] if fallback_chain else DEFAULT_FALLBACK_MODEL,
            reason=f"invalid_override_not_allowed:{role}",
            score=0.0,
            fallback_chain=fallback_chain,
        )

    best: ModelDecision | None = None
    for idx, candidate in enumerate(role_candidates):
        if candidate not in available_ids:
            continue
        ok, why = _passes_hard_filters(role, candidate)
        if not ok:
            continue
        score, parts = _candidate_score(role=role, model_id=candidate, rank_index=idx)
        reason = (
            f"router:{role}:rank={idx}"
            f"|success={parts['success_rate']:.3f}"
            f"|error={parts['error_rate']:.3f}"
            f"|rl={parts['rate_limit_rate']:.3f}"
            f"|lat_pen={parts['latency_penalty']:.3f}"
            f"|score={score:.4f}"
        )
        decision = ModelDecision(model_id=candidate, reason=reason, score=score, fallback_chain=fallback_chain)
        if best is None or decision.score > best.score:
            best = decision

    if best:
        return best

    if fallback_chain:
        return ModelDecision(model_id=fallback_chain[0], reason=f"fallback:role-sequence:{role}", score=0.0, fallback_chain=fallback_chain)
    if available_ids:
        chosen = sorted(available_ids)[0]
        return ModelDecision(model_id=chosen, reason="fallback:first-available", score=0.0, fallback_chain=[chosen])
    return ModelDecision(model_id=DEFAULT_FALLBACK_MODEL, reason="fallback:hardcoded", score=-1.0, fallback_chain=[DEFAULT_FALLBACK_MODEL])
