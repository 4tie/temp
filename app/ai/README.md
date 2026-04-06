## AI Folder Structure

Canonical runtime surfaces:

- `events.py`: shared loop/evolution event schema. All SSE emitters should use `serialize_ai_loop_event()` or `serialize_evolution_event()`.
- `pipelines/`: classifier + orchestrator execution paths. This is the primary AI runtime entrypoint.
- `models/`: provider clients, provider dispatch, and model registry.
- `prompts/`: system prompts and goal directives.
- `tools/`: deterministic analysis helpers such as `deep_analysis.py`.
- `memory/`: conversation and thread persistence.
- `evolution/`: autonomous mutation/evolution loop.
- `market/`: reusable market-regime helpers used by evolution.
- `context_builder.py`: builds AI context bundles from runs, metrics, and strategy state.

Canonical HTTP split:

- `app/routers/ai_chat/`: request parsing plus HTTP/SSE responses only.
- `app/services/ai_chat/`: thread, provider, apply-code, loop, and report business logic.

Shared contracts used by AI features:

- `app/services/results/metric_registry.py`: single source of truth for metrics used by compare, results UI, AI context, and loop reports.
- `app/services/strategies/strategy_snapshot_service.py`: `get_strategy_editable_context(strategy_name)` returns source path, sidecar path, extracted params, current values, and validation flags.
- Strategy semantics:
  - source of code = `user_data/strategies/*.py`
  - editable runtime knobs = sidecar `*.json`
  - UI metadata = AST-extracted parameter metadata normalized by `strategy_param_metadata_service.py`

Routing and model selection:

- `model_routing_policy.py`: role policy, weights, and hard filters
- `model_router.py`: deterministic role-based model selection
- `model_metrics_store.py`: persistent model performance observations

Notes:

- Mounted AI API lives in `app/routers/ai_chat/` and is registered by `app/main.py`.
- Conversation migration support remains in `app.ai.memory.threads`, which can import old JSON records from `user_data/ai_conversations/`.
