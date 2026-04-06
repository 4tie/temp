"""
Evolution orchestrator — runs the closed-loop backtest → analyse → mutate → backtest cycle.

Each evolution session runs in a daemon thread. Progress events are stored in a
module-level queue (dict keyed by loop_id) so the SSE endpoint can drain them.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.ai.events import LoopEventStatus, LoopEventType, coerce_loop_event_type, serialize_evolution_event
from app.core.config import AI_EVOLUTION_DIR, STRATEGIES_DIR
from app.core.json_io import read_json, write_json
from app.services.storage import load_run_meta, load_run_results
from app.services.runner import start_backtest, wait_for_run
from app.ai.tools.deep_analysis import analyze
from app.ai.evolution.fitness import compute_fitness, FitnessScore
from app.ai.evolution import feedback_store
from app.ai.market.regime_detector import detect_regime

logger = logging.getLogger(__name__)

# ── In-memory state ───────────────────────────────────────────────────────────
# loop_id → list of progress event dicts (drained by SSE endpoint)
_evolution_events: dict[str, list[dict]] = {}
# loop_id → session summary dict
_evolution_sessions: dict[str, dict] = {}
_state_lock = threading.Lock()


# ── Public API ────────────────────────────────────────────────────────────────

def start_evolution(
    run_id: str,
    goal_id: str | None,
    max_generations: int,
    provider: str,
    model: str | None,
    loop_id: str,
) -> None:
    """Spawn a daemon thread that runs the evolution loop."""
    with _state_lock:
        _evolution_events[loop_id] = []
        _evolution_sessions[loop_id] = {
            "loop_id": loop_id,
            "run_id": run_id,
            "goal_id": goal_id,
            "max_generations": max_generations,
            "provider": provider,
            "model": model,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "generations_completed": 0,
            "best_fitness": 0.0,
            "best_version": None,
        }

    thread = threading.Thread(
        target=_evolution_worker,
        args=(run_id, goal_id, max_generations, provider, model, loop_id),
        daemon=True,
    )
    thread.start()


def get_evolution_status(loop_id: str) -> dict | None:
    with _state_lock:
        return _evolution_sessions.get(loop_id)


def list_evolution_runs() -> list[dict]:
    with _state_lock:
        sessions = list(_evolution_sessions.values())

    # Also pick up persisted sessions from disk that aren't in memory
    if AI_EVOLUTION_DIR.exists():
        in_memory_ids = {s["loop_id"] for s in sessions}
        for f in sorted(AI_EVOLUTION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.stem.endswith("_feedback"):
                continue
            lid = f.stem
            if lid not in in_memory_ids:
                data = read_json(f, None)
                if data and "loop_id" in data:
                    sessions.append(data.get("session", data))

    return sessions


def drain_events(loop_id: str) -> list[dict]:
    """Pop and return all pending events for a loop_id."""
    with _state_lock:
        events = list(_evolution_events.get(loop_id, []))
        if loop_id in _evolution_events:
            _evolution_events[loop_id].clear()
    return events


def get_run_detail(loop_id: str) -> dict | None:
    path = AI_EVOLUTION_DIR / f"{loop_id}.json"
    return read_json(path, None)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _default_evolution_status(event_type: LoopEventType) -> str:
    if event_type in {LoopEventType.LOOP_FAILED, LoopEventType.BACKTEST_FAILED, LoopEventType.MUTATION_FAILED}:
        return LoopEventStatus.FAILED.value
    if event_type in {LoopEventType.LOOP_COMPLETED, LoopEventType.CYCLE_DONE}:
        return LoopEventStatus.COMPLETED.value
    return LoopEventStatus.INFO.value


def _emit(loop_id: str, event: dict | LoopEventType | str, **kwargs: Any) -> None:
    if isinstance(event, dict):
        raw = dict(event)
        message = kwargs.pop("message", raw.pop("message", None))
        done = bool(kwargs.pop("done", raw.pop("done", False)))
        generation = kwargs.pop("generation", raw.get("generation"))
        raw_status = kwargs.pop("status", raw.pop("status", None))
        event_type = kwargs.pop("event_type", raw.pop("event_type", raw.pop("step", LoopEventType.LOOP_STARTED.value)))
        coerced = coerce_loop_event_type(event_type)
        status = raw_status or _default_evolution_status(coerced)
        payload = {**raw, **kwargs}
        serialized = serialize_evolution_event(
            loop_id,
            coerced,
            status=status,
            message=message,
            done=done,
            generation=generation if isinstance(generation, int) else None,
            payload=payload,
        )
    else:
        message = kwargs.pop("message", None)
        done = bool(kwargs.pop("done", False))
        generation = kwargs.pop("generation", None)
        coerced = coerce_loop_event_type(event)
        status = kwargs.pop("status", _default_evolution_status(coerced))
        serialized = serialize_evolution_event(
            loop_id,
            coerced,
            status=status,
            message=message,
            done=done,
            generation=generation if isinstance(generation, int) else None,
            payload=kwargs,
        )
    with _state_lock:
        if loop_id not in _evolution_events:
            _evolution_events[loop_id] = []
        _evolution_events[loop_id].append(serialized)


def _update_session(loop_id: str, **kwargs: Any) -> None:
    with _state_lock:
        if loop_id in _evolution_sessions:
            _evolution_sessions[loop_id].update(kwargs)


def _save_run_log(loop_id: str, session: dict, generations: list[dict]) -> None:
    write_json(AI_EVOLUTION_DIR / f"{loop_id}.json", {
        "loop_id": loop_id,
        "session": session,
        "generations": generations,
    })


# ── Worker ────────────────────────────────────────────────────────────────────

def _evolution_worker(
    run_id: str,
    goal_id: str | None,
    max_generations: int,
    provider: str,
    model: str | None,
    loop_id: str,
) -> None:
    generations: list[dict] = []
    best_fitness = 0.0
    best_version: str | None = None
    current_run_id = run_id

    try:
        # ── Load initial backtest ─────────────────────────────────────────────
        meta = load_run_meta(current_run_id)
        if not meta:
            _emit(loop_id, {"step": "error", "message": f"Run '{current_run_id}' not found.", "done": True})
            _update_session(loop_id, status="failed")
            return

        strategy_name: str = meta.get("strategy", "")
        pairs: list[str] = meta.get("pairs", [])
        timeframe: str = meta.get("timeframe", "5m")
        exchange: str = meta.get("exchange", "binance")
        timerange: str | None = meta.get("timerange")

        if not strategy_name:
            _emit(loop_id, {"step": "error", "message": "No strategy name in run meta.", "done": True})
            _update_session(loop_id, status="failed")
            return

        for generation in range(1, max_generations + 1):
            gen_record: dict[str, Any] = {
                "generation": generation,
                "base_run_id": current_run_id,
            }

            # ── Step 1: Analyse ───────────────────────────────────────────────
            _emit(loop_id, {
                "step": "analyzing",
                "generation": generation,
                "message": f"Running deep analysis on {current_run_id}…",
            })

            results = load_run_results(current_run_id) or {}
            run_data = {**results, "strategy": strategy_name}
            analysis = analyze(run_data, run_id=current_run_id)
            fitness_before: FitnessScore = compute_fitness(run_data)
            gen_record["fitness_before"] = fitness_before.value
            gen_record["fitness_breakdown_before"] = fitness_before.breakdown

            if generation == 1:
                best_fitness = fitness_before.value

            # ── Step 2: Detect market regime ──────────────────────────────────
            regime_info: dict = {}
            if pairs:
                try:
                    loop = asyncio.new_event_loop()
                    try:
                        regime = loop.run_until_complete(detect_regime(pairs[0], timeframe, exchange))
                    finally:
                        loop.close()
                    regime_info = {
                        "regime": regime.regime,
                        "trend": regime.trend_direction,
                        "volatility": regime.volatility_level,
                    }
                except Exception as exc:
                    logger.debug("Regime detection failed: %s", exc)

            gen_record["regime"] = regime_info

            # ── Step 3: Read strategy source ──────────────────────────────────
            strategy_py = STRATEGIES_DIR / f"{strategy_name}.py"
            if not strategy_py.exists():
                _emit(loop_id, {
                    "step": "error",
                    "generation": generation,
                    "message": f"Strategy file {strategy_name}.py not found.",
                    "done": generation == max_generations,
                })
                break

            source_code = strategy_py.read_text(encoding="utf-8")

            # ── Step 4: Mutate ────────────────────────────────────────────────
            _emit(loop_id, {
                "step": "mutating",
                "generation": generation,
                "message": f"AI editing strategy code (generation {generation})…",
            })

            feedback_history = feedback_store.get_history(strategy_name)

            try:
                loop = asyncio.new_event_loop()
                try:
                    mutation = loop.run_until_complete(mutate_strategy(
                        strategy_name=strategy_name,
                        source_code=source_code,
                        analysis=analysis,
                        fitness_value=fitness_before.value,
                        goal_id=goal_id,
                        provider=provider,
                        model=model,
                        generation=generation,
                        feedback_history=feedback_history,
                    ))
                finally:
                    loop.close()
            except Exception as exc:
                logger.error("Mutation failed gen %d: %s", generation, exc)
                _emit(loop_id, {
                    "step": "error",
                    "generation": generation,
                    "message": f"Mutation failed: {exc}",
                    "done": generation == max_generations,
                })
                break

            gen_record["version_name"] = mutation.version_name
            gen_record["changes_summary"] = mutation.changes_summary
            gen_record["mutation_success"] = mutation.success

            if not mutation.success:
                _emit(loop_id, {
                    "step": "mutation_failed",
                    "generation": generation,
                    "message": f"Mutation invalid: {'; '.join(mutation.validation_errors)}",
                    "done": generation == max_generations,
                })
                generations.append(gen_record)
                continue

            # ── Step 5: Run backtest on mutated strategy ───────────────────────
            _emit(loop_id, {
                "step": "backtesting",
                "generation": generation,
                "message": f"Running backtest on {mutation.version_name}…",
            })

            new_run_id = start_backtest(
                strategy=mutation.version_name,
                pairs=pairs,
                timeframe=timeframe,
                timerange=timerange,
                exchange=exchange,
                strategy_params={},
            )
            gen_record["new_run_id"] = new_run_id

            # ── Step 6: Wait for backtest ─────────────────────────────────────
            final_meta = wait_for_run(new_run_id, timeout_s=600)
            new_status = final_meta.get("status", "unknown")

            if new_status != "completed":
                _emit(loop_id, {
                    "step": "backtest_failed",
                    "generation": generation,
                    "message": f"Backtest {new_run_id} ended with status '{new_status}'.",
                    "done": generation == max_generations,
                })
                feedback_store.record(
                    strategy=strategy_name,
                    generation=generation,
                    changes_summary=mutation.changes_summary,
                    fitness_before=fitness_before.value,
                    fitness_after=0.0,
                    accepted=False,
                )
                generations.append(gen_record)
                continue

            # ── Step 7: Score new backtest ────────────────────────────────────
            new_results = load_run_results(new_run_id) or {}
            new_run_data = {**new_results, "strategy": mutation.version_name}
            fitness_after: FitnessScore = compute_fitness(new_run_data)
            gen_record["fitness_after"] = fitness_after.value
            gen_record["fitness_breakdown_after"] = fitness_after.breakdown

            delta = fitness_after.value - fitness_before.value
            accepted = fitness_after.value > fitness_before.value

            # ── Step 8: Record feedback ───────────────────────────────────────
            feedback_store.record(
                strategy=strategy_name,
                generation=generation,
                changes_summary=mutation.changes_summary,
                fitness_before=fitness_before.value,
                fitness_after=fitness_after.value,
                accepted=accepted,
            )

            gen_record["accepted"] = accepted
            gen_record["delta"] = round(delta, 2)

            _emit(loop_id, {
                "step": "comparing",
                "generation": generation,
                "fitness_before": fitness_before.value,
                "fitness_after": fitness_after.value,
                "delta": f"{delta:+.1f}",
                "accepted": accepted,
                "version_name": mutation.version_name,
                "changes_summary": mutation.changes_summary,
                "new_run_id": new_run_id,
            })

            # ── Step 9: Advance if improved ───────────────────────────────────
            if accepted:
                current_run_id = new_run_id
                if fitness_after.value > best_fitness:
                    best_fitness = fitness_after.value
                    best_version = mutation.version_name

            generations.append(gen_record)
            _update_session(
                loop_id,
                generations_completed=generation,
                best_fitness=best_fitness,
                best_version=best_version,
            )

            # Persist after each generation
            session_snapshot = get_evolution_status(loop_id) or {}
            _save_run_log(loop_id, session_snapshot, generations)

        # ── Done ──────────────────────────────────────────────────────────────
        _emit(loop_id, {
            "step": "done",
            "generation": max_generations,
            "best_version": best_version,
            "best_fitness": round(best_fitness, 2),
            "done": True,
        })
        _update_session(loop_id, status="completed", best_fitness=best_fitness, best_version=best_version)

    except Exception as exc:
        logger.error("Evolution worker crashed (loop_id=%s): %s", loop_id, exc)
        _emit(loop_id, {"step": "error", "message": str(exc), "done": True})
        _update_session(loop_id, status="failed")

    finally:
        session_snapshot = get_evolution_status(loop_id) or {}
        _save_run_log(loop_id, session_snapshot, generations)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _resolve_strategy_names(meta: dict[str, Any]) -> tuple[str, str]:
    base_strategy = meta.get("base_strategy") or meta.get("strategy_class") or meta.get("strategy") or ""
    source_strategy = meta.get("strategy_source_name") or meta.get("strategy") or base_strategy
    return base_strategy, source_strategy


def _load_strategy_source(strategy_name: str) -> str:
    strategy_py = STRATEGIES_DIR / f"{strategy_name}.py"
    return strategy_py.read_text(encoding="utf-8")


def _weakest_populated_regime(analysis: dict) -> tuple[str | None, dict | None]:
    per_regime = ((analysis.get("regime_analysis") or {}).get("per_regime_performance") or {})
    populated = {
        regime: stats
        for regime, stats in per_regime.items()
        if (stats or {}).get("trade_count", 0) >= 10
    }
    if not populated:
        return None, None
    weakest_regime = min(populated, key=lambda regime: float(populated[regime].get("avg_profit", 0.0)))
    return weakest_regime, populated[weakest_regime]


def _evaluate_regime_robustness(base_analysis: dict, candidate_analysis: dict) -> tuple[bool, str | None, dict]:
    weakest_regime, weakest_stats = _weakest_populated_regime(base_analysis)
    if weakest_regime is None or weakest_stats is None:
        return True, None, {"mode": "neutral", "reason": "insufficient_regime_data"}

    candidate_stats = (
        ((candidate_analysis.get("regime_analysis") or {}).get("per_regime_performance") or {}).get(weakest_regime)
        or {}
    )
    if candidate_stats.get("trade_count", 0) < 10:
        return False, f"candidate lacks enough trades in weakest regime '{weakest_regime}'", {
            "mode": "strict",
            "weakest_regime": weakest_regime,
            "before": weakest_stats,
            "after": candidate_stats,
        }

    before_avg_profit = float(weakest_stats.get("avg_profit", 0.0))
    after_avg_profit = float(candidate_stats.get("avg_profit", 0.0))
    before_win_rate = float(weakest_stats.get("win_rate", 0.0))
    after_win_rate = float(candidate_stats.get("win_rate", 0.0))

    if after_avg_profit < before_avg_profit:
        return False, f"avg profit worsened in weakest regime '{weakest_regime}'", {
            "mode": "strict",
            "weakest_regime": weakest_regime,
            "before": weakest_stats,
            "after": candidate_stats,
        }
    if after_win_rate < before_win_rate - 2.0:
        return False, f"win rate fell by more than 2 points in weakest regime '{weakest_regime}'", {
            "mode": "strict",
            "weakest_regime": weakest_regime,
            "before": weakest_stats,
            "after": candidate_stats,
        }
    return True, None, {
        "mode": "strict",
        "weakest_regime": weakest_regime,
        "before": weakest_stats,
        "after": candidate_stats,
    }


def _evolution_worker(
    run_id: str,
    goal_id: str | None,
    max_generations: int,
    provider: str,
    model: str | None,
    loop_id: str,
) -> None:
    from app.ai.evolution.version_manager import create_backtest_workspace
    from app.services.result_normalizer import normalize_backtest_result

    generations: list[dict] = []
    best_fitness = 0.0
    best_version: str | None = None
    current_run_id = run_id

    try:
        initial_meta = load_run_meta(current_run_id)
        if not initial_meta:
            _emit(loop_id, {"step": "error", "message": f"Run '{current_run_id}' not found.", "done": True})
            _update_session(loop_id, status="failed")
            return

        base_strategy, current_source_name = _resolve_strategy_names(initial_meta)
        pairs: list[str] = initial_meta.get("pairs", [])
        timeframe: str = initial_meta.get("timeframe", "5m")
        exchange: str = initial_meta.get("exchange") or "binance"
        timerange: str | None = initial_meta.get("timerange")

        if not base_strategy:
            _emit(loop_id, {"step": "error", "message": "No strategy name in run meta.", "done": True})
            _update_session(loop_id, status="failed")
            return

        _update_session(loop_id, strategy=base_strategy, status="running")

        for generation in range(1, max_generations + 1):
            gen_record: dict[str, Any] = {
                "generation": generation,
                "base_run_id": current_run_id,
                "base_strategy": base_strategy,
                "source_strategy": current_source_name,
            }

            _emit(
                loop_id,
                {
                    "step": "analyzing",
                    "generation": generation,
                    "message": f"Running deep analysis on {current_source_name}...",
                },
            )

            base_results = load_run_results(current_run_id)
            if not base_results:
                gen_record["error"] = "Base run results not found."
                generations.append(gen_record)
                _emit(loop_id, {"step": "error", "generation": generation, "message": gen_record["error"], "done": True})
                _update_session(loop_id, status="failed")
                break

            base_run_data = normalize_backtest_result({**base_results, "strategy": current_source_name})
            base_analysis = analyze(base_run_data, run_id=current_run_id)
            fitness_before = compute_fitness(base_run_data)
            gen_record["fitness_before"] = fitness_before.value
            gen_record["fitness_breakdown_before"] = fitness_before.breakdown

            if generation == 1:
                best_fitness = fitness_before.value
                if current_source_name != base_strategy:
                    best_version = current_source_name

            regime_info: dict[str, Any] = {}
            if pairs:
                try:
                    regime = _run_async(detect_regime(pairs[0], timeframe, exchange))
                    regime_info = {
                        "regime": regime.regime,
                        "trend_direction": regime.trend_direction,
                        "volatility_level": regime.volatility_level,
                        "confidence": regime.confidence,
                        "details": regime.details,
                    }
                except Exception as exc:
                    logger.debug("Regime detection failed: %s", exc)
            gen_record["market_regime"] = regime_info

            try:
                source_code = _load_strategy_source(current_source_name)
            except FileNotFoundError:
                gen_record["error"] = f"Strategy file {current_source_name}.py not found."
                generations.append(gen_record)
                _emit(loop_id, {"step": "error", "generation": generation, "message": gen_record["error"], "done": True})
                _update_session(loop_id, status="failed")
                break

            _emit(
                loop_id,
                {
                    "step": "mutating",
                    "generation": generation,
                    "message": f"AI editing strategy code for generation {generation}...",
                },
            )

            feedback_history = feedback_store.get_history(base_strategy)
            from app.ai.evolution.strategy_editor import mutate_strategy

            mutation = _run_async(
                mutate_strategy(
                    strategy_name=base_strategy,
                    source_code=source_code,
                    analysis=base_analysis,
                    fitness=fitness_before,
                    goal_id=goal_id,
                    provider=provider,
                    model=model,
                    generation=generation,
                    feedback_history=feedback_history,
                    regime_context=regime_info,
                )
            )
            gen_record["version_name"] = mutation.version_name
            gen_record["changes_summary"] = mutation.changes_summary
            gen_record["mutation_success"] = mutation.success

            if not mutation.success:
                gen_record["validation_errors"] = list(mutation.validation_errors)
                generations.append(gen_record)
                _emit(
                    loop_id,
                    {
                        "step": "mutation_failed",
                        "generation": generation,
                        "message": f"Mutation invalid: {'; '.join(mutation.validation_errors)}",
                        "done": False,
                    },
                )
                _update_session(loop_id, generations_completed=generation - 1, best_fitness=best_fitness, best_version=best_version)
                _save_run_log(loop_id, get_evolution_status(loop_id) or {}, generations)
                continue

            feedback_store.record_pending(
                strategy=base_strategy,
                generation=generation,
                changes_summary=mutation.changes_summary,
                fitness_before=fitness_before.value,
                version_name=mutation.version_name,
            )

            workspace = create_backtest_workspace(
                base_strategy_name=base_strategy,
                version_name=mutation.version_name,
                source=mutation.new_code,
                loop_id=loop_id,
                generation=generation,
            )
            gen_record["workspace"] = str(workspace)

            _emit(
                loop_id,
                {
                    "step": "backtesting",
                    "generation": generation,
                    "message": f"Running backtest on {mutation.version_name}...",
                },
            )

            new_run_id = start_backtest(
                strategy=base_strategy,
                strategy_label=mutation.version_name,
                strategy_path=str(workspace),
                pairs=pairs,
                timeframe=timeframe,
                timerange=timerange,
                exchange=exchange,
                strategy_params={},
                extra_meta={
                    "base_strategy": base_strategy,
                    "strategy_source_name": mutation.version_name,
                    "strategy_version": mutation.version_name,
                    "evolution_loop_id": loop_id,
                    "evolution_generation": generation,
                },
            )
            gen_record["new_run_id"] = new_run_id

            final_meta = wait_for_run(new_run_id, timeout_s=600)
            if final_meta.get("status") != "completed":
                gen_record["accepted"] = False
                gen_record["rejection_reason"] = f"backtest ended with status '{final_meta.get('status', 'unknown')}'"
                generations.append(gen_record)
                feedback_store.record(
                    strategy=base_strategy,
                    generation=generation,
                    changes_summary=mutation.changes_summary,
                    fitness_before=fitness_before.value,
                    fitness_after=0.0,
                    accepted=False,
                    version_name=mutation.version_name,
                )
                _emit(
                    loop_id,
                    {
                        "step": "backtest_failed",
                        "generation": generation,
                        "message": f"Backtest {new_run_id} ended with status '{final_meta.get('status', 'unknown')}'.",
                    },
                )
                _update_session(loop_id, generations_completed=generation, best_fitness=best_fitness, best_version=best_version)
                _save_run_log(loop_id, get_evolution_status(loop_id) or {}, generations)
                continue

            candidate_source_name = final_meta.get("strategy_source_name") or mutation.version_name
            candidate_results = load_run_results(new_run_id) or {}
            candidate_run_data = normalize_backtest_result({**candidate_results, "strategy": candidate_source_name})
            candidate_analysis = analyze(candidate_run_data, run_id=new_run_id)
            fitness_after = compute_fitness(candidate_run_data)
            delta = round(fitness_after.value - fitness_before.value, 2)
            robustness_passed, rejection_reason, robustness_details = _evaluate_regime_robustness(
                base_analysis,
                candidate_analysis,
            )
            accepted = fitness_after.value > fitness_before.value and robustness_passed

            gen_record.update(
                {
                    "fitness_after": fitness_after.value,
                    "fitness_breakdown_after": fitness_after.breakdown,
                    "delta": delta,
                    "accepted": accepted,
                    "robustness_passed": robustness_passed,
                    "rejection_reason": rejection_reason,
                    "robustness_details": robustness_details,
                }
            )

            feedback_store.record(
                strategy=base_strategy,
                generation=generation,
                changes_summary=mutation.changes_summary,
                fitness_before=fitness_before.value,
                fitness_after=fitness_after.value,
                accepted=accepted,
                version_name=mutation.version_name,
            )

            _emit(
                loop_id,
                {
                    "step": "comparing",
                    "generation": generation,
                    "fitness_before": fitness_before.value,
                    "fitness_after": fitness_after.value,
                    "delta": f"{delta:+.2f}",
                    "accepted": accepted,
                    "version_name": mutation.version_name,
                    "changes_summary": mutation.changes_summary,
                    "new_run_id": new_run_id,
                    "robustness_passed": robustness_passed,
                    "rejection_reason": rejection_reason,
                },
            )

            if accepted:
                current_run_id = new_run_id
                current_source_name = mutation.version_name
                if fitness_after.value > best_fitness:
                    best_fitness = fitness_after.value
                    best_version = mutation.version_name

            generations.append(gen_record)
            _update_session(
                loop_id,
                generations_completed=generation,
                best_fitness=best_fitness,
                best_version=best_version,
                strategy=base_strategy,
            )
            _save_run_log(loop_id, get_evolution_status(loop_id) or {}, generations)

        _emit(
            loop_id,
            {
                "step": "done",
                "generation": max_generations,
                "best_version": best_version,
                "best_fitness": round(best_fitness, 2),
                "done": True,
            },
        )
        _update_session(loop_id, status="completed", best_fitness=best_fitness, best_version=best_version, strategy=base_strategy)

    except Exception as exc:
        logger.exception("Evolution worker crashed (loop_id=%s)", loop_id)
        _emit(loop_id, {"step": "error", "message": str(exc), "done": True})
        _update_session(loop_id, status="failed")
    finally:
        _save_run_log(loop_id, get_evolution_status(loop_id) or {}, generations)
