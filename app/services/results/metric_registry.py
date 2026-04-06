from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from app.services.results.summary_normalizer import (
    coerce_profit_pct,
    coerce_rate_pct,
    drawdown_to_pct,
    to_float,
)


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    category: str
    format: str
    higher_is_better: bool | None
    sources: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)
    decimals: int = 2
    show_sign: bool = False


RESULT_METRICS: tuple[MetricDef, ...] = (
    MetricDef(
        key="starting_balance",
        label="Starting Balance",
        category="capital",
        format="currency",
        higher_is_better=None,
        sources=(("summary", "startingBalance"), ("overview", "starting_balance"), ("balance_metrics", "starting_balance")),
    ),
    MetricDef(
        key="final_balance",
        label="Final Balance",
        category="capital",
        format="currency",
        higher_is_better=True,
        sources=(("summary", "finalBalance"), ("overview", "final_balance"), ("balance_metrics", "final_balance")),
    ),
    MetricDef(
        key="profit_percent",
        label="Profit %",
        category="performance",
        format="percent",
        higher_is_better=True,
        sources=(
            ("summary", "totalProfitPct"),
            ("summary", "profit_total_pct"),
            ("overview", "profit_percent"),
            ("balance_metrics", "profit_total_pct"),
            ("overview", "profit_total"),
        ),
        aliases=("profit_pct",),
        decimals=2,
        show_sign=True,
    ),
    MetricDef(
        key="profit_total_abs",
        label="Profit",
        category="performance",
        format="currency",
        higher_is_better=True,
        sources=(
            ("summary", "totalProfit"),
            ("overview", "profit_total_abs"),
            ("balance_metrics", "profit_total_abs"),
        ),
        aliases=("profit_total",),
    ),
    MetricDef(
        key="total_trades",
        label="Total Trades",
        category="activity",
        format="integer",
        higher_is_better=None,
        sources=(("summary", "totalTrades"), ("overview", "total_trades"), ("run_metadata", "total_trades")),
        decimals=0,
    ),
    MetricDef(
        key="trades_per_day",
        label="Trades / Day",
        category="activity",
        format="number",
        higher_is_better=None,
        sources=(("summary", "tradesPerDay"), ("summary", "trades_per_day"), ("overview", "trades_per_day"), ("run_metadata", "trades_per_day")),
        decimals=2,
    ),
    MetricDef(
        key="win_rate",
        label="Win Rate",
        category="performance",
        format="percent",
        higher_is_better=True,
        sources=(("summary", "winRate"), ("overview", "win_rate"), ("summary_metrics", "winrate")),
        decimals=1,
    ),
    MetricDef(
        key="profit_factor",
        label="Profit Factor",
        category="performance",
        format="ratio",
        higher_is_better=True,
        sources=(("summary", "profitFactor"), ("overview", "profit_factor"), ("summary_metrics", "profit_factor")),
        decimals=3,
    ),
    MetricDef(
        key="max_drawdown",
        label="Max Drawdown",
        category="risk",
        format="percent",
        higher_is_better=False,
        sources=(
            ("summary", "maxDrawdown"),
            ("summary", "max_drawdown_pct"),
            ("overview", "max_drawdown"),
            ("risk_metrics", "max_drawdown_pct"),
            ("risk_metrics", "max_drawdown"),
        ),
        decimals=1,
    ),
    MetricDef(
        key="trading_volume",
        label="Trading Volume",
        category="activity",
        format="currency",
        higher_is_better=None,
        sources=(("summary", "tradingVolume"), ("overview", "trading_volume"), ("summary_metrics", "total_volume")),
    ),
    MetricDef(
        key="sharpe_ratio",
        label="Sharpe",
        category="quality",
        format="ratio",
        higher_is_better=True,
        sources=(("summary", "sharpeRatio"), ("summary", "sharpe_ratio"), ("overview", "sharpe_ratio"), ("summary_metrics", "sharpe")),
        decimals=2,
    ),
)

CORE_RESULT_METRICS: tuple[str, ...] = (
    "starting_balance",
    "final_balance",
    "profit_percent",
    "profit_total_abs",
    "total_trades",
    "win_rate",
    "profit_factor",
    "max_drawdown",
    "trading_volume",
)
RESULTS_TABLE_METRICS: tuple[str, ...] = (
    "profit_percent",
    "total_trades",
    "win_rate",
    "max_drawdown",
    "sharpe_ratio",
)
AI_CONTEXT_METRICS: tuple[str, ...] = (
    "profit_percent",
    "win_rate",
    "max_drawdown",
    "total_trades",
    "sharpe_ratio",
    "profit_factor",
)
AI_LOOP_REPORT_METRICS: tuple[str, ...] = CORE_RESULT_METRICS

_METRIC_INDEX = {metric.key: metric for metric in RESULT_METRICS}
for metric in RESULT_METRICS:
    for alias in metric.aliases:
        _METRIC_INDEX[alias] = metric


def get_metric_def(key: str) -> MetricDef:
    try:
        return _METRIC_INDEX[key]
    except KeyError as exc:
        raise KeyError(f"Unknown metric key: {key}") from exc


def iter_metric_defs(keys: Iterable[str] | None = None) -> list[MetricDef]:
    selected = list(keys or [metric.key for metric in RESULT_METRICS])
    return [get_metric_def(key) for key in selected]


def metric_registry_payload() -> dict[str, Any]:
    return {
        "metrics": [_metric_payload(metric) for metric in RESULT_METRICS],
        "groups": {
            "core": list(CORE_RESULT_METRICS),
            "results_table": list(RESULTS_TABLE_METRICS),
            "ai_context": list(AI_CONTEXT_METRICS),
            "ai_loop_report": list(AI_LOOP_REPORT_METRICS),
        },
    }


def extract_metric_value(result: Mapping[str, Any] | None, key: str) -> Any:
    if not isinstance(result, Mapping):
        return None

    metric = get_metric_def(key)
    raw = None
    for section, source_key in metric.sources:
        if section == "__root__":
            candidate = result.get(source_key)
        else:
            container = result.get(section)
            candidate = container.get(source_key) if isinstance(container, Mapping) else None
        if candidate is not None and candidate != "":
            raw = candidate
            break
    return _normalize_metric_value(metric, raw, result)


def build_metric_snapshot(
    result: Mapping[str, Any] | None,
    metric_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        return {}
    snapshot: dict[str, Any] = {}
    for metric in iter_metric_defs(metric_keys):
        snapshot[metric.key] = extract_metric_value(result, metric.key)
    return snapshot


def compare_metric_snapshots(
    snapshot_a: Mapping[str, Any] | None,
    snapshot_b: Mapping[str, Any] | None,
    metric_keys: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for metric in iter_metric_defs(metric_keys):
        before = snapshot_a.get(metric.key) if isinstance(snapshot_a, Mapping) else None
        after = snapshot_b.get(metric.key) if isinstance(snapshot_b, Mapping) else None
        diff[metric.key] = {
            "label": metric.label,
            "category": metric.category,
            "format": metric.format,
            "higher_is_better": metric.higher_is_better,
            "a": before,
            "b": after,
            "diff": metric_delta(before, after),
        }
    return diff


def build_metric_delta_rows(
    before_result: Mapping[str, Any] | None,
    after_result: Mapping[str, Any] | None,
    metric_keys: Iterable[str] | None = None,
    *,
    section: str = "core",
) -> list[dict[str, Any]]:
    snapshot_before = build_metric_snapshot(before_result, metric_keys)
    snapshot_after = build_metric_snapshot(after_result, metric_keys)
    rows: list[dict[str, Any]] = []
    for metric in iter_metric_defs(metric_keys):
        before = snapshot_before.get(metric.key)
        after = snapshot_after.get(metric.key)
        if before is None and after is None:
            continue
        rows.append(
            {
                "section": section,
                "metric": metric.key,
                "label": metric.label,
                "category": metric.category,
                "format": metric.format,
                "higher_is_better": metric.higher_is_better,
                "before": before,
                "after": after,
                "delta": metric_delta(before, after),
            }
        )
    return rows


def metric_delta(before: Any, after: Any) -> float | None:
    try:
        return round(float(after) - float(before), 4)
    except Exception:
        return None


def _metric_payload(metric: MetricDef) -> dict[str, Any]:
    payload = asdict(metric)
    payload.pop("sources", None)
    return payload


def _normalize_metric_value(metric: MetricDef, raw: Any, result: Mapping[str, Any]) -> Any:
    if metric.key == "profit_percent":
        return coerce_profit_pct(
            raw,
            ratio_value=_pick_result_value(result, ("overview", "profit_total"), ("balance_metrics", "profit_total")),
            abs_value=_pick_result_value(
                result,
                ("summary", "totalProfit"),
                ("overview", "profit_total_abs"),
                ("balance_metrics", "profit_total_abs"),
            ),
            starting_balance=_pick_result_value(
                result,
                ("summary", "startingBalance"),
                ("overview", "starting_balance"),
                ("balance_metrics", "starting_balance"),
            ),
            final_balance=_pick_result_value(
                result,
                ("summary", "finalBalance"),
                ("overview", "final_balance"),
                ("balance_metrics", "final_balance"),
            ),
        )

    if metric.key == "win_rate":
        return coerce_rate_pct(raw)

    if metric.key == "max_drawdown":
        return drawdown_to_pct(raw)

    if metric.format == "integer":
        numeric = to_float(raw)
        return int(numeric) if numeric is not None else None

    if metric.format in {"currency", "ratio", "number", "percent"}:
        return to_float(raw)

    return raw


def _pick_result_value(result: Mapping[str, Any], *paths: tuple[str, str]) -> Any:
    for section, key in paths:
        container = result.get(section)
        if isinstance(container, Mapping):
            value = container.get(key)
            if value is not None and value != "":
                return value
    return None


__all__ = [
    "AI_CONTEXT_METRICS",
    "AI_LOOP_REPORT_METRICS",
    "CORE_RESULT_METRICS",
    "RESULTS_TABLE_METRICS",
    "MetricDef",
    "build_metric_delta_rows",
    "build_metric_snapshot",
    "compare_metric_snapshots",
    "extract_metric_value",
    "get_metric_def",
    "iter_metric_defs",
    "metric_delta",
    "metric_registry_payload",
]
