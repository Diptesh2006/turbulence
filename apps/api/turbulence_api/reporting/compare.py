from __future__ import annotations

from typing import Any

from turbulence_api.reporting.models import MetricDifference, MetricsSnapshot, RunComparison


class CompareRunsService:
    COMPARED_METRICS = {
        "resilience_score",
        "availability_percentage",
        "overall_correctness_rate",
        "schema_valid_response_rate",
        "p95_end_to_end_latency_ms",
        "p50_end_to_end_latency_ms",
        "time_to_recovery_ms",
        "fallback_recovery_rate",
        "successful_requests",
        "failed_requests",
        "real_error_count",
        "simulated_error_count",
        "total_cost",
        "cost_per_successful_request",
    }
    HIGHER_IS_BETTER = {
        "resilience_score",
        "availability_percentage",
        "overall_correctness_rate",
        "schema_valid_response_rate",
        "fallback_recovery_rate",
        "successful_requests",
    }
    LOWER_IS_BETTER = {
        "p95_end_to_end_latency_ms",
        "p50_end_to_end_latency_ms",
        "time_to_recovery_ms",
        "failed_requests",
        "real_error_count",
        "simulated_error_count",
        "total_cost",
        "cost_per_successful_request",
    }

    def compare(
        self,
        baseline: MetricsSnapshot,
        candidate: MetricsSnapshot,
    ) -> RunComparison:
        differences: dict[str, MetricDifference] = {}
        baseline_data = baseline.model_dump()
        candidate_data = candidate.model_dump()
        baseline_data["resilience_score"] = baseline.resilience_score.score
        candidate_data["resilience_score"] = candidate.resilience_score.score
        for key in sorted(self.COMPARED_METRICS):
            before = baseline_data.get(key)
            after = candidate_data.get(key)
            if isinstance(before, dict) or isinstance(after, dict):
                continue
            differences[key] = _difference(before, after, _direction(key))
        return RunComparison(
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            differences=differences,
        )


def _difference(before: Any, after: Any, direction: str) -> MetricDifference:
    absolute = None
    percentage = None
    change_kind = "no_data"
    if _is_number(before) and _is_number(after):
        absolute = after - before
        if before != 0:
            percentage = absolute / before * 100
        change_kind = _change_kind(absolute, direction)
    return MetricDifference(
        before=before,
        after=after,
        absolute_difference=absolute,
        percentage_difference=percentage,
        direction=direction,
        change_kind=change_kind,
    )


def _direction(key: str) -> str:
    if key in CompareRunsService.HIGHER_IS_BETTER:
        return "higher_is_better"
    if key in CompareRunsService.LOWER_IS_BETTER:
        return "lower_is_better"
    return "neutral"


def _change_kind(absolute: float, direction: str) -> str:
    if absolute == 0 or direction == "neutral":
        return "no_change"
    if direction == "higher_is_better":
        return "improvement" if absolute > 0 else "regression"
    if direction == "lower_is_better":
        return "improvement" if absolute < 0 else "regression"
    return "no_change"


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
