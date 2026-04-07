"""
Strategy editor — sends strategy source + diagnosis to AI and returns mutated code.

Reuses pipeline orchestrator helpers for Python extraction and validation.
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.ai.evolution.fitness import FitnessScore
from app.ai.evolution.version_manager import create_version
from app.ai.models.registry import fetch_free_models
from app.ai.pipelines.orchestrator import _call_model, _extract_python_code, _validate_python_code
from app.ai.prompts.trading import GOAL_DIRECTIVES

logger = logging.getLogger(__name__)

_MUTATION_SYSTEM_PROMPT = """\
You are an expert FreqTrade strategy developer performing a targeted mutation.

STRICT RULES:
1. Output ONLY valid Python code inside ```python ... ``` fences — nothing before or after
2. Keep the class name EXACTLY as provided — do not rename it
3. Only change: IntParameter/DecimalParameter defaults, minimal_roi values, stoploss,
   trailing_stop settings, and entry/exit indicator thresholds
4. Do NOT change: imports, class name, method signatures, timeframe, startup_candle_count
5. After the closing ``` fence, write a single line starting with "# CHANGES:" followed by
   a 1-2 sentence plain-English description of exactly what you changed and why
6. If you cannot improve the strategy, output the original code unchanged with
   "# CHANGES: No changes made — strategy already optimal for this goal."
"""


@dataclass
class MutationResult:
    success: bool
    new_code: str
    version_id: str
    version_name: str
    candidate_vector: dict[str, Any]
    candidate_fingerprint: str
    changes_summary: str
    validation_errors: list[str] = field(default_factory=list)


_PARAM_TYPES = {"IntParameter", "DecimalParameter", "BooleanParameter", "CategoricalParameter"}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, float):
        return float(Decimal(str(value)).quantize(Decimal("0.000001")))
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, tuple):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _normalize_value(value[k]) for k in sorted(value.keys(), key=lambda item: str(item))}
    return value


def _safe_literal_eval(node: ast.AST) -> Any | None:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _extract_candidate_vector(strategy_name: str, source_code: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source_code)
    except Exception:
        return {}

    class_node: ast.ClassDef | None = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == strategy_name:
            class_node = node
            break
    if class_node is None:
        return {}

    vector: dict[str, Any] = {}
    scalar_hint_tokens = (
        "rsi",
        "adx",
        "atr",
        "threshold",
        "entry",
        "exit",
        "cooldown",
        "protection",
        "guard",
        "limit",
        "take_profit",
        "profit_target",
        "stop_buffer",
    )

    def _capture_scalar(name: str, node: ast.AST) -> None:
        literal = _safe_literal_eval(node)
        if literal is None:
            return
        if isinstance(literal, (int, float, bool, str)):
            vector[name] = _normalize_value(literal)
    for stmt in class_node.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            continue
        name = target.id
        value = stmt.value

        if name in {"minimal_roi", "stoploss", "trailing_stop", "trailing_stop_positive", "trailing_stop_positive_offset"}:
            literal = _safe_literal_eval(value)
            if literal is not None:
                vector[name] = _normalize_value(literal)
            continue

        if isinstance(value, ast.Call):
            func_name = ""
            if isinstance(value.func, ast.Name):
                func_name = value.func.id
            elif isinstance(value.func, ast.Attribute):
                func_name = value.func.attr
            if func_name in _PARAM_TYPES:
                default_node = None
                for kw in value.keywords or []:
                    if kw.arg == "default":
                        default_node = kw.value
                        break
                if default_node is not None:
                    literal = _safe_literal_eval(default_node)
                    if literal is not None:
                        vector[name] = _normalize_value(literal)
                continue

        lowered = name.lower()
        if (
            lowered.startswith(("buy_", "sell_", "entry_", "exit_", "protection_", "cooldown_"))
            or any(token in lowered for token in scalar_hint_tokens)
        ):
            _capture_scalar(name, value)

    # Handle annotated constants: `rsi_entry: int = 30`.
    for stmt in class_node.body:
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            continue
        name = stmt.target.id
        lowered = name.lower()
        if (
            lowered.startswith(("buy_", "sell_", "entry_", "exit_", "protection_", "cooldown_"))
            or any(token in lowered for token in scalar_hint_tokens)
        ) and stmt.value is not None:
            _capture_scalar(name, stmt.value)

    return dict(sorted(vector.items(), key=lambda item: item[0]))


def _candidate_fingerprint(candidate_vector: dict[str, Any]) -> str:
    normalized = json.dumps(candidate_vector or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _build_mutation_prompt(
    strategy_name: str,
    source_code: str,
    analysis: dict,
    fitness: FitnessScore,
    goal_id: str | None,
    feedback_history: list[dict],
    generation: int,
    regime_context: dict | None,
    tried_candidates: list[dict[str, Any]] | None,
    exploration_level: str | None,
    recent_fail_reasons: list[str] | None,
) -> str:
    root_causes = analysis.get("root_cause_diagnosis") or {}
    param_recs = analysis.get("parameter_recommendations") or []
    health = analysis.get("health_score") or {}

    goal_directive = GOAL_DIRECTIVES.get(goal_id, "") if goal_id else "maximize overall fitness"
    feedback_lines = []
    for entry in feedback_history[-3:]:
        if entry.get("accepted") is None:
            status = "PENDING"
        else:
            status = "ACCEPTED" if entry.get("accepted") else "REJECTED"
        delta = entry.get("delta")
        delta_text = "pending" if delta is None else f"{float(delta):+.2f}"
        feedback_lines.append(
            f"- Gen {entry.get('generation')} [{status}] delta={delta_text}: {entry.get('changes_summary', '')}"
        )

    param_lines = [
        f"- {rec.get('parameter', '?')}: current={rec.get('current_value', '?')} -> "
        f"suggest={rec.get('suggestion', '?')} ({rec.get('reason', '')})"
        for rec in param_recs[:5]
    ]
    regime_lines = []
    if regime_context:
        regime_lines.extend(
            [
                f"- Current regime: {regime_context.get('regime', 'unknown')}",
                f"- Trend: {regime_context.get('trend_direction', regime_context.get('trend', 'unknown'))}",
                f"- Volatility: {regime_context.get('volatility_level', regime_context.get('volatility', 'unknown'))}",
                f"- Confidence: {regime_context.get('confidence', 'unknown')}",
            ]
        )
    tried_lines = []
    for entry in (tried_candidates or [])[-5:]:
        fingerprint = str(entry.get("candidate_fingerprint") or "")[:16]
        version_id = str(entry.get("version_id") or "")
        vector = entry.get("candidate_vector") or {}
        compact = ", ".join(f"{k}={vector[k]}" for k in list(sorted(vector.keys()))[:8])
        tried_lines.append(f"- {fingerprint} [{version_id}] :: {compact}")
    fail_lines = [f"- {reason}" for reason in (recent_fail_reasons or [])[-5:] if str(reason or "").strip()]

    return (
        "STRATEGY SOURCE:\n"
        "```python\n"
        f"{source_code}\n"
        "```\n\n"
        "BACKTEST DIAGNOSIS:\n"
        f"- Fitness score: {fitness.value}/100\n"
        f"- Fitness breakdown: {fitness.breakdown}\n"
        f"- Health score: {health.get('total', 0)}/100\n"
        f"- Primary weakness: {root_causes.get('primary_failure_label', 'unknown')}\n"
        f"- Causal chain: {' -> '.join(step.get('finding', '') for step in root_causes.get('causal_chain', [])[:3])}\n"
        f"- Fix priority: {'; '.join(root_causes.get('fix_priority', [])[:3])}\n"
        + ("\n".join(param_lines) + "\n" if param_lines else "")
        + ("\n".join(regime_lines) + "\n" if regime_lines else "")
        + f"\nGOAL: {goal_directive or 'maximize overall fitness'}\n\n"
        + "FEEDBACK FROM PREVIOUS GENERATIONS:\n"
        + ("\n".join(feedback_lines) if feedback_lines else "- None\n")
        + "\n\nTRIED CANDIDATE VECTORS (DO NOT REUSE):\n"
        + ("\n".join(tried_lines) if tried_lines else "- None\n")
        + "\n\nRECENT FAILURE PATTERNS TO AVOID:\n"
        + ("\n".join(fail_lines) if fail_lines else "- None\n")
        + "\n\nTASK: Mutate the strategy Python code to address the primary weakness.\n"
        + "Rules:\n"
        + "1. Output ONLY valid Python code inside ```python ... ``` fences\n"
        + f"2. Keep the class name EXACTLY as {strategy_name}\n"
        + "3. Only change: IntParameter/DecimalParameter defaults, minimal_roi values, stoploss, trailing_stop settings, entry/exit indicator thresholds\n"
        + "4. Do NOT change: imports, class name, method signatures, timeframe, startup_candle_count\n"
        + "5. After the code block, write a 2-sentence \"# CHANGES:\" comment explaining what you changed\n"
        + "6. DO NOT output a candidate that matches any tried candidate vector listed above\n"
        + f"7. exploration_level={exploration_level or 'medium'} (low=small shifts, medium=broader tuning, high=aggressive diversification)\n"
        + f"Generation: {generation}\n"
    )


async def mutate_strategy(
    strategy_name: str,
    source_code: str,
    analysis: dict,
    fitness: FitnessScore,
    goal_id: str | None,
    provider: str,
    model: str | None,
    generation: int,
    feedback_history: list[dict],
    regime_context: dict | None = None,
    version_id: str | None = None,
    tried_candidates: list[dict[str, Any]] | None = None,
    exploration_level: str | None = None,
    recent_fail_reasons: list[str] | None = None,
) -> MutationResult:
    role_overrides = {"code_gen": model, "reasoner": model, "explainer": model} if model else None
    models = await fetch_free_models(provider)
    prompt = _build_mutation_prompt(
        strategy_name=strategy_name,
        source_code=source_code,
        analysis=analysis,
        fitness=fitness,
        goal_id=goal_id,
        feedback_history=feedback_history,
        generation=generation,
        regime_context=regime_context,
        tried_candidates=tried_candidates,
        exploration_level=exploration_level,
        recent_fail_reasons=recent_fail_reasons,
    )
    messages = [
        {"role": "system", "content": _MUTATION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    step = await _call_model("code_gen", messages, models, role_overrides)
    raw_output = step.output_full

    changes_summary = "No summary provided."
    changes_match = re.search(r"#\s*CHANGES:\s*(.+)", raw_output, re.IGNORECASE)
    if changes_match:
        changes_summary = changes_match.group(1).strip()

    new_code = _extract_python_code(raw_output)
    if not new_code:
        return MutationResult(
            success=False,
            new_code=source_code,
            version_id=version_id or "",
            version_name="",
            candidate_vector={},
            candidate_fingerprint="",
            changes_summary=changes_summary,
            validation_errors=["AI did not return a Python code block."],
        )

    validation = _validate_python_code(raw_output)
    if not validation.valid:
        return MutationResult(
            success=False,
            new_code=source_code,
            version_id=version_id or "",
            version_name="",
            candidate_vector={},
            candidate_fingerprint="",
            changes_summary=changes_summary,
            validation_errors=validation.errors,
        )

    if not re.search(rf"class\s+{re.escape(strategy_name)}\s*\(", new_code):
        return MutationResult(
            success=False,
            new_code=source_code,
            version_id=version_id or "",
            version_name="",
            candidate_vector={},
            candidate_fingerprint="",
            changes_summary=changes_summary,
            validation_errors=[f"Class name '{strategy_name}' not found in mutated code."],
        )

    candidate_vector = _extract_candidate_vector(strategy_name, new_code)
    candidate_fingerprint = _candidate_fingerprint(candidate_vector)
    version_name = create_version(strategy_name, new_code, generation, version_name=version_id)
    return MutationResult(
        success=True,
        new_code=new_code,
        version_id=version_name,
        version_name=version_name,
        candidate_vector=candidate_vector,
        candidate_fingerprint=candidate_fingerprint,
        changes_summary=changes_summary,
        validation_errors=[],
    )


def extract_candidate_vector(strategy_name: str, source_code: str) -> dict[str, Any]:
    return _extract_candidate_vector(strategy_name, source_code)
