from __future__ import annotations

import pytest
from pydantic import ValidationError

from turbulence_api.domain.routing import RouteTarget, RoutingProfile


def test_single_provider_has_one_ordered_route() -> None:
    profile = RoutingProfile.single_provider(
        id="single",
        route=RouteTarget(model="model-a", provider="provider-a"),
    )

    attempt = profile.initial_attempt()

    assert attempt.model == "model-a"
    assert attempt.provider == "provider-a"
    assert attempt.simulator_managed_fallback is False
    assert profile.next_attempt_after_failure(attempt) is None


def test_single_provider_rejects_multiple_routes() -> None:
    with pytest.raises(ValidationError):
        RoutingProfile(
            id="bad",
            type="single_provider",
            routes=[
                RouteTarget(model="model-a", provider="provider-a"),
                RouteTarget(model="model-b", provider="provider-b"),
            ],
        )


def test_gateway_auto_uses_auto_model_and_no_client_provider_claim() -> None:
    profile = RoutingProfile.gateway_auto(id="gateway", metric="cost")

    attempt = profile.initial_attempt()
    hint = profile.gateway_routing_hint()

    assert attempt.model == "auto"
    assert attempt.provider is None
    assert hint is not None
    assert hint.metric == "cost"
    assert profile.next_attempt_after_failure(attempt) is None


def test_gateway_auto_requires_supported_metric() -> None:
    with pytest.raises(ValidationError):
        RoutingProfile(id="gateway", type="gateway_auto", metric="least_confusing")


def test_resilient_route_advances_to_simulator_managed_fallbacks() -> None:
    profile = RoutingProfile.resilient_route(
        id="resilient",
        routes=[
            RouteTarget(model="primary-model", provider="provider-a"),
            RouteTarget(model="fallback-model", provider="provider-b"),
            RouteTarget(model="final-model", provider="provider-c"),
        ],
    )

    first = profile.initial_attempt()
    second = profile.next_attempt_after_failure(first)
    third = profile.next_attempt_after_failure(second)

    assert first.label == "primary route"
    assert second is not None
    assert second.model == "fallback-model"
    assert second.provider == "provider-b"
    assert second.simulator_managed_fallback is True
    assert second.label == "simulator-managed deterministic fallback"
    assert third is not None
    assert third.model == "final-model"
    assert profile.next_attempt_after_failure(third) is None


def test_resilient_route_requires_primary_and_fallback() -> None:
    with pytest.raises(ValidationError):
        RoutingProfile.resilient_route(
            id="bad",
            routes=[RouteTarget(model="primary-model", provider="provider-a")],
        )

