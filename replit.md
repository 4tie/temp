# 4tie — FreqTrade Strategy Management

## Overview
Web-based management interface for the FreqTrade algorithmic trading framework. Built with FastAPI (backend) and a JavaScript SPA (frontend).

## Architecture

### Backend (FastAPI)
- `app/main.py` — Entry point, mounts static files, includes mounted routers
- `app/core/config.py` — Source of truth for host, port, `user_data` root, run/report dirs, and canonical filenames
- `app/core/json_io.py` — Low-level JSON read/write helpers
- `app/core/json_store.py` — Compatibility re-export for legacy JSON helper imports
- `app/core/processes.py` — In-memory active-process registry
- `app/routers/` — API endpoint modules/packages:
  - `backtest.py` — Backtest runs, data download, config, metrics registry endpoint
  - `hyperopt.py` — Hyperopt runs
  - `compare.py` — Multi-run comparison
  - `strategies.py` — Strategy source/params endpoints
  - `presets.py` — Saved backtest presets
  - `settings.py` — App/settings endpoints
  - `evolution.py` — Strategy evolution loop API + SSE stream
  - `ai_chat/` — Mounted `/ai` router package split into `chat_stream.py`, `providers.py`, `threads.py`, `apply_code.py`, `loop_sessions.py`, and `reports.py`
- `app/services/runs/` — Shared run lifecycle framework for backtest and hyperopt
- `app/services/results/` — Raw payload loading, normalization, overview/risk/trade shaping, and metric registry
- `app/services/strategies/` — Strategy source/sidecar/AST metadata contract via `get_strategy_editable_context()`
- `app/services/ai_chat/` — Thread, provider, apply-code, loop, and report business logic
- `app/ai/` — AI subsystem:
  - `events.py` — Canonical loop/evolution event schema and SSE serializer
  - `pipelines/` — Classifier + multi-model orchestrator
  - `models/` — OpenRouter/Ollama clients, provider dispatch, model registry
  - `tools/deep_analysis.py` — Deep backtest analysis engine with health scoring
  - `memory/` — Thread and conversation persistence
  - `evolution/` and `market/` — Evolution loop and market-regime helpers
  - `context_builder.py` — Builds run/strategy context bundles for AI flows
  - `orchestrator.py` and `conversation_store.py` — Legacy compatibility shims

### Frontend (Vanilla JS SPA)
- `templates/layouts/base.html` — Single HTML shell, all pages included
- `templates/pages/` — Per-page HTML fragments
- `static/js/core/` — DOM helpers, API client, app router, auth
- `static/js/pages/` — Page controllers (one per page):
  - `ai-diagnosis.js` — AI chat, loop, and evolution UI consumers
  - `results.js` — Results table that pulls metric definitions from the backend registry
- `static/css/` — Modular CSS (base, layout, components, utilities, per-page)
  - `pages/ai-chat.css` — AI chat layout, messages, deep analysis panel

## Data Storage
- `user_data/` — FreqTrade data directory
  - `backtest_results/` — Per-run directories with `meta.json`, `parsed_results.json`, and raw artifacts
  - `hyperopt_results/` — Hyperopt artifacts and parsed run directories
  - `strategies/` — Strategy `.py` files plus `.json` sidecars
  - `ai_threads/` — Canonical AI thread storage
  - `ai_conversations/` — Legacy conversation storage kept for compatibility
  - `ai_evolution/` — Evolution session state and generation records
  - `ai_loop_reports/` — Markdown loop reports
  - `ai_pipeline_logs/` — AI pipeline execution logs

## Environment Variables
- `BACKTEST_API_HOST` — Server host (default: `127.0.0.1`)
- `BACKTEST_API_PORT` — Server port (default: `5000`)
- `OPENROUTER_API_KEY` — Required for OpenRouter AI provider
- `OLLAMA_BASE_URL` — Ollama server URL (default: http://localhost:11434)
- `USER_DATA_DIR` — Override user_data directory path
- `FREQTRADE_EXCHANGE` — Default exchange (default: binance)
- `FREQTRADE_PYTHON` — Python executable used for FreqTrade subprocesses

## Key Features
- Run FreqTrade backtests and hyperopt from the web UI
- Strategy Lab for comparing and managing strategies
- AI Diagnosis: chat, thread history, provider/model picker, apply-code loop, loop reports, and deep analysis
- Results viewer with charts and trade details
- Jobs monitor for active processes

## AI System Notes
- Mounted AI API lives in `app/routers/ai_chat/` under `/ai/*`
- Canonical thread endpoints are `/ai/threads/*`; `/ai/conversations/*` remains as compatibility aliases
- AI loop and evolution streams use the shared envelope from `app/ai/events.py`
- Result metrics shown in compare/results/AI contexts come from `app/services/results/metric_registry.py`
- Strategy editing context comes from `app/services/strategies/strategy_snapshot_service.py`

## Running
```bash
python run.py
```
Server starts with `HOST`/`PORT` from `app/core/config.py` (default `127.0.0.1:5000`) and hot-reload watches `app/`, `static/`, and `templates/`.
