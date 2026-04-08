from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.ai.tools.deep_analysis import analyze
from app.core.config import STRATEGIES_DIR
from app.services.results.comparison_metrics import compare_results
from app.services.results.metric_registry import CORE_RESULT_METRICS
from app.services.strategies import load_strategy_param_metadata


INTELLIGENCE_VERSION = 1


def has_strategy_intelligence(result: Mapping[str, Any] | None) -> bool:
    intelligence = result.get("strategy_intelligence") if isinstance(result, Mapping) else None
    return isinstance(intelligence, Mapping) and intelligence.get("version") == INTELLIGENCE_VERSION


def build_strategy_intelligence(
    *,
    run_id: str,
    result: Mapping[str, Any],
    meta: Mapping[str, Any] | None = None,
    parent_result: Mapping[str, Any] | None = None,
    parent_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_result = dict(result or {})
    summary = normalized_result.get("summary") or {}
    analysis = analyze(normalized_result, run_id=run_id, include_ai_narrative=False)
    root = analysis.get("root_cause_diagnosis") or {}
    weaknesses = list(analysis.get("weaknesses") or [])
    strengths = list(analysis.get("strengths") or [])
    parameter_recommendations = list(analysis.get("parameter_recommendations") or [])
    editable_param_lookup = _editable_param_lookup(meta)

    diagnosis_items = _build_diagnosis_items(root, weaknesses, analysis)
    suggestions, rerun_plan = _build_suggestions(`r`n        run_id=run_id,`r`n        root=root,`r`n        parameter_recommendations=parameter_recommendations,`r`n        editable_param_lookup=editable_param_lookup,`r`n        meta=meta,`r`n    )
    summary_card = _build_summary(summary, normalized_result)
    comparison = _build_parent_comparison(
        current_result=normalized_result,
        parent_result=parent_result,
        parent_run_id=(meta or {}).get("parent_run_id") or (parent_meta or {}).get("run_id"),
    )
    suggestion_groups = _group_suggestions(suggestions)

    return {
        "version": INTELLIGENCE_VERSION,
        "summary": summary_card,
        "diagnosis": {
            "primary": {
                "id": root.get("primary_failure_mode") or "unknown",
                "title": root.get("primary_failure_label") or "No clear primary issue detected",
                "severity": root.get("severity") or "neutral",
                "explanation": root.get("root_cause_conclusion") or "No root-cause conclusion available.",
                "evidence": _primary_evidence(root),
                "metric_snapshot": dict(root.get("metric_snapshot") or {}),
                "confidence": root.get("confidence") or "low",
                "confidence_note": root.get("confidence_note") or "",
            },
            "issues": diagnosis_items,
            "secondary_issues": list(root.get("secondary_issues") or []),
            "strengths": [
                {
                    "title": item.get("title") or "Strength",
                    "evidence": item.get("evidence") or "",
                }
                for item in strengths[:3]
            ],
        },
        "suggestions": suggestions,
        "suggestion_groups": suggestion_groups,
        "rerun_plan": rerun_plan,
        "analysis_snapshot": {
            "health_score": analysis.get("health_score") or {},
            "signal_frequency": analysis.get("signal_frequency") or {},
            "exit_quality": analysis.get("exit_quality") or {},
            "overfitting": analysis.get("overfitting") or {},
            "data_warnings": list(analysis.get("data_warnings") or []),
        },
        "comparison_to_parent": comparison,
        "iteration_memory": {
            "parent_run_id": (meta or {}).get("parent_run_id"),
            "improvement_source": (meta or {}).get("improvement_source"),
            "improvement_items": list((meta or {}).get("improvement_items") or []),
            "improvement_applied": list((meta or {}).get("improvement_applied") or []),
            "improvement_skipped": list((meta or {}).get("improvement_skipped") or []),
            "improvement_brief": (meta or {}).get("improvement_brief"),
        },
    }


def attach_strategy_intelligence(result: Mapping[str, Any], intelligence: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(result or {})
    enriched["strategy_intelligence"] = dict(intelligence or {})
    return enriched


def _build_summary(summary: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    overview = result.get("overview") or {}
    run_metadata = result.get("run_metadata") or {}
    risk = result.get("risk_metrics") or {}
    total_trades = _number(_coalesce(summary.get("totalTrades"), overview.get("total_trades")))
    backtest_days = _number(run_metadata.get("backtest_days"))
    trades_per_day = _number(_coalesce(summary.get("tradesPerDay"), run_metadata.get("trades_per_day")))
    if trades_per_day is None and total_trades is not None and backtest_days and backtest_days > 0:
        trades_per_day = total_trades / backtest_days

    return {
        "starting_wallet": _number(_coalesce(summary.get("startingBalance"), overview.get("starting_balance"))),
        "final_wallet": _number(_coalesce(summary.get("finalBalance"), overview.get("final_balance"))),
        "net_profit_abs": _number(_coalesce(summary.get("totalProfit"), overview.get("profit_total_abs"))),
        "net_profit_pct": _number(_coalesce(summary.get("totalProfitPct"), overview.get("profit_percent"))),
        "total_trades": total_trades,
        "trades_per_day": trades_per_day,
        "win_rate": _number(_coalesce(summary.get("winRate"), overview.get("win_rate"))),
        "max_drawdown": _number(_coalesce(summary.get("maxDrawdown"), overview.get("max_drawdown"), risk.get("max_drawdown_pct"))),
        "profit_factor": _number(_coalesce(summary.get("profitFactor"), overview.get("profit_factor"))),
        "avg_trade_duration": _coalesce(summary.get("avgTradeDuration"), summary.get("avg_trade_duration"), overview.get("avg_trade_duration")),
    }


def _build_diagnosis_items(
    root: Mapping[str, Any],
    weaknesses: list[dict[str, Any]],
    analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if root:
        evidence_text = " ".join(
            step.get("finding", "")
            for step in (root.get("causal_chain") or [])
            if isinstance(step, Mapping) and step.get("finding")
        ).strip()
        items.append(
            {
                "id": root.get("primary_failure_mode") or "primary",
                "title": root.get("primary_failure_label") or "Primary issue",
                "severity": root.get("severity") or "warning",
                "explanation": root.get("root_cause_conclusion") or "No conclusion available.",
                "evidence": evidence_text or "No supporting metric evidence was captured.",
                "source": "root_cause",
            }
        )

    for weakness in weaknesses[:3]:
        title = weakness.get("title") or "Observed issue"
        if any(item["title"] == title for item in items):
            continue
        items.append(
            {
                "id": title.lower().replace(" ", "_"),
                "title": title,
                "severity": weakness.get("severity") or "warning",
                "explanation": weakness.get("impact") or weakness.get("evidence") or "",
                "evidence": weakness.get("evidence") or "",
                "source": "weakness",
            }
        )

    signal_frequency = analysis.get("signal_frequency") or {}
    diagnosis = signal_frequency.get("diagnosis")
    if diagnosis and not any(item["id"] == "signal_frequency" for item in items):
        items.append(
            {
                "id": "signal_frequency",
                "title": "Signal Frequency",
                "severity": "warning",
                "explanation": str(diagnosis),
                "evidence": f"{signal_frequency.get('trades_per_day', 0)} trades/day",
                "source": "analysis",
            }
        )

    for idx, item in enumerate(root.get("secondary_issues") or [], start=1):
        secondary_item = _secondary_issue_item(item, idx)
        if secondary_item:
            items.append(secondary_item)

    for idx, warning in enumerate(analysis.get("data_warnings") or [], start=1):
        issue = warning.get("issue") if isinstance(warning, Mapping) else None
        impact = warning.get("impact") if isinstance(warning, Mapping) else None
        if not issue:
            continue
        items.append(
            {
                "id": f"data-warning-{idx}",
                "title": "Data Warning",
                "severity": "warning",
                "explanation": str(impact or issue),
                "evidence": str(issue),
                "source": "data_warning",
            }
        )

    return items[:5]


def _build_suggestions(
    *,
    run_id: str,
    root: Mapping[str, Any],
    parameter_recommendations: list[dict[str, Any]],
    editable_param_lookup: Mapping[str, str],
    meta: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    auto_param_changes: list[dict[str, Any]] = []
    unsupported_items: list[dict[str, Any]] = []

    strategy_name = str(
        (meta or {}).get("strategy_class")
        or (meta or {}).get("base_strategy")
        or (meta or {}).get("strategy")
        or ""
    ).strip()
    run_context = {
        "run_id": run_id,
        "strategy_name": strategy_name,
        "timeframe": (meta or {}).get("timeframe"),
        "exchange": (meta or {}).get("exchange"),
        "timerange": (meta or {}).get("timerange"),
    }
    primary_title = str(root.get("primary_failure_label") or root.get("primary_failure_mode") or "Run diagnosis")
    primary_evidence = _primary_evidence(root)

    for idx, item in enumerate(parameter_recommendations[:4], start=1):
        parameter = str(item.get("parameter") or "").strip()
        suggestion_value = item.get("suggestion")
        title = parameter or f"Adjustment {idx}"
        auto_param = _normalize_auto_param_change(parameter, suggestion_value, editable_param_lookup)
        auto_applicable = auto_param is not None
        evidence = str(item.get("evidence") or "").strip()
        suggestion_id = f"param-{idx}"
        suggestions.append(
            {
                "id": suggestion_id,
                "title": title,
                "description": str(item.get("reason") or item.get("suggestion") or ""),
                "priority": item.get("confidence") or "medium",
                "auto_applicable": auto_applicable,
                "parameter": auto_param["name"] if auto_param else parameter,
                "suggested_value": auto_param["value"] if auto_param else suggestion_value,
                "evidence": evidence,
                "action_type": "quick_param" if auto_applicable else "manual_guidance",
                "source": "parameter_recommendation",
                "apply_action": {
                    "enabled": True,
                    "type": "apply_suggestion",
                    "suggestion_id": suggestion_id,
                    "action_type": "quick_param" if auto_applicable else "manual_guidance",
                    "label": "Apply",
                    "supports_retest": True,
                    "target": {
                        "parameter": auto_param["name"] if auto_param else parameter,
                        "value": auto_param["value"] if auto_param else suggestion_value,
                    } if auto_applicable else None,
                    "ai_apply_payload": {
                        "title": title,
                        "description": str(item.get("reason") or item.get("suggestion") or ""),
                        "evidence": evidence,
                        "diagnosis_title": primary_title,
                        "diagnosis_evidence": primary_evidence,
                        "run_context": run_context,
                    } if not auto_applicable else None,
                },
            }
        )
        if auto_param:
            auto_param_changes.append(
                {
                    **auto_param,
                    "label": title,
                    "reason": str(item.get("reason") or ""),
                    "evidence": evidence,
                }
            )
        else:
            unsupported_items.append(
                {
                    "title": title,
                    "parameter": parameter or None,
                    "suggested_value": suggestion_value,
                    "reason": str(item.get("reason") or ""),
                    "evidence": evidence,
                }
            )

    for idx, text in enumerate(root.get("fix_priority") or [], start=1):
        suggestion_id = f"fix-{idx}"
        suggestions.append(
            {
                "id": suggestion_id,
                "title": str(text),
                "description": str(text),
                "priority": "high" if idx == 1 else "medium",
                "auto_applicable": False,
                "parameter": None,
                "suggested_value": None,
                "evidence": "",
                "action_type": "manual_guidance",
                "source": "fix_priority",
                "apply_action": {
                    "enabled": True,
                    "type": "apply_suggestion",
                    "suggestion_id": suggestion_id,
                    "action_type": "manual_guidance",
                    "label": "Apply",
                    "supports_retest": True,
                    "target": None,
                    "ai_apply_payload": {
                        "title": str(text),
                        "description": str(text),
                        "evidence": "",
                        "diagnosis_title": primary_title,
                        "diagnosis_evidence": primary_evidence,
                        "run_context": run_context,
                    },
                },
            }
        )

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for suggestion in suggestions:
        key = f"{suggestion.get('title')}::{suggestion.get('parameter')}::{suggestion.get('suggested_value')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(suggestion)

    return deduped[:6], {
        "auto_param_changes": auto_param_changes,
        "unsupported_items": unsupported_items[:4],
        "manual_actions": [
            suggestion["title"]
            for suggestion in deduped
            if not suggestion.get("auto_applicable")
        ][:4],
        "auto_action_count": len(auto_param_changes),
        "manual_action_count": sum(1 for suggestion in deduped if not suggestion.get("auto_applicable")),
    }


def _normalize_auto_param_change(
    parameter: str,
    suggestion_value: Any,
    editable_param_lookup: Mapping[str, str],
) -> dict[str, Any] | None:
    key = parameter.strip().lower()
    if not key or not _is_scalar_suggestion_value(suggestion_value):
        return None
    mapped_name = editable_param_lookup.get(key)
    if not mapped_name:
        return None
    return {"name": mapped_name, "value": suggestion_value}


def _editable_param_lookup(meta: Mapping[str, Any] | None) -> dict[str, str]:
    strategy_name = str(
        (meta or {}).get("strategy_class")
        or (meta or {}).get("base_strategy")
        or (meta or {}).get("strategy")
        or ""
    ).strip()
    strategy_path = (meta or {}).get("strategy_path")
    if not strategy_name or not _is_default_strategy_path(strategy_path):
        return {}
    try:
        metadata = load_strategy_param_metadata(strategy_name, strategies_dir=STRATEGIES_DIR)
    except Exception:
        return {}

    lookup: dict[str, str] = {}
    for item in metadata.get("parameters") or []:
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            lookup[name.strip().lower()] = name.strip()
    return lookup


def _is_default_strategy_path(strategy_path: Any) -> bool:
    if not strategy_path:
        return True
    try:
        return Path(strategy_path).resolve() == STRATEGIES_DIR.resolve()
    except Exception:
        return False


def _is_scalar_suggestion_value(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and value != ""


def _build_parent_comparison(
    *,
    current_result: Mapping[str, Any],
    parent_result: Mapping[str, Any] | None,
    parent_run_id: str | None,
) -> dict[str, Any] | None:
    if not isinstance(parent_result, Mapping):
        return None

    metrics = compare_results(parent_result, current_result, keys=list(CORE_RESULT_METRICS))
    return {
        "parent_run_id": parent_run_id,
        "metrics": metrics,
        "highlights": _comparison_highlights(metrics),
    }


def _comparison_highlights(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    ordered_keys = ("profit_percent", "profit_total_abs", "win_rate", "profit_factor", "max_drawdown")
    rows: list[dict[str, Any]] = []
    for key in ordered_keys:
        row = metrics.get(key) if isinstance(metrics, Mapping) else None
        if not isinstance(row, Mapping) or row.get("diff") is None:
            continue
        rows.append(dict(row))
    return rows[:4]


def _primary_evidence(root: Mapping[str, Any]) -> str:
    findings = [
        str(step.get("finding") or "").strip()
        for step in (root.get("causal_chain") or [])
        if isinstance(step, Mapping) and str(step.get("finding") or "").strip()
    ]
    evidence = " ".join(findings[:3]).strip()
    if evidence:
        return evidence
    return _metric_snapshot_text(root.get("metric_snapshot"))


def _group_suggestions(suggestions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    quick_params = [dict(item) for item in suggestions if item.get("auto_applicable")]
    manual_guidance = [dict(item) for item in suggestions if not item.get("auto_applicable")]
    return {
        "quick_params": quick_params,
        "manual_guidance": manual_guidance,
    }


def _secondary_issue_item(raw_value: Any, idx: int) -> dict[str, Any] | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    title, _, explanation = text.partition(":")
    normalized_title = title.replace("_", " ").strip().title() if title else f"Secondary issue {idx}"
    normalized_explanation = explanation.strip() or text
    return {
        "id": f"secondary-{idx}",
        "title": normalized_title,
        "severity": "warning",
        "explanation": normalized_explanation,
        "evidence": text,
        "source": "secondary_issue",
    }


def _metric_snapshot_text(snapshot: Any) -> str:
    if not isinstance(snapshot, Mapping):
        return ""
    parts: list[str] = []
    total_trades = _number(snapshot.get("total_trades"))
    win_rate = _number(snapshot.get("win_rate_pct"))
    profit_factor = _number(snapshot.get("profit_factor"))
    drawdown = _number(snapshot.get("max_drawdown_pct"))
    total_profit = _number(snapshot.get("total_profit_pct"))
    if total_trades is not None:
        parts.append(f"{int(total_trades)} trades")
    if win_rate is not None:
        parts.append(f"{win_rate:.1f}% win rate")
    if profit_factor is not None:
        parts.append(f"profit factor {profit_factor:.2f}")
    if total_profit is not None:
        parts.append(f"{total_profit:+.2f}% return")
    if drawdown is not None:
        parts.append(f"{drawdown:.2f}% max drawdown")
    return " | ".join(parts)


def _number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None

