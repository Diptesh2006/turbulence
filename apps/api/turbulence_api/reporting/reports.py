from __future__ import annotations

from collections import Counter
from typing import Any

from turbulence_api.reporting.metrics import MetricsAggregator
from turbulence_api.reporting.models import (
    AiIncidentAnalysis,
    DeterministicRecommendation,
    ExecutiveVerdict,
    FailureAnalysis,
    IncidentTimelineItem,
    MetricsSnapshot,
    PostFlightReport,
    RouteAnalysisItem,
)
from turbulence_api.simulation.events import SimulationEvent
from turbulence_api.simulation.models import AttemptRecord, SimulationRun

TARGET_AVAILABILITY_PERCENTAGE = 99.0
TARGET_CORRECTNESS_RATE = 95.0
UNRELIABLE_AVAILABILITY_MARGIN = 5.0


class PostFlightReportService:
    def __init__(self, metrics_aggregator: MetricsAggregator | None = None) -> None:
        self._metrics_aggregator = metrics_aggregator or MetricsAggregator()

    def create_report(
        self,
        run: SimulationRun,
        events: list[SimulationEvent] | None = None,
    ) -> PostFlightReport:
        events = sorted(events or [], key=lambda event: event.sequence)
        metrics = self._metrics_aggregator.snapshot(run, events)
        return PostFlightReport(
            run_id=run.id,
            scenario_id=run.scenario.id,
            run_state=run.state,
            mode=run.scenario.mode,
            created_at=run.created_at.isoformat(),
            updated_at=run.updated_at.isoformat(),
            executive_verdict=_executive_verdict(run, metrics),
            metrics=metrics,
            incident_timeline=_incident_timeline(run, events),
            route_analysis=_route_analysis(run),
            failure_analysis=_failure_analysis(metrics),
            recommendations=_recommendations(run, metrics),
            ai_analysis=AiIncidentAnalysis(
                available=False,
                generated=False,
                label="AI-generated analysis unavailable in deterministic local report",
            ),
        )


def _executive_verdict(
    run: SimulationRun,
    metrics: MetricsSnapshot,
) -> ExecutiveVerdict:
    if run.state == "cancelled":
        return _verdict("inconclusive", "The run was cancelled before a full outcome was measured.")
    if run.state == "failed" or run.error:
        return _verdict("unreliable", "The run ended with a fatal orchestration error.")
    if (
        metrics.availability_percentage is None
        or metrics.overall_correctness_rate is None
        or metrics.successful_requests == 0
    ):
        return _verdict(
            "inconclusive",
            "Required metrics are missing or no logical request completed successfully.",
        )

    if (
        metrics.availability_percentage
        < TARGET_AVAILABILITY_PERCENTAGE - UNRELIABLE_AVAILABILITY_MARGIN
        or metrics.overall_correctness_rate < TARGET_CORRECTNESS_RATE
    ):
        return _verdict(
            "unreliable",
            "Availability or correctness is materially below the configured report threshold.",
        )

    degraded = (
        metrics.failed_requests > 0
        or metrics.fallback_triggered_requests > 0
        or metrics.failed_requests > 0
        or metrics.simulated_error_count > 0
        or metrics.real_error_count > 0
        or metrics.schema_valid_response_rate not in {None, 100}
        or _latency_degraded(run, metrics)
    )
    if (
        run.state == "completed"
        and metrics.availability_percentage >= TARGET_AVAILABILITY_PERCENTAGE
        and metrics.overall_correctness_rate >= TARGET_CORRECTNESS_RATE
        and not run.error
        and not degraded
    ):
        return _verdict("production_ready", "The run met availability and correctness thresholds.")

    if run.state == "completed" and metrics.availability_percentage > 0 and degraded:
        return _verdict(
            "degraded_but_recovered",
            "The run completed but measured degradation, fallback, fault, or "
            "validation signals occurred.",
        )

    return _verdict("inconclusive", "The run completed but does not fit a stronger verdict.")


def _verdict(verdict: str, explanation: str) -> ExecutiveVerdict:
    return ExecutiveVerdict(
        verdict=verdict,
        explanation=explanation,
        target_availability_percentage=TARGET_AVAILABILITY_PERCENTAGE,
        target_correctness_rate=TARGET_CORRECTNESS_RATE,
    )


def _latency_degraded(run: SimulationRun, metrics: MetricsSnapshot) -> bool:
    return (
        run.scenario.latency_slo_ms is not None
        and metrics.p95_end_to_end_latency_ms is not None
        and metrics.p95_end_to_end_latency_ms > run.scenario.latency_slo_ms
    )


def _incident_timeline(
    run: SimulationRun,
    events: list[SimulationEvent],
) -> list[IncidentTimelineItem]:
    selected: list[SimulationEvent] = []
    selected.extend(event for event in events if event.type == "fault.activated")
    first_affected = next(
        (
            event
            for event in events
            if event.type == "fault.injected"
            or (
                event.type == "attempt.completed"
                and event.payload.get("simulated_status_code") is not None
            )
        ),
        None,
    )
    if first_affected is not None:
        selected.append(first_affected)
    selected.extend(event for event in events if event.type == "fallback.started")
    recovery = _recovery_event(run, events)
    if recovery is not None:
        selected.append(recovery)
    selected.extend(event for event in events if event.type == "fault.cleared")
    terminal = next(
        (
            event
            for event in events
            if event.type in {"run.completed", "run.failed", "run.cancelled"}
        ),
        None,
    )
    if terminal is not None:
        selected.append(terminal)

    deduped = {event.sequence: event for event in selected}
    return [
        IncidentTimelineItem(
            sequence=event.sequence,
            timestamp=event.timestamp.isoformat(),
            event_type=event.type,
            source=_timeline_source(event),
            label=_timeline_label(event),
            request_id=_str_payload(event.payload, "request_id"),
            route_index=_int_payload(event.payload, "route_index"),
            payload=_sanitized_payload(event.payload),
        )
        for event in sorted(deduped.values(), key=lambda item: item.sequence)
    ]


def _timeline_source(event: SimulationEvent):
    if event.type == "gateway.response_received" and event.payload.get("is_mock") is True:
        return "mock"
    return event.source


def _timeline_label(event: SimulationEvent) -> str:
    labels = {
        "fault.activated": "Simulated fault activated",
        "fault.injected": "Simulated fault affected an attempt",
        "fallback.started": "Simulator-managed fallback started",
        "request.completed": "Request recovered after fallback",
        "fault.cleared": "Simulated fault cleared",
        "run.completed": "Run completed",
        "run.failed": "Run failed",
        "run.cancelled": "Run cancelled",
        "attempt.completed": "Attempt completed with simulated status",
    }
    return labels.get(event.type, event.type)


def _sanitized_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "rule_id",
        "message",
        "request_id",
        "attempt_id",
        "route_index",
        "model",
        "provider",
        "label",
        "state",
        "simulated_status_code",
        "metrics",
        "provenance",
    }
    return {key: value for key, value in payload.items() if key in allowed}


def _recovery_event(
    run: SimulationRun,
    events: list[SimulationEvent],
) -> SimulationEvent | None:
    fallback_request_ids = {
        _str_payload(event.payload, "request_id")
        for event in events
        if event.type == "fallback.started"
    }
    successful_request_ids = {
        request.id for request in run.requests if request.state == "completed"
    }
    return next(
        (
            event
            for event in events
            if event.type == "request.completed"
            and _str_payload(event.payload, "request_id") in fallback_request_ids
            and _str_payload(event.payload, "request_id") in successful_request_ids
        ),
        None,
    )


def _route_analysis(run: SimulationRun) -> list[RouteAnalysisItem]:
    grouped: dict[int, list[AttemptRecord]] = {}
    for request in run.requests:
        for attempt in request.attempts:
            grouped.setdefault(attempt.index, []).append(attempt)

    concentrate_native = run.scenario.routing_profile.type == "gateway_auto"
    items: list[RouteAnalysisItem] = []
    for route_index, attempts in sorted(grouped.items()):
        first = attempts[0]
        successes = sum(1 for attempt in attempts if attempt.validation_passed is True)
        failures = sum(
            1
            for attempt in attempts
            if attempt.state in {"failed", "blocked", "abandoned"}
            or attempt.validation_passed is False
        )
        fallback_usage = sum(1 for attempt in attempts if attempt.simulator_managed_fallback)
        items.append(
            RouteAnalysisItem(
                route_index=route_index,
                requested_model=first.model,
                requested_provider=first.provider,
                actual_model=_most_common(attempt.actual_model for attempt in attempts),
                actual_provider=_most_common(attempt.actual_provider for attempt in attempts),
                attempts=len(attempts),
                successes=successes,
                failures=failures,
                fallback_usage=fallback_usage,
                simulator_managed_fallback=any(
                    attempt.simulator_managed_fallback for attempt in attempts
                ),
                concentrate_native=concentrate_native,
            )
        )
    return items


def _failure_analysis(metrics: MetricsSnapshot) -> FailureAnalysis:
    distribution = metrics.error_distribution_by_type
    simulated_failures = sum(
        count for key, count in distribution.items() if key.startswith("simulated.")
    )
    validation_failures = distribution.get("validation.failed", 0)
    real_failures = sum(count for key, count in distribution.items() if key.startswith("real."))
    classified = simulated_failures + validation_failures + real_failures
    return FailureAnalysis(
        real_failures=real_failures,
        simulated_failures=simulated_failures,
        validation_failures=validation_failures,
        rate_limits=distribution.get("simulated.rate_limit_burst", 0)
        + distribution.get("simulated.http_429", 0),
        timeouts=distribution.get("real.timeout", 0),
        malformed_json=distribution.get("simulated.malformed_json", 0),
        provider_outage_injections=distribution.get("simulated.provider_outage", 0),
        unknown_unclassified_errors=max(
            0,
            metrics.real_error_count + metrics.simulated_error_count - classified,
        ),
        distribution=distribution,
    )


def _recommendations(
    run: SimulationRun,
    metrics: MetricsSnapshot,
) -> list[DeterministicRecommendation]:
    recommendations: list[DeterministicRecommendation] = []
    if metrics.fallback_triggered_requests and metrics.fallback_recovery_rate == 100:
        recommendations.append(
            _recommendation(
                "fallback_recovered_successfully",
                "Simulated provider outage was recovered through fallback routing. "
                "Keep the fallback path, but continue monitoring recovery time and "
                "fallback capacity.",
            )
        )
    if metrics.simulated_error_count > 0:
        recommendations.append(
            _recommendation(
                "simulated_faults_present",
                "Simulated provider failures occurred; confirm that production "
                "alerting distinguishes simulated/client-boundary tests from real "
                "provider incidents.",
            )
        )
    if _latency_degraded(run, metrics):
        recommendations.append(
            _recommendation(
                "latency_slo_exceeded",
                "p95 latency exceeded the configured SLO; lower concurrency, "
                "adjust the route, or add a fallback with better latency.",
            )
        )
    if metrics.fallback_triggered_requests and (
        metrics.fallback_recovery_rate is None or metrics.fallback_recovery_rate < 100
    ):
        recommendations.append(
            _recommendation(
                "fallback_recovery_poor",
                "Fallback recovery was incomplete; add another fallback route or "
                "review simulator-managed fallback ordering.",
            )
        )
    if metrics.schema_valid_response_rate is not None and metrics.schema_valid_response_rate < 100:
        recommendations.append(
            _recommendation(
                "schema_validity_low",
                "Structured-output schema validity degraded; keep strict validation "
                "and consider retrying with a tighter schema instruction.",
            )
        )
    if "simulated.rate_limit_burst" in metrics.error_distribution_by_type:
        recommendations.append(
            _recommendation(
                "simulated_rate_limits",
                "Simulated rate limits occurred; add retry budget, jittered backoff, "
                "and route-level rate-limit handling.",
            )
        )
    if (
        metrics.overall_correctness_rate is not None
        and metrics.overall_correctness_rate < TARGET_CORRECTNESS_RATE
    ):
        recommendations.append(
            _recommendation(
                "correctness_low",
                "Correctness is below threshold; revise the workload prompt or "
                "change the model route.",
            )
        )
    if metrics.total_cost is None:
        recommendations.append(
            _recommendation(
                "cost_unknown",
                "Cost optimization cannot be evaluated because the gateway did not "
                "return cost data.",
            )
        )
    if _baseline_healthy(run, metrics):
        recommendations.append(
            _recommendation(
                "baseline_healthy",
                "No deterministic reliability issues were detected; keep this run "
                "as a baseline for future comparisons.",
            )
        )
    return recommendations


def _baseline_healthy(run: SimulationRun, metrics: MetricsSnapshot) -> bool:
    return (
        metrics.simulated_error_count == 0
        and metrics.real_error_count == 0
        and metrics.failed_requests == 0
        and metrics.fallback_triggered_requests == 0
        and metrics.error_distribution_by_type.get("validation.failed", 0) == 0
        and not _latency_degraded(run, metrics)
        and (
            metrics.overall_correctness_rate is not None
            and metrics.overall_correctness_rate >= TARGET_CORRECTNESS_RATE
        )
        and metrics.schema_valid_response_rate in {None, 100}
    )


def _recommendation(code: str, message: str) -> DeterministicRecommendation:
    return DeterministicRecommendation(code=code, message=message)


def _most_common(values) -> str | None:
    present = [value for value in values if value]
    if not present:
        return None
    return Counter(present).most_common(1)[0][0]


def _str_payload(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _int_payload(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    return value if isinstance(value, int) else None
