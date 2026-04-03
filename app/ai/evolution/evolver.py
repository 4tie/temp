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

from app.core.config import AI_EVOLUTION_DIR, STRATEGIES_DIR
from app.core.storage import read_json, write_json
from app.services.storage import load_run_meta, load_run_results
from app.services.runner import start_backtest, wait_for_run
from app.ai.tools.deep_analysis import analyze
from app.ai.evolution.fitness import compute_fitness, FitnessScore
from app.ai.evolution.strategy_editor import mutate_strategy
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

def _emit(loop_id: str, event: dict) -> None:
    with _state_lock:
        if loop_id not in _evolution_events:
            _evolution_events[loop_id] = []
        _evolution_events[loop_id].append(event)


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
