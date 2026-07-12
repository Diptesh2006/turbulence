from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Any

from turbulence_api.reporting.models import (
    MetricsSnapshot,
    ResilienceComponentScore,
    ResilienceScore,
    TokenTotals,
)
from turbulence_api.simulation.events import SimulationEvent
from turbulence_api.simulation.models import AttemptRecord, RequestRecord, SimulationRun


class MetricsAggregator:
    def snapshot(
        self,
        run: SimulationRun,
        events: list[SimulationEvent] | None = None,
    ) -> MetricsSnapshot:
        events = events or []
        total_requests = run.metrics.total_requests or len(run.requests)
        total_attempts = sum(len(request.attempts) for request in run.requests)
        successful_requests = sum(1 for request in run.requests if request.state == "completed")
        failed_requests = sum(1 for request in run.requests if request.state == "failed")
        fallback_triggered = [request for request in run.requests if _has_fallback_attempt(request)]
        fallback_successes = [
            request for request in fallback_triggered if request.state == "completed"
        ]
        validations = [_score(request) for request in run.requests if _score(request) is not None]
        schema_valid = [score for score in validations if score.get("schema_valid") is True]

        e2e_latencies = _request_latencies(events)
        upstream_latencies = [
            attempt.upstream_latency_ms
            for request in run.requests
            for attempt in request.attempts
            if attempt.upstream_latency_ms is not None
        ]
        injected_latencies = [
            attempt.injected_latency_ms
            for request in run.requests
            for attempt in request.attempts
            if attempt.injected_latency_ms
        ]
        token_totals = _token_totals(_attempts(run))
        total_cost = _sum_optional(attempt.cost_total for attempt in _attempts(run))
        time_to_recovery_ms = _time_to_recovery_ms(run, events)

        snapshot = MetricsSnapshot(
            run_id=run.id,
            total_logical_requests=total_requests,
            total_attempts=total_attempts,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            availability_percentage=_percent(successful_requests, total_requests),
            fallback_triggered_requests=len(fallback_triggered),
            successful_fallback_recoveries=len(fallback_successes),
            fallback_recovery_rate=_percent(len(fallback_successes), len(fallback_triggered)),
            retry_count=sum(max(0, len(request.attempts) - 1) for request in run.requests),
            real_error_count=_real_error_count(run),
            simulated_error_count=_simulated_error_count(run),
            schema_valid_response_rate=_percent(len(schema_valid), len(validations)),
            category_accuracy=_score_percent(schema_valid, "category_correct"),
            priority_accuracy=_score_percent(schema_valid, "priority_correct"),
            overall_correctness_rate=_score_percent(validations, "overall_correct"),
            p50_end_to_end_latency_ms=_percentile(e2e_latencies, 50),
            p95_end_to_end_latency_ms=_percentile(e2e_latencies, 95),
            p50_upstream_latency_ms=_percentile(upstream_latencies, 50),
            p95_upstream_latency_ms=_percentile(upstream_latencies, 95),
            total_injected_latency_ms=sum(injected_latencies) if injected_latencies else None,
            tokens=token_totals,
            mock_response_count=_mock_response_count(run, events),
            total_cost=total_cost,
            cost_per_successful_request=(
                total_cost / successful_requests
                if total_cost is not None and successful_requests > 0
                else None
            ),
            time_to_recovery_ms=time_to_recovery_ms,
            requests_by_actual_model_provider=_requests_by_actual_model_provider(run),
            error_distribution_by_type=_error_distribution(run),
            route_attempt_distribution=_route_attempt_distribution(run),
            resilience_score=ResilienceScore(score=None, components=[]),
        )
        snapshot.resilience_score = _resilience_score(run, snapshot)
        return snapshot


def _attempts(run: SimulationRun) -> list[AttemptRecord]:
    return [attempt for request in run.requests for attempt in request.attempts]


def _score(request: RequestRecord) -> dict[str, Any] | None:
    if not request.validation_result:
        return None
    score = request.validation_result.get("score")
    return score if isinstance(score, dict) else None


def _has_fallback_attempt(request: RequestRecord) -> bool:
    return any(attempt.simulator_managed_fallback for attempt in request.attempts)


def _percent(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator * 100


def _score_percent(scores: list[dict[str, Any]], key: str) -> float | None:
    if not scores:
        return None
    return _percent(sum(1 for score in scores if score.get(key) is True), len(scores))


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    rank = math.ceil(percentile / 100 * len(sorted_values)) - 1
    return sorted_values[max(0, min(rank, len(sorted_values) - 1))]


def _sum_optional(values) -> int | float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _token_totals(attempts: list[AttemptRecord]) -> TokenTotals:
    return TokenTotals(
        input_tokens=_sum_optional(attempt.input_tokens for attempt in attempts),
        output_tokens=_sum_optional(attempt.output_tokens for attempt in attempts),
        total_tokens=_sum_optional(attempt.total_tokens for attempt in attempts),
    )


def _mock_response_count(
    run: SimulationRun,
    events: list[SimulationEvent],
) -> int | None:
    event_mock_values = [
        event.payload.get("is_mock")
        for event in events
        if event.type == "gateway.response_received"
    ]
    if any(value is True for value in event_mock_values):
        return sum(1 for value in event_mock_values if value is True)

    attempts = _attempts(run)
    explicit_provider_count = sum(
        1 for attempt in attempts if attempt.actual_provider == "mock" or attempt.provider == "mock"
    )
    if explicit_provider_count:
        return explicit_provider_count
    if event_mock_values or any(
        attempt.actual_provider is not None or attempt.provider is not None for attempt in attempts
    ):
        return 0
    return None


def _real_error_count(run: SimulationRun) -> int:
    return sum(1 for attempt in _attempts(run) if attempt.errors)


def _simulated_error_count(run: SimulationRun) -> int:
    count = 0
    for attempt in _attempts(run):
        count += sum(
            1
            for provenance in attempt.fault_provenance
            if provenance.simulated_status_code is not None or provenance.corrupted_response
        )
    return count


def _request_latencies(events: list[SimulationEvent]) -> list[float]:
    queued_at: dict[str, datetime] = {}
    latencies: list[float] = []
    for event in events:
        request_id = event.payload.get("request_id")
        if not isinstance(request_id, str):
            continue
        if event.type == "request.queued":
            queued_at[request_id] = event.timestamp
        elif event.type == "request.completed" and request_id in queued_at:
            delta = event.timestamp - queued_at[request_id]
            latencies.append(delta.total_seconds() * 1000)
    return latencies


def _time_to_recovery_ms(run: SimulationRun, events: list[SimulationEvent]) -> float | None:
    first_fault = next((event for event in events if event.type == "fault.activated"), None)
    if first_fault is None:
        return None

    fallback_request_ids = {
        event.payload.get("request_id")
        for event in events
        if event.type == "fallback.started" and isinstance(event.payload.get("request_id"), str)
    }
    successful_request_ids = {
        request.id for request in run.requests if request.state == "completed"
    }
    for event in events:
        request_id = event.payload.get("request_id")
        if (
            event.sequence > first_fault.sequence
            and event.type == "request.completed"
            and request_id in fallback_request_ids
            and request_id in successful_request_ids
        ):
            return (event.timestamp - first_fault.timestamp).total_seconds() * 1000
    return None


def _requests_by_actual_model_provider(run: SimulationRun) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for request in run.requests:
        completed = next((a for a in request.attempts if a.validation_passed is True), None)
        if completed is None:
            continue
        model = completed.actual_model or completed.model
        provider = completed.actual_provider or completed.provider or "unknown"
        counts[f"{model}/{provider}"] += 1
    return dict(counts)


def _error_distribution(run: SimulationRun) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for attempt in _attempts(run):
        for provenance in attempt.fault_provenance:
            if provenance.simulated_status_code is not None or provenance.corrupted_response:
                counts[f"simulated.{provenance.type}"] += 1
        if attempt.simulated_status_code is not None:
            counts[f"simulated.http_{attempt.simulated_status_code}"] += 1
        if attempt.errors:
            counts["real.gateway_error"] += len(attempt.errors)
        if attempt.validation_passed is False:
            counts["validation.failed"] += 1
    return dict(counts)


def _route_attempt_distribution(run: SimulationRun) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for attempt in _attempts(run):
        provider = attempt.provider or "unspecified"
        counts[f"{attempt.index}:{attempt.model}/{provider}"] += 1
    return dict(counts)


def _resilience_score(run: SimulationRun, snapshot: MetricsSnapshot) -> ResilienceScore:
    components = [
        _availability_component(snapshot),
        _recovery_component(run, snapshot),
        _fallback_component(snapshot),
        _correctness_component(snapshot),
        _latency_component(run, snapshot),
    ]
    applicable = [component for component in components if not component.excluded]
    if not applicable:
        return ResilienceScore(
            score=None,
            components=components,
            excluded_components=[component.name for component in components],
        )
    earned = sum(component.earned_points or 0 for component in applicable)
    possible = sum(component.max_points for component in applicable)
    return ResilienceScore(
        score=earned / possible * 100,
        components=components,
        excluded_components=[component.name for component in components if component.excluded],
    )


def _availability_component(snapshot: MetricsSnapshot) -> ResilienceComponentScore:
    if snapshot.availability_percentage is None:
        return _excluded("availability", 30, "no logical requests")
    return ResilienceComponentScore(
        name="availability",
        max_points=30,
        earned_points=snapshot.availability_percentage / 100 * 30,
    )


def _recovery_component(
    run: SimulationRun,
    snapshot: MetricsSnapshot,
) -> ResilienceComponentScore:
    if run.scenario.recovery_time_slo_ms is None:
        return _excluded("recovery_time", 20, "recovery-time SLO is not configured")
    if snapshot.time_to_recovery_ms is None:
        return _excluded("recovery_time", 20, "no measured fallback recovery after a fault")
    ratio = (
        1.0
        if snapshot.time_to_recovery_ms <= run.scenario.recovery_time_slo_ms
        else run.scenario.recovery_time_slo_ms / snapshot.time_to_recovery_ms
    )
    return ResilienceComponentScore(
        name="recovery_time",
        max_points=20,
        earned_points=max(0.0, min(1.0, ratio)) * 20,
    )


def _fallback_component(snapshot: MetricsSnapshot) -> ResilienceComponentScore:
    if snapshot.fallback_recovery_rate is None:
        return _excluded("fallback_recovery", 20, "no fallback-triggered requests")
    return ResilienceComponentScore(
        name="fallback_recovery",
        max_points=20,
        earned_points=snapshot.fallback_recovery_rate / 100 * 20,
    )


def _correctness_component(snapshot: MetricsSnapshot) -> ResilienceComponentScore:
    if snapshot.overall_correctness_rate is None:
        return _excluded("correctness", 15, "no validated responses")
    return ResilienceComponentScore(
        name="correctness",
        max_points=15,
        earned_points=snapshot.overall_correctness_rate / 100 * 15,
    )


def _latency_component(
    run: SimulationRun,
    snapshot: MetricsSnapshot,
) -> ResilienceComponentScore:
    if run.scenario.latency_slo_ms is None:
        return _excluded("p95_latency", 15, "latency SLO is not configured")
    if snapshot.p95_end_to_end_latency_ms is None:
        return _excluded("p95_latency", 15, "no completed request latency")
    ratio = (
        1.0
        if snapshot.p95_end_to_end_latency_ms <= run.scenario.latency_slo_ms
        else run.scenario.latency_slo_ms / snapshot.p95_end_to_end_latency_ms
    )
    return ResilienceComponentScore(
        name="p95_latency",
        max_points=15,
        earned_points=max(0.0, min(1.0, ratio)) * 15,
    )


def _excluded(name: str, max_points: float, reason: str) -> ResilienceComponentScore:
    return ResilienceComponentScore(
        name=name,
        max_points=max_points,
        earned_points=None,
        excluded=True,
        reason=reason,
    )
