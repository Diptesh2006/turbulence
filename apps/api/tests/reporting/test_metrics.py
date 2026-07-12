from __future__ import annotations

from datetime import UTC, datetime, timedelta

from turbulence_api.domain.faults import FaultProvenance
from turbulence_api.domain.routing import RouteTarget, RoutingProfile
from turbulence_api.reporting.compare import CompareRunsService
from turbulence_api.reporting.metrics import MetricsAggregator
from turbulence_api.reporting.reports import PostFlightReportService
from turbulence_api.simulation.events import SimulationEvent
from turbulence_api.simulation.models import (
    AttemptRecord,
    RequestRecord,
    ScenarioConfig,
    SimulationRun,
)


def test_empty_run_keeps_unknown_rates_null() -> None:
    run = _run("empty")

    snapshot = MetricsAggregator().snapshot(run, [])

    assert snapshot.total_logical_requests == 0
    assert snapshot.availability_percentage is None
    assert snapshot.schema_valid_response_rate is None
    assert snapshot.total_cost is None
    assert snapshot.tokens.total_tokens is None
    assert snapshot.resilience_score.score is None


def test_partial_run_does_not_interpret_missing_upstream_values_as_zero() -> None:
    run = _run("partial")
    run.metrics.total_requests = 1
    run.requests.append(
        RequestRecord(
            id="req-1",
            fixture_id="stt-001",
            state="running",
            attempts=[
                AttemptRecord(
                    request_id="req-1",
                    index=0,
                    model="mock-fast",
                    provider="mock",
                    state="started",
                )
            ],
        )
    )

    snapshot = MetricsAggregator().snapshot(run, [])

    assert snapshot.total_logical_requests == 1
    assert snapshot.successful_requests == 0
    assert snapshot.availability_percentage == 0
    assert snapshot.p50_upstream_latency_ms is None
    assert snapshot.total_cost is None
    assert snapshot.cost_per_successful_request is None


def test_successful_run_metrics_and_report() -> None:
    run = _run("success", latency_slo_ms=500)
    run.metrics.total_requests = 1
    run.requests.append(_successful_request("req-1", upstream_latency_ms=25))
    events = _request_events(run.id, "req-1", duration_ms=100)

    snapshot = MetricsAggregator().snapshot(run, events)
    report = PostFlightReportService().create_report(run, events)

    assert snapshot.total_attempts == 1
    assert snapshot.successful_requests == 1
    assert snapshot.availability_percentage == 100
    assert snapshot.schema_valid_response_rate == 100
    assert snapshot.category_accuracy == 100
    assert snapshot.priority_accuracy == 100
    assert snapshot.overall_correctness_rate == 100
    assert snapshot.p50_end_to_end_latency_ms == 100
    assert snapshot.p95_upstream_latency_ms == 25
    assert snapshot.tokens.input_tokens == 10
    assert snapshot.tokens.output_tokens == 5
    assert snapshot.tokens.total_tokens == 15
    assert snapshot.total_cost == 0.03
    assert snapshot.cost_per_successful_request == 0.03
    assert snapshot.requests_by_actual_model_provider == {"mock-fast/mock": 1}
    assert report.metrics.run_id == run.id


def test_degraded_run_tracks_fallback_recovery_and_resilience_reweighting() -> None:
    run = _run("degraded", recovery_time_slo_ms=1000, latency_slo_ms=1000)
    run.metrics.total_requests = 1
    request = _successful_request("req-1", upstream_latency_ms=30)
    request.attempts.insert(
        0,
        AttemptRecord(
            request_id="req-1",
            index=0,
            model="primary",
            provider="primary",
            state="blocked",
            simulated_status_code=424,
            fault_provenance=[
                FaultProvenance(
                    rule_id="outage",
                    type="provider_outage",
                    target_provider="primary",
                    simulated_status_code=424,
                )
            ],
        ),
    )
    request.attempts[1].index = 1
    request.attempts[1].simulator_managed_fallback = True
    run.requests.append(request)
    events = _fallback_events(run.id, "req-1", recovery_ms=250)

    snapshot = MetricsAggregator().snapshot(run, events)

    assert snapshot.fallback_triggered_requests == 1
    assert snapshot.successful_fallback_recoveries == 1
    assert snapshot.fallback_recovery_rate == 100
    assert snapshot.retry_count == 1
    assert snapshot.simulated_error_count == 1
    assert snapshot.real_error_count == 0
    assert snapshot.time_to_recovery_ms == 250
    assert snapshot.error_distribution_by_type["simulated.provider_outage"] == 1
    assert snapshot.error_distribution_by_type["simulated.http_424"] == 1
    assert snapshot.route_attempt_distribution["0:primary/primary"] == 1
    assert snapshot.route_attempt_distribution["1:mock-fast/mock"] == 1
    assert snapshot.resilience_score.score == 100


def test_completely_failed_run_metrics() -> None:
    run = _run("failed")
    run.metrics.total_requests = 1
    run.requests.append(
        RequestRecord(
            id="req-1",
            fixture_id="stt-001",
            state="failed",
            attempts=[
                AttemptRecord(
                    request_id="req-1",
                    index=0,
                    model="primary",
                    provider="primary",
                    state="blocked",
                    simulated_status_code=424,
                    fault_provenance=[
                        FaultProvenance(
                            rule_id="outage",
                            type="provider_outage",
                            simulated_status_code=424,
                        )
                    ],
                )
            ],
        )
    )

    snapshot = MetricsAggregator().snapshot(run, [])

    assert snapshot.failed_requests == 1
    assert snapshot.availability_percentage == 0
    assert snapshot.fallback_recovery_rate is None
    assert snapshot.schema_valid_response_rate is None
    assert snapshot.simulated_error_count == 1
    assert snapshot.total_cost is None


def test_compare_runs_returns_absolute_and_percentage_differences() -> None:
    baseline = MetricsAggregator().snapshot(
        _run_with_requests("baseline", successful=1, failed=1),
        [],
    )
    candidate = MetricsAggregator().snapshot(
        _run_with_requests("candidate", successful=2, failed=0),
        [],
    )

    comparison = CompareRunsService().compare(baseline, candidate)

    assert comparison.differences["successful_requests"].absolute_difference == 1
    assert comparison.differences["successful_requests"].percentage_difference == 100
    assert comparison.differences["failed_requests"].absolute_difference == -1


def _run(
    run_id: str,
    *,
    recovery_time_slo_ms: int | None = None,
    latency_slo_ms: int | None = None,
) -> SimulationRun:
    return SimulationRun(
        id=run_id,
        scenario=ScenarioConfig(
            id=f"scenario-{run_id}",
            request_count=1,
            recovery_time_slo_ms=recovery_time_slo_ms,
            latency_slo_ms=latency_slo_ms,
            routing_profile=RoutingProfile.single_provider(
                id="single",
                route=RouteTarget(model="mock-fast", provider="mock"),
            ),
        ),
    )


def _successful_request(request_id: str, *, upstream_latency_ms: float) -> RequestRecord:
    return RequestRecord(
        id=request_id,
        fixture_id="stt-001",
        state="completed",
        validation_result={
            "score": {
                "schema_valid": True,
                "category_correct": True,
                "priority_correct": True,
                "summary_keyword_coverage": 1.0,
                "overall_correct": True,
            }
        },
        attempts=[
            AttemptRecord(
                request_id=request_id,
                index=0,
                model="mock-fast",
                provider="mock",
                actual_model="mock-fast",
                actual_provider="mock",
                state="completed",
                validation_passed=True,
                upstream_latency_ms=upstream_latency_ms,
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cost_total=0.03,
            )
        ],
    )


def _run_with_requests(run_id: str, *, successful: int, failed: int) -> SimulationRun:
    run = _run(run_id)
    run.metrics.total_requests = successful + failed
    for index in range(successful):
        run.requests.append(_successful_request(f"req-s-{index}", upstream_latency_ms=10))
    for index in range(failed):
        run.requests.append(
            RequestRecord(id=f"req-f-{index}", fixture_id="stt-001", state="failed")
        )
    return run


def _request_events(run_id: str, request_id: str, *, duration_ms: int) -> list[SimulationEvent]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        SimulationEvent(
            sequence=1,
            type="request.queued",
            source="system",
            timestamp=start,
            run_id=run_id,
            payload={"request_id": request_id},
        ),
        SimulationEvent(
            sequence=2,
            type="request.completed",
            source="system",
            timestamp=start + timedelta(milliseconds=duration_ms),
            run_id=run_id,
            payload={"request_id": request_id, "state": "completed"},
        ),
    ]


def _fallback_events(run_id: str, request_id: str, *, recovery_ms: int) -> list[SimulationEvent]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        SimulationEvent(
            sequence=1,
            type="fault.activated",
            source="simulated",
            timestamp=start,
            run_id=run_id,
            payload={"rule_id": "outage"},
        ),
        SimulationEvent(
            sequence=2,
            type="fallback.started",
            source="simulated",
            timestamp=start + timedelta(milliseconds=10),
            run_id=run_id,
            payload={"request_id": request_id},
        ),
        SimulationEvent(
            sequence=3,
            type="request.queued",
            source="system",
            timestamp=start,
            run_id=run_id,
            payload={"request_id": request_id},
        ),
        SimulationEvent(
            sequence=4,
            type="request.completed",
            source="system",
            timestamp=start + timedelta(milliseconds=recovery_ms),
            run_id=run_id,
            payload={"request_id": request_id, "state": "completed"},
        ),
    ]
