"""
AI Pipeline Orchestrator — multi-model pipeline engine.
Supports 6 pipeline types: simple, analysis, debate, code, structured, tool.
Supports true streaming for the final pipeline step.
Logs every run to user_data/ai_pipeline_logs/.
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import tempfile
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, AsyncGenerator

from ..core.storage import write_json, _ensure
from .openrouter_client import chat_complete, stream_chat
from .ai_registry import fetch_free_models, get_model_for_role
from .ai_classifier import (
    classify, Classification, PipelineType, ComplexityLevel,
)

logger = logging.getLogger(__name__)

PIPELINE_LOG_DIR = Path("user_data/ai_pipeline_logs")


@dataclass
class PipelineStep:
    role: str
    model_id: str
    duration_ms: int = 0
    fallback_used: bool = False
    fallback_reason: str | None = None
    selection_reason: str = ""
    output_preview: str = ""
    output_full: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("output_full", None)
        return d


@dataclass
class CodeValidation:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    method: str = "ast_parse"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PipelineResult:
    final_text: str
    pipeline_type: str
    steps: list[PipelineStep] = field(default_factory=list)
    total_duration_ms: int = 0
    confidence: float | None = None
    consensus: bool | None = None
    disagreements: list[str] = field(default_factory=list)
    judge_activated: bool | None = None
    judge_reason: str | None = None
    classification: Classification | None = None
    run_id: str = ""
    code_validation: CodeValidation | None = None
    context_metadata: dict | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "final_text": self.final_text,
            "pipeline_type": self.pipeline_type,
            "steps": [s.to_dict() for s in self.steps],
            "total_duration_ms": self.total_duration_ms,
            "confidence": self.confidence,
            "consensus": self.consensus,
            "disagreements": self.disagreements,
            "judge_activated": self.judge_activated,
            "judge_reason": self.judge_reason,
            "run_id": self.run_id,
        }
        if self.classification:
            d["classification"] = self.classification.model_dump()
        if self.code_validation:
            d["code_validation"] = self.code_validation.to_dict()
        if self.context_metadata:
            d["context_metadata"] = self.context_metadata
        return d


LAST_RESORT_MODEL = "openrouter/free"

REASONER_SYSTEM_PROMPT = """You are an expert quantitative trading strategy analyst with deep expertise in systematic trading, risk management, and FreqTrade.

Provide thorough, evidence-based analysis with specific numbers. Reference these institutional benchmarks:
- Sharpe ratio: <0.5 poor, 0.5-1.0 acceptable, 1.0-2.0 good, >2.0 excellent (institutional target: >1.0)
- Sortino ratio: same scale but preferred over Sharpe for asymmetric returns
- Profit factor: <1.0 losing, 1.0-1.2 marginal, 1.2-1.5 acceptable, 1.5-2.0 good, >2.0 excellent
- Max drawdown: >25% high risk (institutional limit typically 15-20%), >40% dangerous
- Win rate context: 40-60% typical for trend-following, 60-80% for mean-reversion
- Expectancy: must be positive; per-trade expectancy <$0.50 suggests weak edge
- Calmar ratio: >1.0 good, >2.0 excellent (annual return / max drawdown)

For FreqTrade strategies specifically:
- Check stoploss, trailing_stop, minimal_roi configuration
- Evaluate parameter optimization space (IntParameter/DecimalParameter ranges)
- Consider timeframe suitability and startup_candle_count adequacy
- Review entry/exit signal logic for robustness"""

GOAL_DIRECTIVES: dict[str, str] = {
    "lower_drawdown": """GOAL: Reduce Drawdown
Focus your analysis primarily on drawdown reduction. Key metrics to examine: max drawdown %, Calmar ratio (target >1.0), recovery factor. Inspect the stoploss value (aim for -5% to -10%), trailing_stop configuration, and exit reason breakdown. Flag any exit type (force_exit, stop_loss) that exceeds 30% of exits as a risk signal. Suggest tighter stoploss or trailing stop parameters where applicable.""",

    "higher_win_rate": """GOAL: Increase Win Rate
Focus your analysis primarily on improving win rate. Benchmark: 40-60% for trend-following, 60-80% for mean-reversion. Examine entry signal quality (RSI/MA parameters), the ratio of ROI exits vs stoploss exits (high ROI exits = good), and per-pair win rates. Suggest tightening entry conditions, adjusting indicator thresholds, or filtering low-win-rate pairs.""",

    "higher_profit": """GOAL: Maximize Total Profit
Focus on return on investment, profit factor (target >1.5), and expectancy. Examine avg profit/trade, best vs worst trades, and whether the strategy is leaving profits on the table (e.g. exiting too early via minimal_roi). Suggest ROI schedule adjustments, position sizing improvements, and parameter tuning for higher-profit entries.""",

    "more_trades": """GOAL: Increase Trade Frequency
Focus on trade count and signal generation. Examine how many signals fire per timeframe, whether entry conditions are too restrictive, and how loosening RSI/MA thresholds affects quality. Recommend specific parameter relaxations (e.g. raise buy_rsi threshold) that maintain acceptable profit factor (>1.2) while generating more trades.""",

    "cut_losers": """GOAL: Cut Losing Trades
Focus on loss reduction. Examine stoploss tightness, trailing_stop settings, force_exit and stop_loss exit reason frequencies. Calculate the average loss on losing trades and identify if a tighter stoploss or earlier exit could improve overall expectancy. Suggest specific stoploss values and exit condition guards.""",

    "lower_risk": """GOAL: Lower Risk
Focus on overall risk-adjusted returns: Sharpe ratio (target >1.0), Sortino ratio, max consecutive losses, and volatility. Examine position sizing, number of simultaneous open trades, and stoploss configuration. Suggest risk management improvements that preserve returns while reducing volatility.""",

    "scalping": """GOAL: Scalping Optimization
Focus on trade duration, small-profit capture, and high-frequency patterns. Evaluate minimal_roi decay schedule for short-term profit taking (e.g. 0-5 minutes: 1-2%), startup_candle_count adequacy, and spread/fee impact. Suggest ROI table adjustments and fast-exit signal logic for scalping on 1m/5m timeframes.""",

    "swing_trading": """GOAL: Swing Trading Optimization
Focus on medium-term holding (hours to days). Evaluate trailing_stop for profit protection over longer holds, timeframe suitability (1h/4h), and pair selection for swing behavior. Suggest appropriate trailing_stop_positive and minimal_roi values for multi-hour positions.""",

    "compound_growth": """GOAL: Compound Growth
Focus on consistent compounding: stability of returns, profit factor consistency across pairs and time periods, and low drawdown. Evaluate if any pairs disproportionately inflate results. Suggest conservative stoploss, diversified pair selection, and consistent ROI targets that support compounding.""",
}

COMPOSER_SYSTEM_PROMPT = """You are a professional trading strategy report writer. Transform raw analysis into clear, actionable reports.

CRITICAL: Always open your response with a "## Top Priority Actions" section containing exactly 2-3 numbered, concrete action bullets — this must be the very first section. Each bullet must name a specific parameter or action (e.g. "1. Set stoploss = -0.07 (currently -0.10) to reduce average loss size"). After this section, continue with detailed analysis.

Rules:
- ALWAYS start with "## Top Priority Actions" (2-3 numbered bullets with specific parameter suggestions)
- Use structured sections with headers (##)
- Include specific numbers, percentages, and dollar amounts
- Provide actionable recommendations with concrete parameter suggestions
- Reference Sharpe (>1.0 target), profit factor (>1.5 target), max drawdown (<20% target)
- Use bullet points for key findings
- End with prioritized next steps
- Keep all data points from the source analysis — never drop numbers"""

CODE_AWARE_ADVISOR_SYSTEM_PROMPT = """You are a FreqTrade strategy code expert and quantitative analyst. You have been provided with the actual strategy source code and backtest results.

Your analysis MUST:
1. Reference specific function names from the code (e.g. populate_entry_trend, populate_indicators)
2. Quote specific line-level logic you see (e.g. "The entry condition at line X uses RSI < {buy_rsi.value}")
3. Suggest concrete parameter value changes using the strategy's existing IntParameter/DecimalParameter definitions (e.g. "Change buy_rsi from range(20,40) default=30 to default=25")
4. Flag any missing patterns: missing stoploss definition, no trailing_stop, no ROI table, missing NaN guards in indicators
5. Identify entry/exit condition improvements based on the actual signal logic you see

For FreqTrade strategies specifically:
- Check stoploss (recommended -0.05 to -0.10 for most), trailing_stop config
- Review IntParameter/DecimalParameter ranges for optimization potential
- Check startup_candle_count vs indicator lookback requirements
- Identify any populate_indicators redundancies or missing indicators
- Review entry/exit guards for NaN values and edge cases

IMPORTANT: Do NOT repeat performance metrics that are already shown in the UI (total profit, win rate, drawdown). Your output is exclusively about what to change and why."""

ANALYST_SYSTEM_PROMPT = """You are an expert quantitative trading analyst. Provide deep, data-driven analysis of trading strategies.

Reference these benchmarks in your analysis:
- Sharpe ratio benchmarks: <0.5 poor, 0.5-1.0 mediocre, 1.0-2.0 good, >2.0 excellent
- Profit factor: <1.0 losing money, 1.2-1.5 marginal edge, >1.5 solid edge, >2.0 strong edge
- Max drawdown institutional limits: 15-20% typical, >25% high risk
- Recovery factor (net profit / max drawdown): >2.0 indicates resilient strategy
- Win rate is meaningless without risk/reward context — always analyze together

For FreqTrade specifics:
- Evaluate stoploss levels (recommended -5% to -10% for most strategies)
- Check trailing_stop configuration for profit protection
- Assess minimal_roi decay schedule appropriateness
- Review populate_indicators for redundant or missing indicators
- Consider startup_candle_count vs indicator lookback requirements"""

CODE_GEN_SYSTEM_PROMPT = """You are an expert FreqTrade strategy developer. Generate clean, production-ready Python code.

Requirements:
- Use FreqTrade IStrategy interface version 3
- Import from freqtrade.strategy: IStrategy, IntParameter, DecimalParameter, CategoricalParameter, BooleanParameter
- Use talib.abstract as ta for indicators
- Always define: stoploss (recommend -0.05 to -0.10), minimal_roi, timeframe, startup_candle_count
- Use IntParameter/DecimalParameter for tunable values with space="buy" or space="sell"
- Implement populate_indicators(), populate_entry_trend(), populate_exit_trend()
- Add proper guards: check for NaN, ensure indicator warmup period
- Consider trailing_stop for profit protection
- Set can_short = False unless explicitly requested
- Add docstring explaining the strategy logic"""

CODE_EXPLAINER_SYSTEM_PROMPT = """You are a trading strategy code reviewer. Explain code changes clearly and assess their impact.

For each code block:
1. Summarize what the code does in plain language
2. List key parameters and their purpose
3. Explain the entry/exit logic
4. Highlight potential risks or improvements
5. Estimate expected impact on: win rate, profit factor, drawdown
6. Note any FreqTrade-specific best practices followed or violated"""


async def _call_model(
    role: str,
    messages: list[dict],
    models: list,
    role_overrides: dict[str, str] | None = None,
) -> PipelineStep:
    model_id, reason = get_model_for_role(role, models, role_overrides)
    start = time.monotonic()
    fallback_used = False
    fallback_reason = None
    selection_reason = reason

    try:
        result = await chat_complete(messages, model=model_id)
    except Exception as e:
        logger.warning("Model %s failed for role %s: %s — trying fallback", model_id, role, e)
        fallback_used = True
        fallback_reason = str(e)
        selection_reason = f"fallback:{reason}→{LAST_RESORT_MODEL}"
        try:
            result = await chat_complete(messages, model=LAST_RESORT_MODEL)
            model_id = LAST_RESORT_MODEL
        except Exception as e2:
            logger.error("Fallback also failed for role %s: %s", role, e2)
            result = f"[Error: model unavailable for {role}]"

    duration = int((time.monotonic() - start) * 1000)
    return PipelineStep(
        role=role,
        model_id=model_id,
        duration_ms=duration,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        selection_reason=selection_reason,
        output_preview=result[:200],
        output_full=result,
    )


def _save_log(result: PipelineResult) -> None:
    _ensure(PIPELINE_LOG_DIR)
    log_data = {
        "id": result.run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **result.to_dict(),
    }
    log_data.pop("final_text", None)
    write_json(PIPELINE_LOG_DIR / f"{result.run_id}.json", log_data)


def _extract_python_code(code: str) -> str | None:
    fence_start = code.find("```python")
    if fence_start >= 0:
        fence_end = code.find("```", fence_start + 9)
        if fence_end > fence_start:
            return code[fence_start + 9:fence_end].strip()
    if "```" in code:
        parts = code.split("```")
        if len(parts) >= 3:
            block = parts[1].strip()
            if block.startswith("python"):
                block = block[6:].strip()
            return block
    return None


def _validate_python_code(code: str) -> CodeValidation:
    import subprocess
    import tempfile
    import shutil

    code_block = _extract_python_code(code)
    if not code_block:
        return CodeValidation(valid=True, errors=[], method="no_code_found")

    errors: list[str] = []
    method = "subprocess_ast"

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, prefix="ft_code_"
        ) as tmp:
            tmp.write(code_block)
            tmp_path = tmp.name

        proc = subprocess.run(
            ["python", "-c", f"import ast; ast.parse(open('{tmp_path}').read())"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            err_text = (proc.stderr or proc.stdout or "Unknown AST error").strip()
            for line in err_text.splitlines():
                if line.strip():
                    errors.append(line.strip())
            return CodeValidation(valid=False, errors=errors, method=method)

        ft_bin = shutil.which("freqtrade")
        if ft_bin and "IStrategy" in code_block:
            method = "subprocess_ast+freqtrade"
            try:
                import os
                strategy_dir = os.path.dirname(tmp_path)
                ft_proc = subprocess.run(
                    [ft_bin, "strategy-check", "--strategy-path", strategy_dir,
                     "--strategy", os.path.splitext(os.path.basename(tmp_path))[0]],
                    capture_output=True, text=True, timeout=30,
                )
                if ft_proc.returncode != 0:
                    ft_err = (ft_proc.stderr or ft_proc.stdout or "").strip()
                    if ft_err and "Error" in ft_err:
                        errors.append(f"FreqTrade check: {ft_err[:300]}")
            except Exception:
                pass

    except subprocess.TimeoutExpired:
        errors.append("Validation timed out")
        return CodeValidation(valid=False, errors=errors, method=method)
    except Exception as e:
        try:
            ast.parse(code_block)
        except SyntaxError as se:
            errors.append(f"Syntax error at line {se.lineno}: {se.msg}")
            return CodeValidation(valid=False, errors=errors, method="ast_parse_fallback")
        method = "ast_parse_fallback"
    finally:
        try:
            import os
            os.unlink(tmp_path)
        except Exception:
            pass

    if errors:
        return CodeValidation(valid=False, errors=errors, method=method)
    return CodeValidation(valid=True, errors=[], method=method)


async def run_simple(
    messages: list[dict],
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> PipelineResult:
    models = await fetch_free_models()
    start = time.monotonic()

    step = await _call_model("explainer", messages, models, role_overrides)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=step.output_full,
        pipeline_type="simple",
        steps=[step],
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


async def stream_simple(
    messages: list[dict],
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> AsyncGenerator[dict, None]:
    models = await fetch_free_models()
    model_id, reason = get_model_for_role("explainer", models, role_overrides)
    start = time.monotonic()

    full_text = ""
    async for chunk in stream_chat(messages, model=model_id):
        if chunk.get("error"):
            yield {"error": chunk["error"], "done": True}
            return
        if chunk.get("delta"):
            full_text += chunk["delta"]
            yield {"delta": chunk["delta"], "done": False}
        if chunk.get("done"):
            break

    duration = int((time.monotonic() - start) * 1000)
    step = PipelineStep(
        role="explainer", model_id=model_id, duration_ms=duration,
        selection_reason=reason, output_preview=full_text[:200], output_full=full_text,
    )
    result = PipelineResult(
        final_text=full_text, pipeline_type="simple", steps=[step],
        total_duration_ms=duration, classification=classification,
        run_id=str(uuid.uuid4()),
    )
    _save_log(result)
    pipeline_info = result.to_dict()
    pipeline_info.pop("final_text", None)
    yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


def _build_reasoner_prompt(goal_id: str | None = None) -> str:
    base = REASONER_SYSTEM_PROMPT
    if goal_id and goal_id in GOAL_DIRECTIVES:
        return f"{GOAL_DIRECTIVES[goal_id]}\n\n---\n\n{base}"
    return base


def _build_reasoner_msgs(
    task_prompt: str,
    context: str,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> list[dict]:
    system = _build_reasoner_prompt(goal_id)
    if has_strategy_source:
        system = f"{CODE_AWARE_ADVISOR_SYSTEM_PROMPT}\n\n---\n\n{system}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]


async def run_analysis(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> PipelineResult:
    models = await fetch_free_models()
    start = time.monotonic()
    steps: list[PipelineStep] = []

    reasoner_msgs = _build_reasoner_msgs(task_prompt, context, goal_id, has_strategy_source)
    reasoner_step = await _call_model("reasoner", reasoner_msgs, models, role_overrides)
    steps.append(reasoner_step)

    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Rewrite this analysis for the user:\n\n{reasoner_step.output_full}"},
    ]
    composer_step = await _call_model("composer", composer_msgs, models, role_overrides)
    steps.append(composer_step)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=composer_step.output_full,
        pipeline_type="analysis",
        steps=steps,
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


async def stream_analysis(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> AsyncGenerator[dict, None]:
    models = await fetch_free_models()
    start = time.monotonic()
    steps: list[PipelineStep] = []

    yield {"status": "reasoning", "done": False}

    reasoner_msgs = _build_reasoner_msgs(task_prompt, context, goal_id, has_strategy_source)
    reasoner_step = await _call_model("reasoner", reasoner_msgs, models, role_overrides)
    steps.append(reasoner_step)

    yield {"status": "composing", "done": False}

    model_id, reason = get_model_for_role("composer", models, role_overrides)
    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Rewrite this analysis for the user:\n\n{reasoner_step.output_full}"},
    ]

    full_text = ""
    async for chunk in stream_chat(composer_msgs, model=model_id):
        if chunk.get("error"):
            yield {"error": chunk["error"], "done": True}
            return
        if chunk.get("delta"):
            full_text += chunk["delta"]
            yield {"delta": chunk["delta"], "done": False}
        if chunk.get("done"):
            break

    composer_duration = int((time.monotonic() - start) * 1000) - sum(s.duration_ms for s in steps)
    steps.append(PipelineStep(
        role="composer", model_id=model_id, duration_ms=composer_duration,
        selection_reason=reason, output_preview=full_text[:200], output_full=full_text,
    ))

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=full_text, pipeline_type="analysis", steps=steps,
        total_duration_ms=total_ms, classification=classification,
        run_id=str(uuid.uuid4()),
    )
    _save_log(result)
    pipeline_info = result.to_dict()
    pipeline_info.pop("final_text", None)
    yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


async def run_debate(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> PipelineResult:
    models = await fetch_free_models()
    start = time.monotonic()
    steps: list[PipelineStep] = []

    analyst_system = ANALYST_SYSTEM_PROMPT
    if goal_id and goal_id in GOAL_DIRECTIVES:
        analyst_system = f"{GOAL_DIRECTIVES[goal_id]}\n\n---\n\n{analyst_system}"
    if has_strategy_source:
        analyst_system = f"{CODE_AWARE_ADVISOR_SYSTEM_PROMPT}\n\n---\n\n{analyst_system}"
    analyst_msgs = [
        {"role": "system", "content": analyst_system},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]

    analyst_a_task = _call_model("analyst_a", analyst_msgs, models, role_overrides)
    analyst_b_task = _call_model("analyst_b", analyst_msgs, models, role_overrides)
    analyst_a_step, analyst_b_step = await asyncio.gather(analyst_a_task, analyst_b_task)
    steps.extend([analyst_a_step, analyst_b_step])

    should_judge = True
    judge_reason = "complexity=high"
    if classification and classification.complexity != ComplexityLevel.high:
        len_a = len(analyst_a_step.output_full)
        len_b = len(analyst_b_step.output_full)
        ratio = max(len_a, len_b) / max(min(len_a, len_b), 1)
        should_judge = ratio > 1.4
        judge_reason = f"output_ratio={ratio:.2f}>1.4" if should_judge else f"output_ratio={ratio:.2f}<=1.4 (skipped)"

    if should_judge:
        judge_msgs = [
            {"role": "system", "content": """You are a senior analyst judge. Compare two independent analyses of the same trading strategy.
Return ONLY valid JSON (no markdown):
{
  "shared_conclusions": ["conclusion 1", "conclusion 2"],
  "disagreements": ["point of disagreement 1"],
  "confidence": 0.85,
  "best_recommendation": "The strongest recommendation from either analysis",
  "weak_points": ["weak point 1"]
}"""},
            {"role": "user", "content": f"""Compare these two analyses:

=== ANALYST A ===
{analyst_a_step.output_full}

=== ANALYST B ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""},
        ]
        judge_step = await _call_model("judge", judge_msgs, models, role_overrides)
        steps.append(judge_step)

        confidence = None
        consensus = None
        disagreements: list[str] = []

        try:
            judge_text = judge_step.output_full.strip()
            js = judge_text.find("{")
            je = judge_text.rfind("}") + 1
            if js >= 0 and je > js:
                judge_data = json.loads(judge_text[js:je])
                confidence = float(judge_data.get("confidence", 0.7))
                disagreements = judge_data.get("disagreements", [])
                shared = judge_data.get("shared_conclusions", [])
                consensus = len(disagreements) <= len(shared)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Judge output parse error: %s", e)
            confidence = 0.6

        composer_input = f"""Based on two independent analyses and a judge review, compose the final answer.

Judge summary: {judge_step.output_full}

=== FULL ANALYST A OUTPUT ===
{analyst_a_step.output_full}

=== FULL ANALYST B OUTPUT ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""
    else:
        confidence = 0.75
        consensus = True
        disagreements = []
        composer_input = f"""Compose a clear final answer from these analyses:

=== ANALYST A ===
{analyst_a_step.output_full}

=== ANALYST B ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""

    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": composer_input},
    ]
    composer_step = await _call_model("composer", composer_msgs, models, role_overrides)
    steps.append(composer_step)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=composer_step.output_full,
        pipeline_type="debate",
        steps=steps,
        total_duration_ms=total_ms,
        confidence=confidence,
        consensus=consensus,
        disagreements=disagreements,
        judge_activated=should_judge,
        judge_reason=judge_reason,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


async def stream_debate(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> AsyncGenerator[dict, None]:
    models = await fetch_free_models()
    start = time.monotonic()
    steps: list[PipelineStep] = []

    yield {"status": "analyzing", "done": False}

    analyst_system = ANALYST_SYSTEM_PROMPT
    if goal_id and goal_id in GOAL_DIRECTIVES:
        analyst_system = f"{GOAL_DIRECTIVES[goal_id]}\n\n---\n\n{analyst_system}"
    if has_strategy_source:
        analyst_system = f"{CODE_AWARE_ADVISOR_SYSTEM_PROMPT}\n\n---\n\n{analyst_system}"
    analyst_msgs = [
        {"role": "system", "content": analyst_system},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]

    analyst_a_task = _call_model("analyst_a", analyst_msgs, models, role_overrides)
    analyst_b_task = _call_model("analyst_b", analyst_msgs, models, role_overrides)
    analyst_a_step, analyst_b_step = await asyncio.gather(analyst_a_task, analyst_b_task)
    steps.extend([analyst_a_step, analyst_b_step])

    should_judge = True
    judge_reason = "complexity=high"
    if classification and classification.complexity != ComplexityLevel.high:
        len_a = len(analyst_a_step.output_full)
        len_b = len(analyst_b_step.output_full)
        ratio = max(len_a, len_b) / max(min(len_a, len_b), 1)
        should_judge = ratio > 1.4
        judge_reason = f"output_ratio={ratio:.2f}>1.4" if should_judge else f"output_ratio={ratio:.2f}<=1.4 (skipped)"

    confidence = 0.75
    consensus = True
    disagreements: list[str] = []

    if should_judge:
        yield {"status": "judging", "done": False}
        judge_msgs = [
            {"role": "system", "content": """You are a senior analyst judge. Compare two independent analyses of the same trading strategy.
Return ONLY valid JSON (no markdown):
{
  "shared_conclusions": ["conclusion 1", "conclusion 2"],
  "disagreements": ["point of disagreement 1"],
  "confidence": 0.85,
  "best_recommendation": "The strongest recommendation from either analysis",
  "weak_points": ["weak point 1"]
}"""},
            {"role": "user", "content": f"""Compare these two analyses:

=== ANALYST A ===
{analyst_a_step.output_full}

=== ANALYST B ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""},
        ]
        judge_step = await _call_model("judge", judge_msgs, models, role_overrides)
        steps.append(judge_step)

        try:
            judge_text = judge_step.output_full.strip()
            js = judge_text.find("{")
            je = judge_text.rfind("}") + 1
            if js >= 0 and je > js:
                judge_data = json.loads(judge_text[js:je])
                confidence = float(judge_data.get("confidence", 0.7))
                disagreements = judge_data.get("disagreements", [])
                shared = judge_data.get("shared_conclusions", [])
                consensus = len(disagreements) <= len(shared)
        except (json.JSONDecodeError, ValueError):
            confidence = 0.6

        composer_input = f"""Based on two independent analyses and a judge review, compose the final answer.

Judge summary: {judge_step.output_full}

=== FULL ANALYST A OUTPUT ===
{analyst_a_step.output_full}

=== FULL ANALYST B OUTPUT ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""
    else:
        composer_input = f"""Compose a clear final answer from these analyses:

=== ANALYST A ===
{analyst_a_step.output_full}

=== ANALYST B ===
{analyst_b_step.output_full}

Original request: {task_prompt}"""

    yield {"status": "composing", "done": False}

    model_id, reason = get_model_for_role("composer", models, role_overrides)
    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": composer_input},
    ]

    full_text = ""
    async for chunk in stream_chat(composer_msgs, model=model_id):
        if chunk.get("error"):
            yield {"error": chunk["error"], "done": True}
            return
        if chunk.get("delta"):
            full_text += chunk["delta"]
            yield {"delta": chunk["delta"], "done": False}
        if chunk.get("done"):
            break

    composer_duration = int((time.monotonic() - start) * 1000) - sum(s.duration_ms for s in steps)
    steps.append(PipelineStep(
        role="composer", model_id=model_id, duration_ms=composer_duration,
        selection_reason=reason, output_preview=full_text[:200], output_full=full_text,
    ))

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=full_text, pipeline_type="debate", steps=steps,
        total_duration_ms=total_ms, confidence=confidence, consensus=consensus,
        disagreements=disagreements, judge_activated=should_judge, judge_reason=judge_reason,
        classification=classification, run_id=str(uuid.uuid4()),
    )
    _save_log(result)
    pipeline_info = result.to_dict()
    pipeline_info.pop("final_text", None)
    yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


async def run_code(
    context: str,
    code_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> PipelineResult:
    models = await fetch_free_models()
    start = time.monotonic()
    steps: list[PipelineStep] = []

    code_msgs = [
        {"role": "system", "content": CODE_GEN_SYSTEM_PROMPT},
        {"role": "user", "content": f"{code_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]
    code_step = await _call_model("code_gen", code_msgs, models, role_overrides)
    steps.append(code_step)

    validation = _validate_python_code(code_step.output_full)

    explainer_msgs = [
        {"role": "system", "content": CODE_EXPLAINER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Explain this code/change:\n\n{code_step.output_full}"},
    ]
    explainer_step = await _call_model("explainer", explainer_msgs, models, role_overrides)
    steps.append(explainer_step)

    final_text = f"{explainer_step.output_full}\n\n---\n\n**Generated Code:**\n\n{code_step.output_full}"

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=final_text,
        pipeline_type="code",
        steps=steps,
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
        code_validation=validation,
    )
    return result


async def stream_code(
    context: str,
    code_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> AsyncGenerator[dict, None]:
    models = await fetch_free_models()
    start = time.monotonic()
    steps: list[PipelineStep] = []

    yield {"status": "generating_code", "done": False}

    code_msgs = [
        {"role": "system", "content": CODE_GEN_SYSTEM_PROMPT},
        {"role": "user", "content": f"{code_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]
    code_step = await _call_model("code_gen", code_msgs, models, role_overrides)
    steps.append(code_step)

    yield {"status": "validating_code", "done": False}
    validation = _validate_python_code(code_step.output_full)

    yield {"status": "explaining", "done": False}

    model_id, reason = get_model_for_role("explainer", models, role_overrides)
    explainer_msgs = [
        {"role": "system", "content": CODE_EXPLAINER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Explain this code/change:\n\n{code_step.output_full}"},
    ]

    full_text = ""
    async for chunk in stream_chat(explainer_msgs, model=model_id):
        if chunk.get("error"):
            yield {"error": chunk["error"], "done": True}
            return
        if chunk.get("delta"):
            full_text += chunk["delta"]
            yield {"delta": chunk["delta"], "done": False}
        if chunk.get("done"):
            break

    full_text += f"\n\n---\n\n**Generated Code:**\n\n{code_step.output_full}"
    yield {"delta": f"\n\n---\n\n**Generated Code:**\n\n{code_step.output_full}", "done": False}

    explainer_duration = int((time.monotonic() - start) * 1000) - sum(s.duration_ms for s in steps)
    steps.append(PipelineStep(
        role="explainer", model_id=model_id, duration_ms=explainer_duration,
        selection_reason=reason, output_preview=full_text[:200], output_full=full_text,
    ))

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=full_text, pipeline_type="code", steps=steps,
        total_duration_ms=total_ms, classification=classification,
        run_id=str(uuid.uuid4()), code_validation=validation,
    )
    _save_log(result)
    pipeline_info = result.to_dict()
    pipeline_info.pop("final_text", None)
    yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


async def run_structured(
    context: str,
    task_prompt: str,
    schema_hint: str | None = None,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> PipelineResult:
    models = await fetch_free_models()
    start = time.monotonic()

    system = "You are a structured data generator. Return ONLY valid JSON — no markdown, no explanation, no text outside the JSON object."
    if schema_hint:
        system += f"\n\nExpected JSON schema:\n{schema_hint}"

    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]
    step = await _call_model("structured_output", msgs, models, role_overrides)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=step.output_full,
        pipeline_type="structured",
        steps=[step],
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


async def run_tool(
    context: str,
    task_prompt: str,
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,
) -> PipelineResult:
    models = await fetch_free_models()
    start = time.monotonic()
    steps: list[PipelineStep] = []

    tool_msgs = [
        {"role": "system", "content": "You are a tool-calling assistant for a trading platform. Analyze the request and describe what tools/actions should be executed, with specific parameters and expected outcomes."},
        {"role": "user", "content": f"{task_prompt}\n\n--- CONTEXT ---\n{context}"},
    ]
    tool_step = await _call_model("tool_caller", tool_msgs, models, role_overrides)
    steps.append(tool_step)

    reasoner_msgs = [
        {"role": "system", "content": REASONER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Tool output:\n{tool_step.output_full}\n\nOriginal request: {task_prompt}\n\nContext:\n{context}"},
    ]
    reasoner_step = await _call_model("reasoner", reasoner_msgs, models, role_overrides)
    steps.append(reasoner_step)

    composer_msgs = [
        {"role": "system", "content": COMPOSER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Tool execution result:\n{tool_step.output_full}\n\nReasoning analysis:\n{reasoner_step.output_full}\n\nOriginal request: {task_prompt}"},
    ]
    composer_step = await _call_model("composer", composer_msgs, models, role_overrides)
    steps.append(composer_step)

    total_ms = int((time.monotonic() - start) * 1000)
    result = PipelineResult(
        final_text=composer_step.output_full,
        pipeline_type="tool",
        steps=steps,
        total_duration_ms=total_ms,
        classification=classification,
        run_id=str(uuid.uuid4()),
    )
    return result


PIPELINE_RUNNERS = {
    PipelineType.simple: "simple",
    PipelineType.analysis: "analysis",
    PipelineType.debate: "debate",
    PipelineType.code: "code",
    PipelineType.structured: "structured",
    PipelineType.tool: "tool",
}


def _classifier_step(classification: Classification) -> PipelineStep:
    return PipelineStep(
        role="classifier",
        model_id=classification.classifier_model_id,
        duration_ms=classification.classifier_duration_ms,
        fallback_used=classification.classifier_fallback_used,
        fallback_reason=classification.classifier_fallback_reason,
        selection_reason=classification.classifier_selection_reason,
        output_preview=f"pipeline={classification.recommended_pipeline.value} complexity={classification.complexity.value}",
        output_full=classification.model_dump_json(),
    )


async def run(
    task_text: str,
    context: str = "",
    role_overrides: dict[str, str] | None = None,
    context_hint: str | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> PipelineResult:
    classification = await classify(task_text, context_hint=context_hint, role_overrides=role_overrides)
    pipeline = classification.recommended_pipeline
    cls_step = _classifier_step(classification)

    logger.info(
        "Orchestrator: classified as %s/%s → pipeline=%s",
        [t.value for t in classification.task_types],
        classification.complexity.value,
        pipeline.value,
    )

    if pipeline == PipelineType.simple:
        messages = [{"role": "user", "content": task_text}]
        if context:
            messages = [
                {"role": "system", "content": f"Context:\n{context}"},
                {"role": "user", "content": task_text},
            ]
        result = await run_simple(messages, role_overrides, classification)

    elif pipeline == PipelineType.analysis:
        result = await run_analysis(context, task_text, role_overrides, classification, goal_id, has_strategy_source)

    elif pipeline == PipelineType.debate:
        result = await run_debate(context, task_text, role_overrides, classification, goal_id, has_strategy_source)

    elif pipeline == PipelineType.code:
        result = await run_code(context, task_text, role_overrides, classification)

    elif pipeline == PipelineType.structured:
        result = await run_structured(context, task_text, role_overrides=role_overrides, classification=classification)

    elif pipeline == PipelineType.tool:
        result = await run_tool(context, task_text, role_overrides, classification)

    else:
        messages = [{"role": "user", "content": task_text}]
        result = await run_simple(messages, role_overrides, classification)

    result.steps.insert(0, cls_step)
    result.total_duration_ms += cls_step.duration_ms
    _save_log(result)
    return result


async def stream_run(
    task_text: str,
    context: str = "",
    role_overrides: dict[str, str] | None = None,
    context_hint: str | None = None,
    goal_id: str | None = None,
    has_strategy_source: bool = False,
) -> AsyncGenerator[dict, None]:
    classification = await classify(task_text, context_hint=context_hint, role_overrides=role_overrides)
    pipeline = classification.recommended_pipeline
    cls_step = _classifier_step(classification)

    logger.info(
        "Orchestrator stream: classified as %s/%s → pipeline=%s",
        [t.value for t in classification.task_types],
        classification.complexity.value,
        pipeline.value,
    )

    yield {"status": "classified", "pipeline_type": pipeline.value, "done": False}

    if pipeline == PipelineType.simple:
        messages = [{"role": "user", "content": task_text}]
        if context:
            messages = [
                {"role": "system", "content": f"Context:\n{context}"},
                {"role": "user", "content": task_text},
            ]
        async for chunk in stream_simple(messages, role_overrides, classification):
            yield chunk

    elif pipeline == PipelineType.analysis:
        async for chunk in stream_analysis(context, task_text, role_overrides, classification, goal_id, has_strategy_source):
            yield chunk

    elif pipeline == PipelineType.debate:
        async for chunk in stream_debate(context, task_text, role_overrides, classification, goal_id, has_strategy_source):
            yield chunk

    elif pipeline == PipelineType.code:
        async for chunk in stream_code(context, task_text, role_overrides, classification):
            yield chunk

    else:
        result = await run(task_text, context, role_overrides, context_hint, goal_id, has_strategy_source)
        pipeline_info = result.to_dict()
        pipeline_info.pop("final_text", None)

        full_text = result.final_text
        yield {"delta": full_text, "done": False}
        yield {"done": True, "fullText": full_text, "pipeline": pipeline_info}


def list_pipeline_logs(limit: int = 50) -> list[dict]:
    _ensure(PIPELINE_LOG_DIR)
    logs = []
    for f in sorted(PIPELINE_LOG_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        from ..core.storage import read_json
        data = read_json(f, None)
        if data:
            logs.append(data)
    return logs


def get_pipeline_log(run_id: str) -> dict | None:
    from ..core.storage import read_json
    return read_json(PIPELINE_LOG_DIR / f"{run_id}.json", None)
