# Task: Strategy Evolution Engine — Backend

## Goal
Build the autonomous closed-loop system:

```
Backtest → Deep Analysis → AI Diagnose → AI Edit Code → Re-run Backtest → Compare → Repeat
```

The engine is non-blocking: every step runs async in the background and progress is streamed to the frontend via SSE. Each generation is saved so the user can inspect, accept, or reject any version.

---

## New directory: app/ai/evolution/

### app/ai/evolution/__init__.py
Re-exports: `start_evolution`, `get_evolution_status`, `list_evolution_runs`

### app/ai/evolution/fitness.py
Scoring function that converts a backtest result into a single "fitness" scalar (0–100). Weights:
- profit_factor × 20 (cap at 2.0 → 20 pts)
- sharpe_ratio × 15 (cap at 2.0 → 15 pts)
- -max_drawdown / 2 (lower is better; 0 drawdown = 25 pts, 50% drawdown = 0)
- win_rate × 0.2 (max 20 pts)
- total_trades bonus: log10(n_trades) × 5 (rewards enough data)

Returns `FitnessScore(value: float, breakdown: dict)`. Returns 0 for insufficient data (< 20 trades).

### app/ai/evolution/strategy_editor.py
Reads a strategy `.py` file, sends it to AI with a structured mutation prompt, validates the returned code (AST parse), writes a new versioned file.

Key function:
```python
async def mutate_strategy(
    strategy_name: str,          # e.g. "MultiMa"
    source_code: str,            # current .py source
    analysis: dict,              # deep_analysis.analyze() output
    fitness: FitnessScore,
    goal_id: str | None,         # "lower_drawdown" etc.
    provider: str,
    model: str,
    generation: int,
    feedback_history: list[dict],  # past mutations that worked/failed
) -> MutationResult
```

`MutationResult`:
- `success: bool`
- `new_code: str` — the mutated Python source
- `version_name: str` — e.g. "MultiMa_evo_g2"
- `changes_summary: str` — what the AI changed and why
- `validation_errors: list[str]`

Mutation prompt structure (sent to code_gen role):
```
STRATEGY SOURCE:
{source_code}

BACKTEST DIAGNOSIS:
- Health score: {score}/100
- Primary weakness: {root_cause_diagnosis.primary_failure_label}
- Causal chain: {causal_chain}
- Fix priority: {fix_priority}
- Parameter recommendations: {param_recs}

GOAL: {goal_directive if goal_id else "maximize overall fitness"}

FEEDBACK FROM PREVIOUS GENERATIONS:
{feedback_history last 3 entries}

TASK: Mutate the strategy Python code to address the primary weakness.
Rules:
1. Output ONLY valid Python code inside ```python ... ``` fences
2. Keep the class name EXACTLY as {strategy_name}
3. Only change: IntParameter/DecimalParameter defaults, minimal_roi values, stoploss, trailing_stop settings, entry/exit indicator thresholds
4. Do NOT change: imports, class name, method signatures, timeframe, startup_candle_count
5. After the code block, write a 2-sentence "# CHANGES:" comment explaining what you changed
```

After the AI responds:
- Extract code block via regex
- AST-parse for syntax
- Check class name preserved
- Write to `user_data/strategies/{version_name}.py`
- Copy `{strategy_name}.json` → `{version_name}.json` (so param file is valid)
- Return MutationResult

### app/ai/evolution/version_manager.py
Manages versioned strategy files.

```python
def create_version(strategy_name: str, source: str, generation: int) -> str
    # Returns version_name e.g. "MultiMa_evo_g2"
    # Writes user_data/strategies/{version_name}.py

def list_versions(strategy_name: str) -> list[VersionInfo]
    # Scans strategies dir for *_evo_g*.py matching base name

def get_version_source(version_name: str) -> str | None

def delete_version(version_name: str) -> bool

def accept_version(version_name: str, base_strategy_name: str) -> bool
    # Copies version_name.py → base_strategy_name.py (user accepts a generation)
```

`VersionInfo`: `version_name`, `generation`, `base_strategy`, `created_at`, `fitness`, `run_id`

### app/ai/evolution/feedback_store.py
Stores what mutations worked/failed per strategy. Backed by `user_data/ai_evolution/{strategy}_feedback.json`.

```python
def record(strategy: str, generation: int, changes_summary: str, fitness_before: float, fitness_after: float, accepted: bool)
def get_history(strategy: str, limit: int = 10) -> list[dict]
    # Returns list of {generation, changes_summary, fitness_before, fitness_after, delta, accepted}
def get_winning_patterns(strategy: str) -> list[str]
    # Returns summaries of accepted mutations (delta > 0)
```

### app/ai/evolution/market_regime.py
Detects current market regime from OHLCV data.

```python
async def detect_regime(pair: str, timeframe: str) -> RegimeResult
```

Uses existing `ohlcv_loader.py` to load the most recent 200 candles for the pair.

Computes:
- **Trend**: 50-period SMA slope (positive/negative/flat)
- **Volatility**: ATR(14) / price ratio → low/medium/high
- **Regime**: one of `bull_trending`, `bear_trending`, `sideways_low_vol`, `sideways_high_vol`, `volatile`

`RegimeResult`: `regime: str`, `trend_direction: str`, `volatility_level: str`, `confidence: float`, `details: dict`

Used in evolution loop to add regime context to the AI prompt and to fitness scoring (penalize strategies that only work in one regime).

### app/ai/evolution/evolver.py
The orchestrator that runs the full loop.

```python
async def start_evolution(
    run_id: str,               # Starting backtest run to evolve from
    goal_id: str | None,       # e.g. "lower_drawdown"
    max_generations: int,      # default 3
    provider: str,
    model: str,
    loop_id: str,              # UUID for tracking this evolution session
) -> None:                     # runs in background thread
```

Loop:
```
1. Load backtest result from run_id (`app.services.results.result_service.parse_backtest_results`)
2. Run deep_analysis.analyze() → get analysis + fitness
3. Detect market regime for the strategy's pairs/timeframe
4. Read strategy source from user_data/strategies/{strategy}.py
5. Call strategy_editor.mutate_strategy() → new code + version_name
6. Save mutation to feedback_store (before fitness known)
7. Start new backtest via runner.start_backtest() → new_run_id
8. Wait for backtest to complete (poll every 5s, timeout 10 min)
9. Parse new backtest result → compute new fitness
10. Compare fitness: old vs new
11. Record in feedback_store (accepted = fitness_after > fitness_before)
12. Save generation result to evolution run log
13. Yield progress event at each step
14. If new fitness > old fitness: use new run_id as base for next generation
   Else: keep old code, try different mutation next generation
15. Repeat for max_generations
```

Progress events (streamed via SSE) now use the shared envelope from `app/ai/events.py`:
```json
{"event_type": "analysis_started", "status": "running", "stream": "evolution", "loop_id": "abc123", "cycle_index": 1, "payload": {"generation": 1, "message": "Running deep analysis..."}, "timestamp": "2026-04-06T12:00:00+00:00"}
{"event_type": "mutation_started", "status": "running", "stream": "evolution", "loop_id": "abc123", "cycle_index": 1, "payload": {"generation": 1, "message": "AI editing strategy code..."}, "timestamp": "2026-04-06T12:00:02+00:00"}
{"event_type": "backtest_started", "status": "running", "stream": "evolution", "loop_id": "abc123", "cycle_index": 1, "payload": {"generation": 1, "message": "Running backtest on MultiMa_evo_g1..."}, "timestamp": "2026-04-06T12:00:10+00:00"}
{"event_type": "comparison_done", "status": "ok", "stream": "evolution", "loop_id": "abc123", "cycle_index": 1, "payload": {"generation": 1, "fitness_before": 42.1, "fitness_after": 57.8, "delta": "+15.7", "accepted": true}, "timestamp": "2026-04-06T12:01:12+00:00"}
{"event_type": "loop_completed", "status": "completed", "stream": "evolution", "loop_id": "abc123", "cycle_index": 3, "payload": {"generation": 3, "best_version": "MultiMa_evo_g2", "best_fitness": 61.3}, "timestamp": "2026-04-06T12:05:00+00:00"}
```

Canonical envelope fields:
- `event_type`
- `status`
- `payload`
- `timestamp`
- `loop_id`
- `cycle_index`
- `stream`

Evolution run saved to `user_data/ai_evolution/{loop_id}.json`.

---

## New directory: app/ai/market/

### app/ai/market/__init__.py
Re-exports: `detect_regime`

### app/ai/market/regime_detector.py
Contains the `detect_regime` function (moved from `evolution/market_regime.py` for reuse).

---

## New API endpoints: app/routers/evolution.py

```
POST /evolution/start
  Body: {run_id, goal_id?, max_generations=3, provider, model}
  → {loop_id}  (immediately; evolution runs in background)

GET  /evolution/stream/{loop_id}
  SSE stream → progress events until done

GET  /evolution/runs
  → list of evolution sessions {loop_id, strategy, started_at, status, generations_completed, best_fitness}

GET  /evolution/run/{loop_id}
  → full evolution run detail with all generations

GET  /evolution/versions/{strategy}
  → list of evolved versions for a strategy

POST /evolution/accept/{loop_id}/{generation}
  → accepts a generation: copies version_name.py over base strategy

DELETE /evolution/version/{version_name}
  → deletes an evolved version file
```

---

## Modified files

### app/core/config.py
Add: `AI_EVOLUTION_DIR = BASE_DIR / "ai_evolution"` + mkdir

### app/main.py
Add: `from app.routers import evolution` + `app.include_router(evolution.router)`

### app/services/runner.py
Add: `wait_for_run(run_id: str, timeout_s: int = 600) -> dict` — polls `load_run_meta` until status != "running", returns final meta.

---

## Dependencies
- No new packages needed: uses existing httpx, fastapi, asyncio

## Acceptance criteria
- `POST /evolution/start` with a valid run_id returns a loop_id within 1 second
- `GET /evolution/stream/{loop_id}` streams JSON events without crashing
- After one full generation, `GET /evolution/versions/{strategy}` shows the new version
- `POST /evolution/accept/{loop_id}/1` overwrites the base strategy file safely
- App starts without import errors
