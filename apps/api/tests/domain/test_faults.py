from __future__ import annotations

from turbulence_api.domain.faults import DeterministicFaultInjector, FaultRule
from turbulence_api.domain.routing import RoutingAttempt
from turbulence_api.integrations.concentrate.models import NormalizedConcentrateResponse


def attempt(
    *,
    model: str = "model-a",
    provider: str | None = "provider-a",
    index: int = 0,
) -> RoutingAttempt:
    return RoutingAttempt(index=index, model=model, provider=provider, label="test")


def test_provider_outage_is_simulated_424_and_skips_upstream() -> None:
    rule = FaultRule(
        id="outage-a",
        type="provider_outage",
        target_provider="provider-a",
        target_model=None,
        start_after_ms=100,
        duration_ms=500,
        probability=1,
    )
    injector = DeterministicFaultInjector(seed=10, scenario_id="scenario-a")

    result = injector.evaluate_pre_call(rules=[rule], attempt=attempt(), at_ms=200)

    assert result.should_send_upstream is False
    assert result.simulated_status_code == 424
    assert result.provenance[0].source == "simulated"
    assert result.provenance[0].rule_id == "outage-a"
    assert result.provenance[0].simulated_status_code == 424
    assert [event.type for event in result.events] == ["fault.activated"]


def test_rate_limit_burst_is_simulated_429_with_retry_after() -> None:
    rule = FaultRule(
        id="rate-limit-a",
        type="rate_limit_burst",
        target_provider=None,
        target_model="model-a",
        start_after_ms=0,
        duration_ms=1000,
        probability=1,
        parameters={"retry_after_ms": 2500},
    )
    injector = DeterministicFaultInjector(seed=10, scenario_id="scenario-a")

    result = injector.evaluate_pre_call(rules=[rule], attempt=attempt(), at_ms=1)

    assert result.should_send_upstream is False
    assert result.simulated_status_code == 429
    assert result.retry_after_ms == 2500
    assert result.provenance[0].retry_after_ms == 2500


def test_latency_spike_records_injected_delay_without_status_code() -> None:
    rule = FaultRule(
        id="latency-a",
        type="latency_spike",
        target_provider="provider-a",
        target_model="model-a",
        start_after_ms=0,
        duration_ms=1000,
        probability=1,
        parameters={"delay_ms": 175},
    )
    injector = DeterministicFaultInjector(seed=10, scenario_id="scenario-a")

    result = injector.evaluate_pre_call(rules=[rule], attempt=attempt(), at_ms=1)

    assert result.should_send_upstream is True
    assert result.simulated_status_code is None
    assert result.injected_delay_ms == 175
    assert result.provenance[0].injected_delay_ms == 175


def test_fault_target_matching_skips_non_matching_provider() -> None:
    rule = FaultRule(
        id="outage-a",
        type="provider_outage",
        target_provider="provider-b",
        target_model=None,
        start_after_ms=0,
        duration_ms=1000,
        probability=1,
    )
    injector = DeterministicFaultInjector(seed=10, scenario_id="scenario-a")

    result = injector.evaluate_pre_call(rules=[rule], attempt=attempt(), at_ms=1)

    assert result.should_send_upstream is True
    assert result.provenance == []


def test_fault_window_activation_and_clearing_events() -> None:
    rule = FaultRule(
        id="latency-a",
        type="latency_spike",
        start_after_ms=100,
        duration_ms=100,
        probability=1,
        parameters={"delay_ms": 1},
    )
    injector = DeterministicFaultInjector(seed=10, scenario_id="scenario-a")

    before = injector.evaluate_pre_call(rules=[rule], attempt=attempt(), at_ms=99)
    active = injector.evaluate_pre_call(rules=[rule], attempt=attempt(), at_ms=100)
    still_active = injector.evaluate_pre_call(rules=[rule], attempt=attempt(), at_ms=150)
    cleared = injector.evaluate_pre_call(rules=[rule], attempt=attempt(), at_ms=200)

    assert before.events == []
    assert [event.type for event in active.events] == ["fault.activated"]
    assert still_active.events == []
    assert [event.type for event in cleared.events] == ["fault.cleared"]
    assert all(event.source == "simulated" for event in active.events + cleared.events)


def test_seeded_probability_is_deterministic_for_same_scenario() -> None:
    rule = FaultRule(
        id="latency-a",
        type="latency_spike",
        start_after_ms=0,
        duration_ms=1000,
        probability=0.5,
        parameters={"delay_ms": 1},
    )

    first = DeterministicFaultInjector(seed=99, scenario_id="same").evaluate_pre_call(
        rules=[rule],
        attempt=attempt(),
        at_ms=10,
    )
    second = DeterministicFaultInjector(seed=99, scenario_id="same").evaluate_pre_call(
        rules=[rule],
        attempt=attempt(),
        at_ms=10,
    )

    assert first.provenance == second.provenance
    assert first.injected_delay_ms == second.injected_delay_ms


def test_malformed_json_corrupts_validation_copy_and_preserves_original() -> None:
    rule = FaultRule(
        id="malformed-a",
        type="malformed_json",
        target_provider="provider-a",
        target_model="model-a",
        start_after_ms=0,
        duration_ms=1000,
        probability=1,
    )
    upstream_response = NormalizedConcentrateResponse(
        id="resp-1",
        model="model-a",
        provider="provider-a",
        assistant_text='{"ok": true}',
    )
    injector = DeterministicFaultInjector(seed=10, scenario_id="scenario-a")

    result = injector.evaluate_post_response(
        rules=[rule],
        attempt=attempt(),
        at_ms=1,
        response=upstream_response,
    )

    assert result.original_response.assistant_text == '{"ok": true}'
    assert result.response_for_validation.assistant_text != '{"ok": true}'
    assert upstream_response.assistant_text == '{"ok": true}'
    assert result.provenance[0].corrupted_response is True
    assert result.provenance[0].original_response_preserved is True

