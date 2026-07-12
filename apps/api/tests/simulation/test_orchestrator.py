from __future__ import annotations

import asyncio

import pytest

from turbulence_api.core.config import Settings
from turbulence_api.domain.faults import FaultRule
from turbulence_api.domain.routing import RouteTarget, RoutingProfile
from turbulence_api.integrations.concentrate.mock import MockConcentrateClient
from turbulence_api.integrations.concentrate.models import ConcentrateResponseRequest
from turbulence_api.services.presets import build_seeded_presets
from turbulence_api.simulation.event_bus import EventBus
from turbulence_api.simulation.models import ScenarioConfig
from turbulence_api.simulation.orchestrator import SimulationOrchestrator
from turbulence_api.simulation.store import InMemoryRunStore


def orchestrator(client=None) -> SimulationOrchestrator:
    concentrate_client = client or MockConcentrateClient(seed=0)
    return SimulationOrchestrator(
        store=InMemoryRunStore(),
        event_bus=EventBus(),
        concentrate_client=concentrate_client,
        mock_concentrate_client=concentrate_client,
    )


def scenario(
    *,
    routing_profile: RoutingProfile,
    fault_rules: list[FaultRule] | None = None,
    seed: int = 7,
    request_count: int = 1,
    rate_per_second: float = 100,
    max_concurrency: int = 2,
    mode: str = "mock",
) -> ScenarioConfig:
    return ScenarioConfig(
        id="scenario-test",
        mode=mode,
        workload_name="support_ticket_triage",
        request_count=request_count,
        seed=seed,
        rate_per_second=rate_per_second,
        max_concurrency=max_concurrency,
        model="mock-fast",
        max_output_tokens=128,
        routing_profile=routing_profile,
        fault_rules=fault_rules or [],
    )


@pytest.mark.asyncio
async def test_successful_run() -> None:
    orch = orchestrator()
    run = await orch.run_to_completion(
        scenario(
            routing_profile=RoutingProfile.single_provider(
                id="single",
                route=RouteTarget(model="mock-fast", provider="mock"),
            )
        ),
        run_id="run-success",
    )

    events = await orch.replay_events_after(run.id, None)

    assert run.state == "completed"
    assert run.metrics.completed_requests == 1
    assert run.metrics.failed_requests == 0
    assert [event.type for event in events][-1] == "run.completed"
    assert "validation.passed" in [event.type for event in events]


@pytest.mark.asyncio
async def test_primary_failure_with_successful_fallback() -> None:
    orch = orchestrator()
    run = await orch.run_to_completion(
        scenario(
            routing_profile=RoutingProfile.resilient_route(
                id="resilient",
                routes=[
                    RouteTarget(model="mock-fast", provider="primary"),
                    RouteTarget(model="mock-fast", provider="fallback"),
                ],
            ),
            fault_rules=[
                FaultRule(
                    id="primary-outage",
                    type="provider_outage",
                    target_provider="primary",
                    start_after_ms=0,
                    duration_ms=10_000,
                    probability=1,
                )
            ],
        ),
        run_id="run-fallback",
    )

    events = await orch.replay_events_after(run.id, None)
    event_types = [event.type for event in events]
    attempts = run.requests[0].attempts

    assert run.state == "completed"
    assert attempts[0].state == "blocked"
    assert attempts[0].simulated_status_code == 424
    assert attempts[0].fault_provenance[0].source == "simulated"
    assert attempts[1].state == "completed"
    assert attempts[1].simulator_managed_fallback is True
    assert "fallback.started" in event_types
    assert "fault.injected" in event_types
    assert events[event_types.index("fallback.started")].source == "simulated"


@pytest.mark.asyncio
async def test_all_routes_failed() -> None:
    orch = orchestrator()
    run = await orch.run_to_completion(
        scenario(
            routing_profile=RoutingProfile.resilient_route(
                id="resilient",
                routes=[
                    RouteTarget(model="mock-fast", provider="primary"),
                    RouteTarget(model="mock-fast", provider="fallback"),
                ],
            ),
            fault_rules=[
                FaultRule(
                    id="all-outage",
                    type="provider_outage",
                    start_after_ms=0,
                    duration_ms=10_000,
                    probability=1,
                )
            ],
        ),
        run_id="run-all-failed",
    )

    events = await orch.replay_events_after(run.id, None)

    assert run.state == "completed"
    assert run.metrics.failed_requests == 1
    assert run.requests[0].state == "failed"
    assert all(attempt.state == "blocked" for attempt in run.requests[0].attempts)
    assert events[-1].type == "run.completed"


@pytest.mark.asyncio
async def test_request_validation_failure_completes_run_with_degraded_metrics() -> None:
    orch = orchestrator()
    run = await orch.run_to_completion(
        scenario(
            routing_profile=RoutingProfile.single_provider(
                id="single",
                route=RouteTarget(model="mock-fast", provider="mock"),
            ),
            fault_rules=[
                FaultRule(
                    id="bad-json",
                    type="malformed_json",
                    start_after_ms=0,
                    duration_ms=10_000,
                    probability=1,
                )
            ],
        ),
        run_id="run-validation-failure",
    )

    events = await orch.replay_events_after(run.id, None)

    assert run.state == "completed"
    assert run.metrics.completed_requests == 0
    assert run.metrics.failed_requests == 1
    assert run.metrics.passed_validations == 0
    assert run.metrics.failed_validations == 1
    assert run.requests[0].state == "failed"
    assert run.requests[0].attempts[0].state == "failed"
    assert events[-1].type == "run.completed"


@pytest.mark.asyncio
async def test_fatal_orchestrator_exception_marks_run_failed() -> None:
    orch = orchestrator()
    config = scenario(
        routing_profile=RoutingProfile.single_provider(
            id="single",
            route=RouteTarget(model="mock-fast", provider="mock"),
        )
    )
    config.workload_name = "missing_workload"

    run = await orch.run_to_completion(config, run_id="run-fatal")
    events = await orch.replay_events_after(run.id, None)

    assert run.state == "failed"
    assert run.error is not None
    assert events[-1].type == "run.failed"
    assert "missing_workload" in events[-1].payload["error"]


@pytest.mark.asyncio
async def test_clear_skies_mock_preset_completes_with_all_validations() -> None:
    settings = Settings(CNAI_MODE="mock")
    preset = next(
        item for item in build_seeded_presets(settings) if item.id == "preset-clear-skies"
    )
    fast_preset = preset.model_copy(update={"rate_per_second": 1000})

    run = await orchestrator().run_to_completion(
        fast_preset,
        run_id="run-clear-skies",
    )

    assert run.state == "completed"
    assert run.metrics.total_requests == 12
    assert run.metrics.completed_requests == 12
    assert run.metrics.failed_requests == 0
    assert run.metrics.passed_validations == 12
    assert run.metrics.failed_validations == 0


@pytest.mark.asyncio
async def test_mock_scenario_uses_mock_adapter() -> None:
    live_client = RecordingConcentrateClient(provider="live-provider", is_mock=False)
    mock_client = RecordingConcentrateClient(provider="mock", is_mock=True)
    orch = SimulationOrchestrator(
        store=InMemoryRunStore(),
        event_bus=EventBus(),
        concentrate_client=live_client,
        mock_concentrate_client=mock_client,
    )

    run = await orch.run_to_completion(
        scenario(
            routing_profile=RoutingProfile.single_provider(
                id="single",
                route=RouteTarget(model="mock-fast", provider="mock"),
            ),
            mode="mock",
        ),
        run_id="run-mock-adapter",
    )

    assert live_client.calls == 0
    assert mock_client.calls == 1
    assert run.requests[0].attempts[0].actual_provider == "mock"


@pytest.mark.asyncio
async def test_live_concentrate_native_scenario_uses_live_adapter() -> None:
    live_client = RecordingConcentrateClient(provider="live-provider", is_mock=False)
    mock_client = RecordingConcentrateClient(provider="mock", is_mock=True)
    orch = SimulationOrchestrator(
        store=InMemoryRunStore(),
        event_bus=EventBus(),
        concentrate_client=live_client,
        mock_concentrate_client=mock_client,
    )

    run = await orch.run_to_completion(
        scenario(
            routing_profile=RoutingProfile.gateway_auto(
                id="gateway-auto",
                metric="performance",
            ),
            mode="concentrate_native",
        ),
        run_id="run-live-adapter",
    )

    assert live_client.calls == 1
    assert mock_client.calls == 0
    assert run.requests[0].attempts[0].actual_provider == "live-provider"
    assert run.requests[0].attempts[0].actual_model == "auto"


@pytest.mark.asyncio
async def test_cancellation_marks_in_progress_abandoned() -> None:
    orch = orchestrator(client=DelayedMockConcentrateClient())
    run = await orch.create_run(
        scenario(
            routing_profile=RoutingProfile.single_provider(
                id="single",
                route=RouteTarget(model="mock-fast", provider="mock"),
            ),
            request_count=3,
            rate_per_second=100,
            max_concurrency=1,
        ),
        run_id="run-cancel",
    )

    await orch.start_run(run.id)
    await asyncio.sleep(0.02)
    await orch.cancel_run(run.id)
    while (await orch.get_run(run.id)).state not in {"cancelled", "failed"}:
        await asyncio.sleep(0.01)

    final_run = await orch.get_run(run.id)
    events = await orch.replay_events_after(run.id, None)

    assert final_run is not None
    assert final_run.state == "cancelled"
    assert final_run.metrics.abandoned_requests >= 1
    assert any(request.state == "abandoned" for request in final_run.requests)
    assert events[-1].type == "run.cancelled"


@pytest.mark.asyncio
async def test_event_ordering_uses_monotonic_sequences() -> None:
    orch = orchestrator()
    run = await orch.run_to_completion(
        scenario(
            routing_profile=RoutingProfile.single_provider(
                id="single",
                route=RouteTarget(model="mock-fast", provider="mock"),
            )
        ),
        run_id="run-order",
    )

    events = await orch.replay_events_after(run.id, None)
    sequences = [event.sequence for event in events]

    assert sequences == list(range(1, len(events) + 1))
    assert events[0].type == "run.created"
    assert events[1].type == "run.started"
    assert events[-1].type == "run.completed"


@pytest.mark.asyncio
async def test_deterministic_fault_reproduction() -> None:
    config = scenario(
        routing_profile=RoutingProfile.resilient_route(
            id="resilient",
            routes=[
                RouteTarget(model="mock-fast", provider="primary"),
                RouteTarget(model="mock-fast", provider="fallback"),
            ],
        ),
        fault_rules=[
            FaultRule(
                id="primary-outage",
                type="provider_outage",
                target_provider="primary",
                start_after_ms=0,
                duration_ms=10_000,
                probability=1,
            ),
            FaultRule(
                id="bad-json",
                type="malformed_json",
                target_provider="fallback",
                start_after_ms=0,
                duration_ms=10_000,
                probability=0,
            ),
        ],
        seed=42,
    )
    first = await orchestrator().run_to_completion(config, run_id="run-deterministic-a")
    second = await orchestrator().run_to_completion(config, run_id="run-deterministic-b")

    first_faults = [
        provenance.model_dump()
        for request in first.requests
        for attempt in request.attempts
        for provenance in attempt.fault_provenance
    ]
    second_faults = [
        provenance.model_dump()
        for request in second.requests
        for attempt in request.attempts
        for provenance in attempt.fault_provenance
    ]

    assert first_faults == second_faults


class DelayedMockConcentrateClient(MockConcentrateClient):
    async def create_response(self, request: ConcentrateResponseRequest):
        await asyncio.sleep(0.1)
        return await super().create_response(request)


class RecordingConcentrateClient(MockConcentrateClient):
    def __init__(self, *, provider: str, is_mock: bool) -> None:
        super().__init__(seed=0)
        self.provider = provider
        self.is_mock = is_mock
        self.calls = 0

    async def create_response(self, request: ConcentrateResponseRequest):
        self.calls += 1
        response = await super().create_response(request)
        return response.model_copy(
            update={
                "model": request.model,
                "provider": self.provider,
                "is_mock": self.is_mock,
            }
        )
