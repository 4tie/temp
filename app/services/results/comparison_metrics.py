from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.results.metric_registry import (
    CORE_RESULT_METRICS,
    build_metric_snapshot,
    compare_metric_snapshots,
)


def _selected_keys(keys: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(keys or CORE_RESULT_METRICS)


def compare_overviews(
    overview_a: dict[str, Any],
    overview_b: dict[str, Any],
    keys: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    return compare_results({"overview": overview_a}, {"overview": overview_b}, keys=keys)


def compare_results(
    result_a: Mapping[str, Any] | None,
    result_b: Mapping[str, Any] | None,
    keys: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    metric_keys = _selected_keys(keys)
    snapshot_a = build_metric_snapshot(result_a, metric_keys)
    snapshot_b = build_metric_snapshot(result_b, metric_keys)
    return compare_metric_snapshots(snapshot_a, snapshot_b, metric_keys)


__all__ = ["compare_overviews", "compare_results"]
