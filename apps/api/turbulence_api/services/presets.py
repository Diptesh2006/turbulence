from __future__ import annotations

from turbulence_api.core.config import Settings
from turbulence_api.domain.faults import FaultRule
from turbulence_api.domain.routing import RouteTarget, RoutingProfile
from turbulence_api.simulation.models import ScenarioConfig


def build_seeded_presets(settings: Settings) -> list[ScenarioConfig]:
    return [
        ScenarioConfig(
            id="preset-clear-skies",
            mode="mock",
            workload_name="support_ticket_triage",
            request_count=12,
            seed=101,
            rate_per_second=2,
            max_concurrency=2,
            model="auto",
            max_output_tokens=settings.workload_max_output_tokens,
            recovery_time_slo_ms=1500,
            latency_slo_ms=2000,
            routing_profile=RoutingProfile.gateway_auto(
                id="clear-skies-gateway-auto",
                metric="performance",
            ),
            fault_rules=[],
        ),
        ScenarioConfig(
            id="preset-provider-mayday",
            mode="mock",
            workload_name="support_ticket_triage",
            request_count=15,
            seed=202,
            rate_per_second=3,
            max_concurrency=3,
            model=settings.openai_model_id,
            max_output_tokens=settings.workload_max_output_tokens,
            recovery_time_slo_ms=1500,
            latency_slo_ms=2500,
            routing_profile=RoutingProfile.resilient_route(
                id="provider-mayday-resilient",
                routes=[
                    RouteTarget(model=settings.openai_model_id, provider="openai"),
                    RouteTarget(model=settings.anthropic_model_id, provider="anthropic"),
                    RouteTarget(model=settings.google_model_id, provider="google"),
                ],
            ),
            fault_rules=[
                FaultRule(
                    id="mayday-primary-outage",
                    type="provider_outage",
                    target_provider="openai",
                    start_after_ms=1667,
                    duration_ms=1667,
                    probability=1,
                    parameters={"purpose": "middle third primary outage"},
                )
            ],
        ),
        ScenarioConfig(
            id="preset-perfect-storm",
            mode="mock",
            workload_name="support_ticket_triage",
            request_count=18,
            seed=303,
            rate_per_second=3,
            max_concurrency=3,
            model=settings.openai_model_id,
            max_output_tokens=settings.workload_max_output_tokens,
            recovery_time_slo_ms=2000,
            latency_slo_ms=3000,
            routing_profile=RoutingProfile.resilient_route(
                id="perfect-storm-resilient",
                routes=[
                    RouteTarget(model=settings.openai_model_id, provider="openai"),
                    RouteTarget(model=settings.anthropic_model_id, provider="anthropic"),
                    RouteTarget(model=settings.google_model_id, provider="google"),
                ],
            ),
            fault_rules=[
                FaultRule(
                    id="storm-latency-spike",
                    type="latency_spike",
                    start_after_ms=0,
                    duration_ms=2200,
                    probability=1,
                    parameters={"delay_ms": 350},
                ),
                FaultRule(
                    id="storm-rate-limit",
                    type="rate_limit_burst",
                    start_after_ms=2200,
                    duration_ms=1200,
                    probability=0.6,
                    parameters={"retry_after_ms": 900},
                ),
                FaultRule(
                    id="storm-malformed-json",
                    type="malformed_json",
                    start_after_ms=3400,
                    duration_ms=2600,
                    probability=0.12,
                    parameters={"purpose": "small structured-output corruption sample"},
                ),
            ],
        ),
    ]
