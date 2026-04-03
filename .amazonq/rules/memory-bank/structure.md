# Project Structure — 4tie

## Directory Layout

```
SameGrossNetframework/
├── app/                        # FastAPI backend application
│   ├── main.py                 # App entry point, router registration, static mounts
│   ├── ai/                     # AI subsystem
│   │   ├── agents/             # Agent definitions (reserved/future)
│   │   ├── memory/             # Conversation persistence (conversations.py)
│   │   ├── models/             # AI model clients and registry
│   │   │   ├── openrouter_client.py  # HTTP client for OpenRouter API (streaming)
│   │   │   ├── ollama_client.py      # Ollama local model client
│   │   │   └── registry.py           # Model registry, role-based model selection
│   │   ├── pipelines/          # Multi-model pipeline engine
│   │   │   ├── orchestrator.py # Pipeline dispatcher (simple/analysis/debate/code/structured/tool)
│   │   │   └── classifier.py   # Task classifier — routes to pipeline type
│   │   ├── prompts/            # System prompt constants (reserved)
│   │   ├── tools/              # AI tools
│   │   │   └── deep_analysis.py # Deep backtest analysis with health scoring
│   │   ├── conversation_store.py  # (legacy) conversation file I/O
│   │   └── orchestrator.py     # (legacy) original orchestrator
│   ├── core/                   # Shared infrastructure
│   │   ├── config.py           # Path constants, env var resolution, dir creation
│   │   ├── processes.py        # Process lifecycle: start, status, logs (in-memory)
│   │   └── storage.py          # Shared JSON read/write helpers (_ensure, read_json, write_json)
│   ├── routers/                # FastAPI route handlers (one file per domain)
│   │   ├── ai_chat.py          # /ai/* endpoints: chat (SSE), conversations, providers, analyze
│   │   ├── backtest.py         # /run, /runs, /config, /pairs, /ohlcv, /indicators, /download-data
│   │   ├── strategies.py       # /strategies/* endpoints
│   │   ├── presets.py          # /presets/* endpoints
│   │   ├── compare.py          # /compare/* endpoints
│   │   └── hyperopt.py         # /hyperopt/* endpoints
│   ├── schemas/                # Pydantic request/response models
│   │   ├── backtest.py         # BacktestRequest, DownloadDataRequest, ConfigPatchRequest, etc.
│   │   └── ai_chat.py          # ChatRequest, ChatResponse, ConversationSummary, ChatMessage
│   └── services/               # Business logic layer
│       ├── runner.py           # start_backtest(), start_download() — spawns subprocesses
│       ├── storage.py          # Run result I/O: load_run_meta, load_run_results, list_runs
│       ├── command_builder.py  # Builds freqtrade CLI command strings
│       ├── data_coverage.py    # Checks local data coverage for pairs/timeframes
│       ├── hyperopt_parser.py  # Parses .fthypt hyperopt result files
│       ├── hyperopt_storage.py # Hyperopt result persistence
│       ├── indicator_calculator.py  # Calculates technical indicators on OHLCV data
│       ├── ohlcv_loader.py     # Loads OHLCV data from local JSON/feather files
│       ├── result_parser.py    # Parses FreqTrade backtest result JSON
│       └── strategy_scanner.py # Scans strategies dir, reads .py and .json sidecar files
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
│   ├── ai_conversations/       # Chat conversation JSON files
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
                   AI Router → Pipeline Orchestrator → AI Model Clients (OpenRouter/Ollama)
```

### AI Pipeline Architecture
The AI subsystem uses a classifier-first multi-model pipeline:
1. `classifier.py` — classifies the task into a pipeline type and complexity level
2. `orchestrator.py` — dispatches to the appropriate pipeline runner
3. Pipeline types: `simple` (1 model), `analysis` (reasoner→composer), `debate` (2 analysts→judge→composer), `code` (code_gen→validator→explainer), `structured` (JSON output), `tool` (tool_caller→reasoner→composer)
4. All pipelines support both batch (`run_*`) and streaming (`stream_*`) variants

### Data Storage Pattern
- All persistent data lives under `user_data/` (configurable via `USER_DATA_DIR` env var)
- Backtest runs: `user_data/backtest_results/{run_id}/` with `meta.json` and `parsed_results.json`
- Conversations: `user_data/ai_conversations/{uuid}.json`
- Strategy params: `user_data/strategies/{StrategyName}.json` (sidecar to `.py` file)
- Config: `user_data/config.json` (FreqTrade config), `user_data/last_config.json` (last UI config)

## Architectural Patterns

- **Router-per-domain**: Each feature area has its own router file (`backtest.py`, `ai_chat.py`, etc.)
- **Service layer separation**: Routers delegate to `app/services/` for business logic
- **Schema-first validation**: All request bodies use Pydantic models in `app/schemas/`
- **SSE streaming**: AI chat uses Server-Sent Events for real-time streaming responses
- **SPA frontend**: Single HTML shell (`base.html`) with hash-based routing; pages are HTML fragments
- **Subprocess isolation**: FreqTrade runs as a child process; status tracked in-memory via `app/core/processes.py`
- **Atomic file writes**: Config writes use `tempfile.mkstemp` + `os.replace` for atomicity
