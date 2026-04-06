# Task: AI Backend Foundation

## Goal
Wire up the full AI backend for the 4tie app: OpenRouter (free-models-only) client, Ollama client, model registry, AI classifier, multi-step pipeline orchestrator, deep backtest analysis engine, and REST/SSE chat endpoints.

## Status
Completed. This document now tracks the canonical structure after the follow-up refactors. Do not use the older flat AI module layout or the pre-split single-file storage/router layout as implementation guidance.

## Canonical files / modules

### Core JSON I/O
- `app/core/json_io.py` — low-level JSON helpers (`read_json`, `write_json`, `ensure_dir`)
- `app/core/json_store.py` — compatibility re-export for legacy imports

### AI runtime
- `app/ai/models/openrouter_client.py` — OpenRouter client
- `app/ai/models/ollama_client.py` — Ollama client
- `app/ai/models/registry.py` — model registry and role selection
- `app/ai/pipelines/classifier.py` — task classifier
- `app/ai/pipelines/orchestrator.py` — multi-step pipeline engine
- `app/ai/tools/deep_analysis.py` — deterministic + AI-assisted deep analysis
- `app/ai/events.py` — shared loop/evolution event schema
- `app/ai/memory/conversations.py` and `app/ai/memory/threads.py` — canonical persistence modules

### API layer
- `app/schemas/ai_chat.py` — Pydantic models for chat/thread/apply-code requests
- `app/routers/ai_chat/__init__.py` — mounted `/ai` router package
- `app/routers/ai_chat/chat_stream.py` — `/ai/chat`, `/ai/analyze/{run_id}`, `/ai/pipeline-logs`
- `app/routers/ai_chat/providers.py` — `/ai/providers`
- `app/routers/ai_chat/threads.py` — `/ai/threads/*` plus `/ai/conversations/*` compatibility aliases

### Router-extracted AI services
- `app/services/ai_chat/provider_service.py`
- `app/services/ai_chat/thread_service.py`
- `app/services/ai_chat/stream_event_service.py`

### Storage
- `user_data/ai_threads/` — canonical thread storage
- `user_data/ai_conversations/` — legacy compatibility storage

### Modified files
- `app/core/config.py` — add `AI_CONVERSATIONS_DIR`, `AI_THREADS_DIR`, `AI_PIPELINE_LOGS_DIR`, and any other AI-owned dirs in one place
- `app/main.py` — `from app.routers import ai_chat` + `app.include_router(ai_chat.router)`

## Key constraints
- **OpenRouter: free models only** — always use `:free` suffix; `app.ai.models.registry` filters `fetch_free_models()` to only models whose id ends in `:free` or whose `pricing.prompt == "0"`
- **Ollama**: gracefully skips when not running (is_available() returns False); no error thrown to user
- **No blue colors** (not relevant for backend but note for log messages)
- **Secrets**: read `OPENROUTER_API_KEY` from env; if missing, OpenRouter is marked unavailable but app still starts; do not hardcode keys
- Imports in orchestrator/classifier/registry must match the package split:
  - `app.ai.pipelines.*`
  - `app.ai.models.*`
  - `app.core.json_io`

## Dependencies
- `httpx` (likely already installed via freqtrade); `pydantic` (already in use); `sse-starlette` for SSE streaming if not already in use — add via pip if absent

## Done when
- `GET /ai/providers` returns valid JSON with at least one provider section
- `POST /ai/chat` streams a response (even if OPENROUTER_API_KEY is not set it returns a clear error message not a 500)
- `POST /ai/analyze/{run_id}` returns the deep analysis dict for any existing run_id
- App starts without import errors
