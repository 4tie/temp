from __future__ import annotations

from typing import Any, Mapping

from app.services.results.metric_registry import (
    CORE_RESULT_METRICS,
    build_metric_snapshot,
    compare_metric_snapshots,
)

CORE_COMPARISON_KEYS = list(CORE_RESULT_METRICS)


def compare_overviews(
    overview_a: dict[str, Any],
    overview_b: dict[str, Any],
    keys: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    return compare_results({"overview": overview_a}, {"overview": overview_b}, keys=keys)


def compare_results(
    result_a: Mapping[str, Any] | None,
    result_b: Mapping[str, Any] | None,
    keys: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    snapshot_a = build_metric_snapshot(result_a, keys or CORE_COMPARISON_KEYS)
    snapshot_b = build_metric_snapshot(result_b, keys or CORE_COMPARISON_KEYS)
    return compare_metric_snapshots(snapshot_a, snapshot_b, keys or CORE_COMPARISON_KEYS)


__all__ = ["CORE_COMPARISON_KEYS", "compare_overviews", "compare_results"]
