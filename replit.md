# 4tie — FreqTrade Strategy Management

## Overview
Web-based management interface for the FreqTrade algorithmic trading framework. Built with FastAPI (backend) and a JavaScript SPA (frontend).

## Architecture

### Backend (FastAPI)
- `app/main.py` — Entry point, mounts static files, includes all routers
- `app/core/config.py` — Paths to user_data directories, port config
- `app/core/storage.py` — Shared JSON read/write helpers
- `app/routers/` — API endpoint modules:
  - `backtest.py` — Backtest runs, data download, config
  - `strategies.py` — Strategy listing and params
  - `presets.py` — Saved backtest presets
  - `compare.py` — Multi-run comparison
  - `hyperopt.py` — Hyperopt runs
  - `ai.py` — AI chat, conversations, providers, deep analysis (SSE streaming)
- `app/services/` — Business logic (runner, storage, data_coverage, etc.)
- `app/ai/` — AI module:
  - `openrouter_client.py` — HTTP client for OpenRouter + Ollama (streaming)
  - `ai_registry.py` — Model registry, role-based model selection
  - `ai_classifier.py` — Task classifier (routes to pipeline type)
  - `orchestrator.py` — Multi-model pipeline engine (simple/analysis/debate/code)
  - `conversation_store.py` — File-based conversation persistence
  - `deep_analysis.py` — Deep backtest analysis engine with health scoring

### Frontend (Vanilla JS SPA)
- `templates/layouts/base.html` — Single HTML shell, all pages included
- `templates/pages/` — Per-page HTML fragments
- `static/js/core/` — DOM helpers, API client, app router, auth
- `static/js/pages/` — Page controllers (one per page):
  - `ai-diagnosis.js` — Full AI chat UI (streaming, sidebar, provider toggle)
- `static/css/` — Modular CSS (base, layout, components, utilities, per-page)
  - `pages/ai-chat.css` — AI chat layout, messages, deep analysis panel

## Data Storage
- `user_data/` — FreqTrade data directory
  - `backtest_results/` — Per-run directories with meta.json + parsed_results.json
  - `ai_conversations/` — Chat conversation JSON files (persisted)
  - `ai_pipeline_logs/` — AI pipeline execution logs

## Environment Variables
- `OPENROUTER_API_KEY` — Required for OpenRouter AI provider
- `OLLAMA_BASE_URL` — Ollama server URL (default: http://localhost:11434)
- `BACKTEST_API_PORT` — Server port (default: 5000)
- `USER_DATA_DIR` — Override user_data directory path
- `FREQTRADE_EXCHANGE` — Default exchange (default: binance)

## Key Features
- Run FreqTrade backtests and hyperopt from the web UI
- Strategy Lab for comparing and managing strategies
- AI Diagnosis: dark-themed chat with provider/model picker, streaming responses, conversation history, deep analysis panel
- Results viewer with charts and trade details
- Jobs monitor for active processes

## AI Chat System (Task 16)
The AI Diagnosis page (`#ai-diagnosis`) renders a full two-column chat interface:
- **Sidebar**: Conversation list loaded from `/ai/conversations`, new chat button, delete per item
- **Header**: Provider toggle (Ollama/OpenRouter), model dropdown (from `/ai/providers`), goal selector
- **Context bar**: Inject latest backtest button, shows active run badge, clear link
- **Message thread**: Role-labelled bubbles with pipeline badges and markdown rendering
- **Input area**: Auto-resize textarea, send/stop buttons, streaming status
- **Deep Analysis panel**: Right drawer with health score ring, strengths/weaknesses, parameter recommendations

## Running
```bash
python run.py
```
Server starts on port 5000 with hot-reload watching app/, static/, templates/.
