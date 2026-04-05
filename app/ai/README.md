## AI Folder Structure

Canonical modules:

- `pipelines/`: classifier + orchestrator execution paths (primary runtime entrypoint)
- `models/`: provider clients, dispatch, registry
- `prompts/`: system prompts and goal directives
- `tools/`: analytical utilities (for example deep analysis)
- `evolution/`: strategy evolution loop
- `memory/`: thread and conversation storage

Compatibility:

- `orchestrator.py` is a thin shim that re-exports `pipelines.orchestrator` for legacy imports.

Routing and model selection:

- `model_routing_policy.py`: role policy, weights, hard filters
- `model_router.py`: deterministic role-based model selection
- `model_metrics_store.py`: persistent model performance observations

