from __future__ import annotations

import difflib
import json
from typing import Any, Mapping

from fastapi import HTTPException

from app.ai.models.provider_dispatch import chat_complete, get_last_dispatch_meta
from app.ai.models.registry import fetch_free_models, get_model_for_role
from app.services.storage import append_app_event, load_run_meta, load_run_results
from app.services.strategies import (
    build_strategy_sidecar_payload,
    read_strategy_current_values,
    read_strategy_source,
    resolve_strategy_source_path,
    save_strategy_current_values,
    save_strategy_source,
)
from app.services.ai_chat.apply_code_service import extract_code_blocks_with_hints


_SUPPORTED_PROVIDERS = {"openrouter", "ollama"}


def _checked_provider(provider: str | None) -> str:
    value = str(provider or "openrouter").strip().lower()
    if value not in _SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    return value


def _is_default_strategy_path(strategy_path: Any) -> bool:
    if not strategy_path:
        return True
    normalized = str(strategy_path).replace("/", "\\").lower().rstrip("\\")
    return normalized.endswith("user_data\\strategies")


def _resolve_suggestion(results: Mapping[str, Any], suggestion_id: str) -> dict[str, Any]:
    suggestions = results.get("strategy_intelligence", {}).get("suggestions") or []
    for item in suggestions:
        if str(item.get("id") or "") == suggestion_id:
            return dict(item)
    raise HTTPException(status_code=404, detail="Suggestion not found")


def _diff_preview(before: str, after: str, *, fromfile: str, tofile: str) -> list[str]:
    return list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )[:80]


def _diff_summary(lines: list[str]) -> dict[str, Any]:
    added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    return {
        "added": added,
        "removed": removed,
        "changed": added + removed,
        "preview": lines,
    }


def _base_retest_payload(
    *,
    run_id: str,
    meta: Mapping[str, Any],
    suggestion: Mapping[str, Any],
    strategy_name: str,
    strategy_params: dict[str, Any],
) -> dict[str, Any]:
    title = str(suggestion.get("title") or "Applied suggestion")
    description = str(suggestion.get("description") or title)
    return {
        "strategy": strategy_name,
        "strategy_label": meta.get("strategy") if meta.get("strategy") != strategy_name else None,
        "strategy_path": meta.get("strategy_path") or None,
        "pairs": list(meta.get("pairs") or []),
        "timeframe": meta.get("timeframe") or "5m",
        "timerange": meta.get("timerange") or None,
        "exchange": meta.get("exchange") or "binance",
        "parent_run_id": run_id,
        "improvement_source": "strategy_intelligence_apply",
        "improvement_items": [title],
        "improvement_applied": [title],
        "improvement_skipped": [],
        "improvement_brief": description,
        "strategy_params": dict(strategy_params or {}),
    }


def _normalize_strategy_source(text: str, strategy_name: str) -> str:
    blocks = extract_code_blocks_with_hints(text)
    for block in blocks:
        lang = str(block.get("language") or "").lower()
        if lang in {"python", "py", ""}:
            code = str(block.get("code") or "").strip()
            if code:
                return code
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
    if f"class {strategy_name}" in raw:
        return raw
    return raw


async def _run_manual_apply(
    *,
    run_id: str,
    meta: Mapping[str, Any],
    results: Mapping[str, Any],
    suggestion: Mapping[str, Any],
    provider: str,
) -> dict[str, Any]:
    strategy_name = str(meta.get("strategy_class") or meta.get("base_strategy") or meta.get("strategy") or "").strip()
    if not strategy_name:
        raise HTTPException(status_code=400, detail="Strategy class is unavailable for AI apply")
    if not _is_default_strategy_path(meta.get("strategy_path")):
        raise HTTPException(status_code=400, detail="AI apply only supports strategies in user_data/strategies")

    source_path = resolve_strategy_source_path(strategy_name)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Strategy source not found")

    old_source = read_strategy_source(strategy_name)
    current_params = read_strategy_current_values(strategy_name) or dict(meta.get("strategy_params") or {})
    diagnosis = results.get("strategy_intelligence", {}).get("diagnosis", {})
    primary = diagnosis.get("primary") or {}
    apply_action = suggestion.get("apply_action") or {}
    ai_payload = apply_action.get("ai_apply_payload") or {}

    models = await fetch_free_models(provider)
    model_id, model_reason = get_model_for_role("code_gen", models)
    messages = [
        {
            "role": "system",
            "content": (
                "You edit Python trading strategies. Return the full updated Python source only in one python code block. "
                "Keep the existing class name and preserve unrelated behavior. Make the smallest safe change that applies the requested suggestion."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "Apply one Strategy Intelligence suggestion to this strategy and return the full updated source.",
                    "run_id": run_id,
                    "strategy_name": strategy_name,
                    "provider_request": provider,
                    "model_reason": model_reason,
                    "suggestion": {
                        "id": suggestion.get("id"),
                        "title": suggestion.get("title"),
                        "description": suggestion.get("description"),
                        "evidence": suggestion.get("evidence"),
                    },
                    "diagnosis": {
                        "title": primary.get("title"),
                        "explanation": primary.get("explanation"),
                        "evidence": primary.get("evidence"),
                    },
                    "apply_context": ai_payload,
                    "current_params": current_params,
                    "current_source": old_source,
                },
                ensure_ascii=False,
            ),
        },
    ]
    raw = await chat_complete(messages, model=model_id, provider=provider)
    new_source = _normalize_strategy_source(raw, strategy_name)
    if not new_source or new_source == old_source:
        raise HTTPException(status_code=502, detail="AI apply did not produce an updated strategy source")

    save_result = save_strategy_source(strategy_name, new_source)
    diff_lines = _diff_preview(old_source, new_source, fromfile=source_path.name, tofile=source_path.name)
    dispatch_meta = get_last_dispatch_meta()
    current_strategy_params = read_strategy_current_values(strategy_name) or current_params
    warnings: list[str] = []
    if dispatch_meta.get("fallback_used"):
        warnings.append("Provider fallback was used while applying this suggestion.")

    return {
        "ok": True,
        "suggestion_id": suggestion.get("id"),
        "action_type": suggestion.get("action_type") or "manual_guidance",
        "applied": True,
        "applied_changes": [f"Updated {strategy_name}.py from AI guidance."],
        "change_set": {
            "params": [],
            "source": {
                "path": str(source_path),
                "changed": True,
                "bytes_written": save_result.get("bytes_written") or 0,
            },
        },
        "diff_summary": _diff_summary(diff_lines),
        "warnings": warnings,
        "strategy_name": strategy_name,
        "strategy_params": dict(current_strategy_params or {}),
        "source_changed": True,
        "provider_meta": {
            "requested_provider": provider,
            "provider": dispatch_meta.get("provider") or provider,
            "requested_model": model_id,
            "model": dispatch_meta.get("model") or model_id,
            "fallback_used": bool(dispatch_meta.get("fallback_used")),
        },
        "retest_payload": _base_retest_payload(
            run_id=run_id,
            meta=meta,
            suggestion=suggestion,
            strategy_name=strategy_name,
            strategy_params=dict(current_strategy_params or {}),
        ),
    }


def _run_quick_apply(
    *,
    run_id: str,
    meta: Mapping[str, Any],
    suggestion: Mapping[str, Any],
) -> dict[str, Any]:
    strategy_name = str(meta.get("strategy_class") or meta.get("base_strategy") or meta.get("strategy") or "").strip()
    if not strategy_name:
        raise HTTPException(status_code=400, detail="Strategy class is unavailable for param apply")
    if not _is_default_strategy_path(meta.get("strategy_path")):
        raise HTTPException(status_code=400, detail="Quick apply only supports strategies in user_data/strategies")

    parameter = str(suggestion.get("parameter") or "").strip()
    if not parameter:
        raise HTTPException(status_code=400, detail="Suggestion is missing a target parameter")
    value = suggestion.get("suggested_value")

    current_values = read_strategy_current_values(strategy_name) or dict(meta.get("strategy_params") or {})
    before_value = current_values.get(parameter)
    updated_values = dict(current_values)
    updated_values[parameter] = value

    before_payload = build_strategy_sidecar_payload(strategy_name, current_values)
    after_payload = build_strategy_sidecar_payload(strategy_name, updated_values)
    save_strategy_current_values(strategy_name, updated_values)
    diff_lines = _diff_preview(
        json.dumps(before_payload, indent=2, ensure_ascii=False),
        json.dumps(after_payload, indent=2, ensure_ascii=False),
        fromfile=f"{strategy_name}.json",
        tofile=f"{strategy_name}.json",
    )

    return {
        "ok": True,
        "suggestion_id": suggestion.get("id"),
        "action_type": suggestion.get("action_type") or "quick_param",
        "applied": True,
        "applied_changes": [f"{parameter}: {before_value!r} -> {value!r}"],
        "change_set": {
            "params": [
                {
                    "name": parameter,
                    "before": before_value,
                    "after": value,
                }
            ],
            "source": {
                "path": str(resolve_strategy_source_path(strategy_name)),
                "changed": False,
                "bytes_written": 0,
            },
        },
        "diff_summary": _diff_summary(diff_lines),
        "warnings": [],
        "strategy_name": strategy_name,
        "strategy_params": updated_values,
        "source_changed": False,
        "provider_meta": {
            "requested_provider": "local",
            "provider": "local",
            "requested_model": None,
            "model": None,
            "fallback_used": False,
        },
        "retest_payload": _base_retest_payload(
            run_id=run_id,
            meta=meta,
            suggestion=suggestion,
            strategy_name=strategy_name,
            strategy_params=updated_values,
        ),
    }


async def apply_strategy_intelligence_suggestion(
    *,
    run_id: str,
    suggestion_id: str,
    provider: str = "openrouter",
) -> dict[str, Any]:
    provider = _checked_provider(provider)
    meta = load_run_meta(run_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Run not found")
    results = load_run_results(run_id)
    if not results:
        raise HTTPException(status_code=404, detail="Run results not found")

    suggestion = _resolve_suggestion(results, suggestion_id)
    action_type = str(suggestion.get("action_type") or "")
    if action_type == "quick_param":
        payload = _run_quick_apply(run_id=run_id, meta=meta, suggestion=suggestion)
    elif action_type == "manual_guidance":
        payload = await _run_manual_apply(
            run_id=run_id,
            meta=meta,
            results=results,
            suggestion=suggestion,
            provider=provider,
        )
    else:
        raise HTTPException(status_code=400, detail="Suggestion is not actionable")

    append_app_event(
        category="event",
        source="strategy_intelligence",
        action="apply_suggestion",
        status="ok",
        message=f"Applied suggestion {suggestion_id} for run {run_id}.",
        run_id=run_id,
        suggestion_id=suggestion_id,
        action_type=payload.get("action_type"),
        strategy=payload.get("strategy_name"),
        provider=(payload.get("provider_meta") or {}).get("provider"),
        source_changed=payload.get("source_changed"),
    )
    return payload
