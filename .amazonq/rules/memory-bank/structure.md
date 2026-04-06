# Project Structure — 4tie

## Directory Layout

```
SameGrossNetframework/
├── app/                        # FastAPI backend application
│   ├── main.py                 # App entry point, router registration, static mounts
│   ├── ai/                     # AI subsystem
│   │   ├── events.py           # Canonical loop/evolution event schema + SSE serializer
│   │   ├── context_builder.py  # Builds AI context bundles from runs + strategy state
│   │   ├── goals.py            # Goal registry / normalization
│   │   ├── agents/             # Agent definitions (reserved/future)
│   │   ├── memory/             # Conversation/thread persistence
│   │   │   ├── conversations.py
│   │   │   └── threads.py
│   │   ├── models/             # AI model clients and registry
│   │   │   ├── openrouter_client.py  # HTTP client for OpenRouter API (streaming)
│   │   │   ├── ollama_client.py      # Ollama local model client
│   │   │   ├── provider_dispatch.py  # Provider abstraction
│   │   │   └── registry.py           # Model registry, role-based model selection
│   │   ├── pipelines/          # Multi-model pipeline engine
│   │   │   ├── orchestrator.py # Pipeline dispatcher (simple/analysis/debate/code/structured/tool)
│   │   │   └── classifier.py   # Task classifier — routes to pipeline type
│   │   ├── prompts/            # System prompts and goal directives
│   │   ├── tools/              # AI tools
│   │   │   └── deep_analysis.py # Deep backtest analysis with health scoring
│   │   ├── evolution/          # Autonomous strategy evolution loop
│   │   ├── market/             # Market regime detection helpers
│   │   └── model_metrics_store.py # Persistent model-router metrics
│   ├── core/                   # Shared infrastructure
│   │   ├── config.py           # Source of truth: env vars, dirs, run/report filenames
│   │   ├── json_io.py          # Shared JSON read/write helpers
│   │   └── processes.py        # Process lifecycle: start, status, logs (in-memory)
│   ├── routers/                # FastAPI route handlers
│   │   ├── ai_chat/            # Mounted /ai router package
│   │   │   ├── __init__.py
│   │   │   ├── chat_stream.py  # /ai/chat, /ai/analyze/{run_id}, /ai/pipeline-logs
│   │   │   ├── providers.py    # /ai/providers
│   │   │   ├── threads.py      # /ai/threads/* + conversation compatibility aliases
│   │   │   ├── apply_code.py   # /ai/chat/apply-code
│   │   │   ├── loop_sessions.py # /ai/loop/* control + stream
│   │   │   └── reports.py      # /ai/loop/{loop_id}/report*
│   │   ├── backtest.py         # /run, /runs, /config, /pairs, /ohlcv, /download-data
│   │   ├── strategies.py       # /strategies/* endpoints
│   │   ├── presets.py          # /presets/* endpoints
│   │   ├── compare.py          # /compare/* endpoints
│   │   ├── hyperopt.py         # /hyperopt/* endpoints
│   │   ├── evolution.py        # /evolution/* endpoints
│   │   └── settings.py         # /settings/* endpoints
│   ├── schemas/                # Pydantic request/response models
│   │   ├── backtest.py         # BacktestRequest, DownloadDataRequest, ConfigPatchRequest, etc.
│   │   └── ai_chat.py          # ChatRequest, thread/apply-code request models
│   └── services/               # Business logic layer
│       ├── ai_chat/            # AI chat business logic extracted from router layer
│       │   ├── provider_service.py
│       │   ├── thread_service.py
│       │   ├── apply_code_service.py
│       │   ├── loop_service.py
│       │   ├── loop_report_service.py
│       │   └── stream_event_service.py
│       ├── runs/               # Shared run framework
│       │   ├── base_run_service.py
│       │   ├── run_metadata_service.py
│       │   ├── run_process_service.py
│       │   ├── run_log_service.py
│       │   ├── backtest_run_service.py
│       │   └── hyperopt_run_service.py
│       ├── results/            # Canonical backtest result parsing/normalization
│       │   ├── result_service.py
│       │   ├── raw_loader.py
│       │   ├── raw_extractors.py
│       │   ├── payload_detector.py
│       │   ├── overview_builder.py
│       │   ├── trade_normalizer.py
│       │   ├── risk_normalizer.py
│       │   ├── summary_normalizer.py
│       │   ├── schema_keys.py
│       │   ├── empty_result_factory.py
│       │   ├── comparison_metrics.py
│       │   └── metric_registry.py
│       ├── strategies/         # Canonical strategy semantics contract
│       │   ├── strategy_source_service.py
│       │   ├── strategy_sidecar_service.py
│       │   ├── strategy_param_metadata_service.py
│       │   ├── strategy_validation_service.py
│       │   └── strategy_snapshot_service.py
│       ├── runner.py           # Legacy entrypoint wrapping run services
│       ├── storage.py          # Domain-level run storage/load/list service
│       ├── execution_context_service.py # Shared config/pair/timerange helpers
│       ├── command_builder.py  # Builds freqtrade CLI command strings
│       ├── data_coverage.py    # Checks local data coverage for pairs/timeframes
│       ├── hyperopt_parser.py  # Parses .fthypt hyperopt result files
│       ├── hyperopt_storage.py # Hyperopt result persistence
│       ├── indicator_calculator.py  # Calculates technical indicators on OHLCV data
│       └── ohlcv_loader.py     # Loads OHLCV data from local JSON/feather files
├── static/                     # Frontend static assets
│   ├── css/
│   │   ├── base.css            # CSS reset and root variables
│   │   ├── layout.css          # Page layout (sidebar, main, topbar)
│   │   ├── components.css      # Reusable UI components
│   │   ├── utilities.css       # Utility classes
│   │   └── pages/              # Per-page CSS overrides (ai-chat.css, etc.)
│   └── js/
│       ├── core/               # Shared JS infrastructure
│       │   ├── api.js          # Fetch wrapper, SSE client
│       │   ├── router.js       # Hash-based SPA router
│       │   └── dom.js          # DOM helpers
│       ├── pages/              # Page controllers (one per page)
│       │   └── ai-diagnosis.js # Full AI chat UI controller
│       ├── components/         # Reusable JS components
│       └── utils/              # Utility functions
├── templates/                  # Jinja2 HTML templates
│   ├── layouts/
│   │   └── base.html           # Single HTML shell — all pages included here
│   ├── pages/                  # Per-page HTML fragments
│   │   ├── ai-diagnosis/
│   │   ├── backtesting/
│   │   ├── dashboard/
│   │   ├── hyperopt/
│   │   ├── jobs/
│   │   ├── results/
│   │   ├── settings/
│   │   └── strategy-lab/
│   └── partials/               # Shared HTML partials
│       ├── sidebar.html
│       ├── statusbar.html
│       └── topbar.html
├── user_data/                  # FreqTrade data directory (runtime)
│   ├── strategies/             # Strategy .py files + .json parameter sidecars
│   ├── backtest_results/       # Per-run dirs with meta.json + parsed_results.json
│   ├── hyperopt_results/       # .fthypt files + parsed run dirs
│   ├── data/                   # OHLCV market data (exchange subdirs)
│   ├── ai_threads/             # Canonical AI thread JSON files
│   ├── ai_conversations/       # Legacy chat conversation JSON files
│   ├── ai_evolution/           # Evolution session state + version metadata
│   ├── ai_loop_reports/        # Markdown AI loop reports
│   ├── ai_pipeline_logs/       # Pipeline execution traces
│   ├── config.json             # FreqTrade main config
│   └── presets.json            # Saved backtest presets
├── scripts/
│   ├── migrate_strategy_json.py  # One-off migration script
│   └── post-merge.sh           # Post-merge setup hook
├── requirements.txt            # Python dependencies
├── run.py                      # Dev server launcher (uvicorn with reload)
└── replit.md                   # Project documentation / architecture notes
```

## Core Components and Relationships

### Request Flow
```
Browser → FastAPI Router → Service Layer → FreqTrade subprocess / File I/O
                        ↓
             AI Router Package → Pipeline Orchestrator → AI Model Clients (OpenRouter/Ollama)
```

### AI Pipeline Architecture
The AI subsystem uses a classifier-first multi-model pipeline:
1. `classifier.py` — classifies the task into a pipeline type and complexity level
2. `orchestrator.py` — dispatches to the appropriate pipeline runner
3. Pipeline types: `simple` (1 model), `analysis` (reasoner→composer), `debate` (2 analysts→judge→composer), `code` (code_gen→validator→explainer), `structured` (JSON output), `tool` (tool_caller→reasoner→composer)
4. All pipelines support both batch (`run_*`) and streaming (`stream_*`) variants

### Data Storage Pattern
- All persistent data lives under `USER_DATA_ROOT` from `app/core/config.py` (default `./user_data`, override via `USER_DATA_DIR`)
- Backtest runs: `user_data/backtest_results/{run_id}/` with `meta.json` and `parsed_results.json`
- Hyperopt runs: `user_data/hyperopt_results/runs/{run_id}/`
- Threads: `user_data/ai_threads/{thread_id}.json` (`ai_conversations/` is legacy compatibility storage)
- Evolution sessions: `user_data/ai_evolution/{loop_id}.json`
- AI loop reports: `user_data/ai_loop_reports/{loop_id}.md`
- Strategy params: `user_data/strategies/{StrategyName}.json` (sidecar to `.py` file)
- Config: `user_data/config.json` (FreqTrade config), `user_data/last_config.json` (last UI config)

## Architectural Patterns

- **Config as source of truth**: `app/core/config.py` owns host, port, root dirs, result dirs, report dirs, and canonical filenames
- **Router-per-domain or router-package**: most feature areas use one router file; AI chat uses the `app/routers/ai_chat/` package
- **Service layer separation**: Routers delegate to `app/services/` for business logic
- **Shared run framework**: backtest and hyperopt share lifecycle logic via `app/services/runs/`
- **Result registry and normalizers**: result parsing lives in `app/services/results/`; metric definitions live in `metric_registry.py`
- **Strategy semantics contract**: routers call `get_strategy_editable_context()` instead of merging `.py`, sidecar `.json`, and AST metadata ad hoc
- **Schema-first validation**: All request bodies use Pydantic models in `app/schemas/`
- **Shared SSE event envelope**: AI loop and evolution streams use `app/ai/events.py`
- **SPA frontend**: Single HTML shell (`base.html`) with hash-based routing; pages are HTML fragments
- **Subprocess isolation**: FreqTrade runs as a child process; status tracked in-memory via `app/core/processes.py`
- **Atomic file writes**: Config writes use `tempfile.mkstemp` + `os.replace` for atomicity
