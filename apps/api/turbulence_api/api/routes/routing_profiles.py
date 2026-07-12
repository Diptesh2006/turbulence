from __future__ import annotations

from fastapi import APIRouter

from turbulence_api.api.schemas import RoutingProfileSummary

router = APIRouter(prefix="/routing-profiles", tags=["routing-profiles"])


@router.get("", response_model=list[RoutingProfileSummary])
async def list_routing_profiles() -> list[RoutingProfileSummary]:
    return [
        RoutingProfileSummary(
            type="single_provider",
            description="Exactly one ordered route; intentionally brittle.",
        ),
        RoutingProfileSummary(
            type="gateway_auto",
            description="Delegates provider/model choice to Concentrate with model='auto'.",
            supported_metrics=["cost", "performance", "p50_latency", "uptime"],
        ),
        RoutingProfileSummary(
            type="resilient_route",
            description="Simulator-managed deterministic fallback over ordered routes.",
        ),
    ]

