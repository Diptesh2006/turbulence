from __future__ import annotations

from typing import Any

from turbulence_api.reporting.models import MetricDifference, MetricsSnapshot, RunComparison


class CompareRunsService:
    def compare(
        self,
        baseline: MetricsSnapshot,
        candidate: MetricsSnapshot,
    ) -> RunComparison:
        differences: dict[str, MetricDifference] = {}
        baseline_data = baseline.model_dump()
        candidate_data = candidate.model_dump()
        for key, before in baseline_data.items():
            if key in {"run_id", "resilience_score"}:
                continue
            after = candidate_data.get(key)
            if isinstance(before, dict) or isinstance(after, dict):
                continue
            differences[key] = _difference(before, after)
        return RunComparison(
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            differences=differences,
        )


def _difference(before: Any, after: Any) -> MetricDifference:
    absolute = None
    percentage = None
    if _is_number(before) and _is_number(after):
        absolute = after - before
        if before != 0:
            percentage = absolute / before * 100
    return MetricDifference(
        before=before,
        after=after,
        absolute_difference=absolute,
        percentage_difference=percentage,
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)

