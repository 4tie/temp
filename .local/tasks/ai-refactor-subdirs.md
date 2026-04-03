# Task: Reorganize app/ai/ into clean subdirectory structure

## Goal
Move all flat `app/ai/*.py` files into their logical subdirectories and add a `memory/conversations.py` module for conversation management. Update every import to match the new layout. No functional changes — this is a structural refactor.

## Current flat layout (before)
```
app/ai/
  __init__.py
  openrouter_client.py
  ollama_client.py
  provider_dispatch.py
  ai_registry.py
  ai_classifier.py
  ai_orchestrator.py
  deep_analysis.py
  agents/      (empty)
  memory/      (empty)
  models/      (empty)
  pipelines/   (empty)
  prompts/     (empty)
  tools/       (empty)
```

## Target layout (after)
```
app/ai/
  __init__.py                      ← updated re-exports
  models/
    __init__.py                    ← re-exports: chat_complete, stream_chat, fetch_free_models, get_model_for_role
    openrouter_client.py           ← moved from app/ai/openrouter_client.py
    ollama_client.py               ← moved from app/ai/ollama_client.py
    provider_dispatch.py           ← moved from app/ai/provider_dispatch.py
    registry.py                    ← moved+renamed from app/ai/ai_registry.py
  pipelines/
    __init__.py                    ← re-exports: run, stream_run, classify, Classification, PipelineType
    orchestrator.py                ← moved+renamed from app/ai/ai_orchestrator.py
    classifier.py                  ← moved+renamed from app/ai/ai_classifier.py
  prompts/
    __init__.py                    ← re-exports all prompt constants
    trading.py                     ← extracted from orchestrator: REASONER_SYSTEM_PROMPT,
                                      COMPOSER_SYSTEM_PROMPT, ANALYST_SYSTEM_PROMPT,
                                      CODE_GEN_SYSTEM_PROMPT, CODE_EXPLAINER_SYSTEM_PROMPT,
                                      CODE_AWARE_ADVISOR_SYSTEM_PROMPT, GOAL_DIRECTIVES
  tools/
    __init__.py                    ← re-exports: analyze, compute_chart_data
    deep_analysis.py               ← moved from app/ai/deep_analysis.py
  memory/
    __init__.py                    ← re-exports: load_conversation, save_conversation, list_conversations, delete_conversation
    conversations.py               ← NEW: conversation CRUD extracted from app/routers/ai_chat.py
  agents/
    __init__.py                    ← placeholder, empty for now
```

## Step-by-step changes

### 1. app/ai/models/
- Create `app/ai/models/__init__.py` with re-exports
- Move `openrouter_client.py` → `app/ai/models/openrouter_client.py`; fix relative imports inside (none needed, it uses only stdlib/httpx)
- Move `ollama_client.py` → `app/ai/models/ollama_client.py`
- Move `provider_dispatch.py` → `app/ai/models/provider_dispatch.py`; update its inner lazy imports: `from .ollama_client import ...` and `from .openrouter_client import ...`
- Move `ai_registry.py` → `app/ai/models/registry.py`; update its import: `from .openrouter_client import list_models` → stays as-is since it's in the same package; `from .ollama_client import list_models as ollama_list_models` → same

### 2. app/ai/prompts/
- Create `app/ai/prompts/__init__.py` with re-exports
- Create `app/ai/prompts/trading.py` containing all system prompts and GOAL_DIRECTIVES moved out of orchestrator (they currently live in `ai_orchestrator.py`)

### 3. app/ai/pipelines/
- Create `app/ai/pipelines/__init__.py` with re-exports
- Move `ai_orchestrator.py` → `app/ai/pipelines/orchestrator.py`; update its imports:
  - `from ..core.storage import write_json, _ensure` → stays (parents[2] is still app/core/storage)
  - `from .openrouter_client import chat_complete, stream_chat` → `from ..models.provider_dispatch import chat_complete, stream_chat`
  - `from .ai_registry import fetch_free_models, get_model_for_role` → `from ..models.registry import fetch_free_models, get_model_for_role`
  - `from .ai_classifier import classify, Classification, PipelineType, ComplexityLevel` → `from .classifier import classify, Classification, PipelineType, ComplexityLevel`
  - All prompt constants imported from `..prompts.trading` instead of defined inline
- Move `ai_classifier.py` → `app/ai/pipelines/classifier.py`; update imports:
  - `from .openrouter_client import chat_complete` → `from ..models.provider_dispatch import chat_complete`
  - `from .ai_registry import fetch_free_models, get_model_for_role` → `from ..models.registry import fetch_free_models, get_model_for_role`

### 4. app/ai/tools/
- Create `app/ai/tools/__init__.py` with re-exports
- Move `deep_analysis.py` → `app/ai/tools/deep_analysis.py`; its internal `_call_openrouter_narrative` already uses `from .openrouter_client import chat_complete` — update to `from ..models.openrouter_client import chat_complete`

### 5. app/ai/memory/
- Create `app/ai/memory/__init__.py` with re-exports
- Create `app/ai/memory/conversations.py` extracting conversation logic currently inlined in `app/routers/ai_chat.py`:
  - `_SAFE_CONV_ID_RE`
  - `_conv_path(conv_id)`
  - `_load_conversation(conv_id) -> dict | None`
  - `_save_conversation(conv_id, data)`
  - `_list_conversations(limit) -> list`
  - `_delete_conversation(conv_id) -> bool`
  Now exposed as public: `load_conversation`, `save_conversation`, `list_conversations`, `delete_conversation`, `new_conversation_id`

### 6. app/ai/agents/
- Create empty `app/ai/agents/__init__.py`

### 7. app/ai/__init__.py (top-level update)
Re-export the most important symbols for convenience:
```python
from .models.provider_dispatch import chat_complete, stream_chat
from .pipelines.orchestrator import run, stream_run
from .pipelines.classifier import classify
from .tools.deep_analysis import analyze
```

### 8. app/routers/ai_chat.py (imports update)
Update all imports to use new paths:
- `from app.ai.pipelines.orchestrator import run, stream_run`
- `from app.ai.pipelines.classifier import classify`
- `from app.ai.models.registry import fetch_free_models`
- `from app.ai.models.openrouter_client import list_models as or_list_models`
- `from app.ai.models.ollama_client import is_available, list_models as oll_list_models`
- `from app.ai.tools.deep_analysis import analyze`
- `from app.ai.memory.conversations import load_conversation, save_conversation, list_conversations, delete_conversation, new_conversation_id`
- Remove all the inline conversation helpers from `ai_chat.py` (moved to memory/conversations.py)

### 9. Delete old flat files
After all moves, delete the old flat files:
- `app/ai/openrouter_client.py`
- `app/ai/ollama_client.py`
- `app/ai/provider_dispatch.py`
- `app/ai/ai_registry.py`
- `app/ai/ai_classifier.py`
- `app/ai/ai_orchestrator.py`
- `app/ai/deep_analysis.py`

## Acceptance criteria
- `python -c "from app.ai import chat_complete, stream_run, analyze"` succeeds
- `python -c "from app.routers.ai_chat import router"` succeeds
- `GET /ai/providers` returns valid JSON
- App starts with no import errors
- All six subdirectories have `__init__.py` files
