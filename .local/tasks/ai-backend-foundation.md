# Task: AI Backend Foundation

## Goal
Wire up the full AI backend for the 4tie app: OpenRouter (free-models-only) client, Ollama client, model registry, AI classifier, multi-step pipeline orchestrator, deep backtest analysis engine, and REST/SSE chat endpoints.

## Files to create / modify

### New files
- `app/core/storage.py` — thin shim with `write_json(path, data)` and `_ensure(path)` helpers (needed by the orchestrator as `from ..core.storage import write_json, _ensure`)
- `app/ai/__init__.py` — exports `chat_complete`, `stream_chat` (re-exports from whichever provider is configured)
- `app/ai/openrouter_client.py` — async httpx client; **free models only** (appends `:free` suffix when absent, rejects models without free tier); API key from `OPENROUTER_API_KEY` env var; list endpoint cached 5 min; retry 3× with exponential backoff; 429 handling with `Retry-After`; `chat_complete(messages, model) -> str` and `stream_chat(messages, model) -> AsyncGenerator[dict, None]`
- `app/ai/ollama_client.py` — async httpx client for local Ollama at `OLLAMA_BASE_URL` (default `http://localhost:11434`); `is_available() -> bool`; `list_models() -> list[str]`; `chat_complete(messages, model) -> str`; `stream_chat(messages, model) -> AsyncGenerator[dict, None]`
- `app/ai/ai_registry.py` — `fetch_free_models() -> list[dict]` (OpenRouter free tier list + local Ollama models); `get_model_for_role(role, models, overrides) -> tuple[str, str]`; roles: `classifier`, `reasoner`, `code_gen`, `analyst_a`, `analyst_b`, `judge`, `composer`; prefers small fast models for classifier, larger for reasoner/judge
- `app/ai/ai_classifier.py` — copied from `attached_assets/ai_classifier_1775234112949.py`, imports adapted (`from .openrouter_client import chat_complete` instead of relative internal paths)
- `app/ai/ai_orchestrator.py` — copied from `attached_assets/ai_orchestrator_1775234112949.py` (1112 lines), imports adapted:  
  - `from ..core.storage import write_json, _ensure` stays as-is (core/storage.py shim handles it)  
  - `from .openrouter_client import chat_complete, stream_chat` stays as-is
- `app/ai/deep_analysis.py` — copied from `attached_assets/deep_analysis_1775234216325.py` (3062 lines); `_call_openrouter_narrative()` kept but adapts to call our `openrouter_client` instead of raw `httpx.post`
- `app/schemas/ai_chat.py` — Pydantic models: `ChatMessage`, `ChatRequest`, `ChatResponse`, `ConversationSummary`
- `app/routers/ai_chat.py` — FastAPI router mounted at `/ai`:
  - `GET  /ai/providers` — returns `{openrouter: {available, models}, ollama: {available, models}}`
  - `POST /ai/chat` — creates or continues a conversation; accepts `{conversation_id?, message, provider, model, goal_id?, context_run_id?}`; streams SSE: `{status}` chunks → `{delta}` chunks → `{done, result}`
  - `GET  /ai/conversations` — lists saved conversations (last 50)
  - `GET  /ai/conversations/{id}` — full conversation with all messages
  - `DELETE /ai/conversations/{id}` — delete
  - `POST /ai/analyze/{run_id}` — runs deep_analysis.analyze() on a backtest run, returns full analysis dict (no AI streaming, pure deterministic + optional AI narrative)
  - `GET  /ai/pipeline-logs` — last 50 orchestrator pipeline logs
- `user_data/ai_conversations/` — directory for JSON conversation files (each file = one conversation)

### Modified files
- `app/core/config.py` — add `AI_CONVERSATIONS_DIR = BASE_DIR / "ai_conversations"` and mkdir
- `app/main.py` — `from app.routers import ai_chat` + `app.include_router(ai_chat.router)`

## Key constraints
- **OpenRouter: free models only** — always use `:free` suffix; `ai_registry.py` filters `fetch_free_models()` to only models whose id ends in `:free` or whose `pricing.prompt == "0"`
- **Ollama**: gracefully skips when not running (is_available() returns False); no error thrown to user
- **No blue colors** (not relevant for backend but note for log messages)
- **Secrets**: read `OPENROUTER_API_KEY` from env; if missing, OpenRouter is marked unavailable but app still starts; do not hardcode keys
- Imports in orchestrator/classifier/registry must be consistent with the `app/ai/` package location

## Dependencies
- `httpx` (likely already installed via freqtrade); `pydantic` (already in use); `sse-starlette` for SSE streaming if not already in use — add via pip if absent

## Done when
- `GET /ai/providers` returns valid JSON with at least one provider section
- `POST /ai/chat` streams a response (even if OPENROUTER_API_KEY is not set it returns a clear error message not a 500)
- `POST /ai/analyze/{run_id}` returns the deep analysis dict for any existing run_id
- App starts without import errors
