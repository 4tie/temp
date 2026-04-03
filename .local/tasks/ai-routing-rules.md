# Task: Complexity-Based AI Routing — Ollama first, OpenRouter for high-stakes roles

## What to build
A routing table in the registry that routes each pipeline role to the right provider based on the classifier's complexity output — not a global setting, not hardcoded per-message, but a decision made per-role per-call.

## Routing table (source of truth)

```
LOW complexity  (or high-confidence simple request)
  → All roles: Ollama first, fallback to cheapest OpenRouter free
  → Exception: code_gen always → OpenRouter (code accuracy cannot be compromised)

MEDIUM complexity  (analysis, explanation, single-step reasoning)
  → classifier   → Ollama
  → reasoner     → Ollama  (draft)
  → composer     → OpenRouter  (polish the draft)
  → code_gen     → OpenRouter
  → explainer    → OpenRouter
  → default      → Ollama

HIGH complexity  (strategy analysis, debate, code mutation)
  → classifier   → Ollama  (fast, just needs to classify)
  → analyst_a    → Ollama  (first perspective — draft quality is fine)
  → analyst_b    → OpenRouter  (second perspective benefits from a different model family)
  → judge        → OpenRouter  (critical validation — needs the best available)
  → composer     → OpenRouter  (final answer quality matters)
  → code_gen     → OpenRouter  (code changes on production strategy)
  → reasoner     → OpenRouter  (complex chain-of-thought needs the strongest model)
  → default      → OpenRouter
```

## Confidence escalation rule
If the classifier's `confidence < 0.7`:
- `low` task → treat as `medium`
- `medium` task → treat as `high`

This prevents simple routing from being applied to tasks the classifier was unsure about.

## Graceful degradation
When the preferred provider for a role is Ollama but Ollama is offline:
- Silently fall back to the cheapest available OpenRouter free model for that role
- Log at DEBUG level, not WARNING — this is expected behaviour

When the preferred provider is OpenRouter but no API key is set:
- Fall back to Ollama for that role
- If Ollama also unavailable → return `[Provider unavailable for role X]` string
- Log at WARNING level (this is an actual configuration gap)

---

## Files to modify

### app/ai/models/registry.py

**Add** at module level:
```python
COMPLEXITY_ROUTING: dict[str, dict[str, str]] = {
    "low": {
        "_default": "ollama",
        "code_gen": "openrouter",
    },
    "medium": {
        "_default": "ollama",
        "composer": "openrouter",
        "code_gen": "openrouter",
        "explainer": "openrouter",
    },
    "high": {
        "_default": "openrouter",
        "classifier": "ollama",
        "analyst_a": "ollama",
    },
}
```

**Add** new function `resolve_provider_for_role`:
```python
def resolve_provider_for_role(
    role: str,
    effective_complexity: str,  # "low" | "medium" | "high"
) -> str:
    """Returns 'openrouter' or 'ollama' for the given role and complexity."""
    table = COMPLEXITY_ROUTING.get(effective_complexity, COMPLEXITY_ROUTING["low"])
    return table.get(role, table.get("_default", "openrouter"))
```

**Add** new function `effective_complexity`:
```python
def effective_complexity(
    complexity: str,
    confidence: float,
    requires_code: bool = False,
) -> str:
    """Escalates complexity when classifier confidence is low."""
    lvl = complexity
    if confidence < 0.7:
        if lvl == "low":
            lvl = "medium"
        elif lvl == "medium":
            lvl = "high"
    if requires_code and lvl == "low":
        lvl = "medium"  # code tasks always get at least medium treatment
    return lvl
```

**Add** new function `get_model_for_role_routed`:
```python
async def get_model_for_role_routed(
    role: str,
    complexity: str,
    confidence: float,
    requires_code: bool = False,
    overrides: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    """
    Returns (model_id, provider, reason).
    Fetches models from the resolved provider; falls back to the other provider.
    """
    if overrides and role in overrides:
        model_id = overrides[role]
        provider = "ollama" if model_id.startswith("ollama/") else "openrouter"
        return model_id, provider, f"override:{role}"

    eff = effective_complexity(complexity, confidence, requires_code)
    preferred_provider = resolve_provider_for_role(role, eff)

    # Try preferred provider first
    models = await fetch_free_models(preferred_provider)
    model_id, reason = get_model_for_role(role, models, overrides=None)

    # If fallback hardcoded model was returned (no real models available), try other provider
    if model_id == _FALLBACK_MODEL and not models:
        other = "openrouter" if preferred_provider == "ollama" else "ollama"
        fallback_models = await fetch_free_models(other)
        if fallback_models:
            model_id, reason = get_model_for_role(role, fallback_models, overrides=None)
            preferred_provider = other
            reason = f"fallback-provider:{reason}"

    return model_id, preferred_provider, f"{eff}-routing:{reason}"
```

---

### app/ai/pipelines/orchestrator.py

**Modify `_call_model`** to use routing when classification is available:

Current signature:
```python
async def _call_model(role, messages, models, role_overrides=None) -> PipelineStep:
```

New signature:
```python
async def _call_model(
    role: str,
    messages: list[dict],
    models: list,                          # kept for backward compat (ignored when classification set)
    role_overrides: dict[str, str] | None = None,
    classification: Classification | None = None,  # NEW
) -> PipelineStep:
```

Routing logic inside `_call_model`:
```python
if classification is not None:
    from ..models.registry import get_model_for_role_routed
    model_id, resolved_provider, reason = await get_model_for_role_routed(
        role=role,
        complexity=classification.complexity.value,
        confidence=classification.confidence,
        requires_code=classification.requires_code,
        overrides=role_overrides,
    )
    # temporarily override the context var for this call
    token = _current_provider.set(resolved_provider)
    try:
        result = await _ai_chat_complete(messages, model_id)
    finally:
        _current_provider.reset(token)
    # ... build PipelineStep with reason
else:
    # original path: use models list + current provider
    model_id, reason = get_model_for_role(role, models, role_overrides)
    result = await _ai_chat_complete(messages, model_id)
```

**Pass `classification` through to `_call_model`** in all pipeline functions that have it:
- `run_simple` → pass `classification`
- `run_analysis` → pass `classification` to both `_call_model("reasoner", ...)` and `_call_model("composer", ...)`
- `run_debate` → pass `classification` to all four `_call_model` calls
- `run_code` → pass `classification`
- Same for all `stream_*` variants

This means each pipeline function needs a one-line change per `_call_model` call, adding `classification=classification`.

---

## What does NOT change
- The `run()` and `stream_run()` entry-point signatures remain the same
- The `_current_provider` ContextVar remains for non-classified calls (e.g. direct tool calls)
- `fetch_free_models(provider)` API unchanged
- The `get_model_for_role` function unchanged (used as the final model-picker within a provider's model list)
- No changes to the router, schemas, or frontend

---

## Acceptance criteria
- `resolve_provider_for_role("composer", "medium")` returns `"openrouter"`
- `resolve_provider_for_role("reasoner", "low")` returns `"ollama"`
- `resolve_provider_for_role("judge", "high")` returns `"openrouter"`
- `effective_complexity("low", 0.5)` returns `"medium"` (low confidence escalates)
- `effective_complexity("medium", 0.9)` returns `"medium"` (high confidence no escalation)
- App starts without errors
- Sending a chat message still works end-to-end
- Pipeline step logs show the routing reason in `selection_reason` field
