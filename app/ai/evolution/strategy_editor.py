"""
Strategy editor — sends strategy source + diagnosis to AI and returns mutated code.

Reuses _extract_python_code and _validate_python_code from the pipeline orchestrator
to avoid duplication.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.ai.pipelines.orchestrator import (
    _extract_python_code,
    _validate_python_code,
    _call_model,
)
from app.ai.models.registry import fetch_free_models
from app.ai.prompts.trading import GOAL_DIRECTIVES
from app.ai.evolution.version_manager import create_version

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
    version_name: str
    changes_summary: str
    validation_errors: list[str] = field(default_factory=list)


def _build_mutation_prompt(
    strategy_name: str,
    source_code: str,
    analysis: dict,
    fitness_value: float,
    goal_id: str | None,
    feedback_history: list[dict],
    generation: int,
) -> str:
    rcd = analysis.get("root_cause_diagnosis") or {}
    param_recs = analysis.get("parameter_recommendations") or []

    goal_directive = (
        GOAL_DIRECTIVES.get(goal_id, "")
        if goal_id
        else "Maximize overall fitness (profit factor, Sharpe, low drawdown)."
    )

    feedback_lines = ""
    if feedback_history:
        recent = feedback_history[-3:]
        lines = []
        for e in recent:
            status = "✓ ACCEPTED" if e.get("accepted") else "✗ REJECTED"
            lines.append(
                f"  Gen {e['generation']} [{status}] Δfitness={e['delta']:+.1f}: {e['changes_summary']}"
            )
        feedback_lines = "FEEDBACK FROM PREVIOUS GENERATIONS:\n" + "\n".join(lines)

    param_rec_lines = ""
    if param_recs:
        lines = [
            f"  - {r.get('parameter','?')}: current={r.get('current_value','?')} → suggest={r.get('suggestion','?')} ({r.get('reason','')})"
            for r in param_recs[:5]
        ]
        param_rec_lines = "PARAMETER RECOMMENDATIONS:\n" + "\n".join(lines)

    return f"""\
STRATEGY SOURCE ({strategy_name}):
```python
{source_code}
```

BACKTEST DIAGNOSIS:
- Health score: {fitness_value:.1f}/100
- Primary weakness: {rcd.get('primary_failure_label', 'unknown')}
- Causal chain: {' → '.join(s.get('finding','') for s in rcd.get('causal_chain',[])[:3])}
- Fix priority: {'; '.join(rcd.get('fix_priority',[])[:3])}
{param_rec_lines}

GOAL: {goal_directive}

{feedback_lines}

TASK: Mutate the strategy Python code to address the primary weakness.
Class name must remain exactly: {strategy_name}
Generation: {generation}
"""


async def mutate_strategy(
    strategy_name: str,
    source_code: str,
    analysis: dict,
    fitness_value: float,
    goal_id: str | None,
    provider: str,
    model: str | None,
    generation: int,
    feedback_history: list[dict],
) -> MutationResult:
    role_overrides = {
        "code_gen": model,
        "reasoner": model,
        "explainer": model,
    } if model else None

    models = await fetch_free_models(provider)

    prompt = _build_mutation_prompt(
        strategy_name=strategy_name,
        source_code=source_code,
        analysis=analysis,
        fitness_value=fitness_value,
        goal_id=goal_id,
        feedback_history=feedback_history,
        generation=generation,
    )

    messages = [
        {"role": "system", "content": _MUTATION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    step = await _call_model("code_gen", messages, models, role_overrides)
    raw_output = step.output_full

    # Extract changes summary from "# CHANGES:" line after the code fence
    changes_summary = "No summary provided."
    changes_match = re.search(r"#\s*CHANGES:\s*(.+)", raw_output, re.IGNORECASE)
    if changes_match:
        changes_summary = changes_match.group(1).strip()

    # Extract and validate code
    new_code = _extract_python_code(raw_output)
    if not new_code:
        return MutationResult(
            success=False,
            new_code=source_code,
            version_name="",
            changes_summary=changes_summary,
            validation_errors=["AI did not return a Python code block."],
        )

    validation = _validate_python_code(raw_output)
    if not validation.valid:
        return MutationResult(
            success=False,
            new_code=source_code,
            version_name="",
            changes_summary=changes_summary,
            validation_errors=validation.errors,
        )

    # Verify class name is preserved
    if not re.search(rf"class\s+{re.escape(strategy_name)}\s*\(", new_code):
        return MutationResult(
            success=False,
            new_code=source_code,
            version_name="",
            changes_summary=changes_summary,
            validation_errors=[f"Class name '{strategy_name}' not found in mutated code."],
        )

    version_name = create_version(strategy_name, new_code, generation)

    return MutationResult(
        success=True,
        new_code=new_code,
        version_name=version_name,
        changes_summary=changes_summary,
        validation_errors=[],
    )
