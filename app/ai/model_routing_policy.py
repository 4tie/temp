"""
Central model routing policy.
This is the single source of truth for role candidates and scoring weights.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleWeights:
    w_quality: float
    w_latency: float
    w_error: float
    w_429: float


ROLE_CANDIDATES: dict[str, list[str]] = {
    "classifier": [
        "meta-llama/llama-3.2-1b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-2-2b-it:free",
        "mistralai/mistral-7b-instruct:free",
    ],
    "reasoner": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
    ],
    "code_gen": [
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
    ],
    "analyst_a": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
    ],
    "analyst_b": [
        "deepseek/deepseek-r1:free",
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ],
    "judge": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.1-70b-instruct:free",
    ],
    "composer": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
    ],
    "explainer": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mixtral-8x7b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
    ],
    "structured_output": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.1-70b-instruct:free",
    ],
    "tool_caller": [
        "meta-llama/llama-3.2-3b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
    ],
}

ROLE_WEIGHTS: dict[str, RoleWeights] = {
    "classifier": RoleWeights(w_quality=0.50, w_latency=0.25, w_error=0.20, w_429=0.05),
    "explainer": RoleWeights(w_quality=0.45, w_latency=0.20, w_error=0.20, w_429=0.15),
    "reasoner": RoleWeights(w_quality=0.60, w_latency=0.10, w_error=0.20, w_429=0.10),
    "code_gen": RoleWeights(w_quality=0.65, w_latency=0.10, w_error=0.15, w_429=0.10),
    "judge": RoleWeights(w_quality=0.55, w_latency=0.05, w_error=0.25, w_429=0.15),
    "analyst_a": RoleWeights(w_quality=0.55, w_latency=0.10, w_error=0.20, w_429=0.15),
    "analyst_b": RoleWeights(w_quality=0.55, w_latency=0.10, w_error=0.20, w_429=0.15),
    "composer": RoleWeights(w_quality=0.50, w_latency=0.15, w_error=0.20, w_429=0.15),
    "structured_output": RoleWeights(w_quality=0.55, w_latency=0.10, w_error=0.20, w_429=0.15),
    "tool_caller": RoleWeights(w_quality=0.40, w_latency=0.25, w_error=0.20, w_429=0.15),
}

DEFAULT_ROLE = "explainer"
DEFAULT_FALLBACK_MODEL = "meta-llama/llama-3.2-1b-instruct:free"

# Hard filters
ROLE_REQUIRED_CAPABILITIES: dict[str, set[str]] = {
    "classifier": {"general"},
    "explainer": {"general"},
    "reasoner": {"general"},
    "analyst_a": {"general"},
    "analyst_b": {"general"},
    "judge": {"general"},
    "composer": {"general"},
    "code_gen": {"code"},
    "structured_output": {"structured"},
    "tool_caller": {"general"},
}

MIN_AVAILABILITY_SAMPLES = 10
MIN_SUCCESS_RATE = 0.45
MAX_RATE_LIMIT_RATE = 0.60

# Strict fallback contract (same role sequence)
ROLE_FALLBACK_LIMIT: dict[str, int] = {
    "classifier": 2,
    "explainer": 2,
    "reasoner": 3,
    "code_gen": 3,
    "judge": 2,
    "analyst_a": 2,
    "analyst_b": 2,
    "composer": 2,
    "structured_output": 2,
    "tool_caller": 2,
}

# Rollout controls
LOW_RISK_ROLES = {"classifier", "explainer"}
