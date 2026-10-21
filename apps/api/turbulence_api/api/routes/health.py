from fastapi import APIRouter

from turbulence_api.core.config import get_settings
from turbulence_api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        service=settings.service_name,
        status="ok",
        version=settings.version,
        environment=settings.environment,
        simulation_mode=settings.simulation_mode,
    )


@router.get("/integrations/breakmybot/capabilities")
async def breakmybot_capabilities() -> dict:
    """Declare scope without conflating simulations with external target tests."""
    return {
        "contract": "breakmybot-turbulence-v1",
        "service": "Turbulence",
        "capabilities": {
            "provider_boundary_simulation": True,
            "simulation_event_provenance": True,
            "external_target_tool_injection": False,
            "external_target_http_fault_proxy": False,
        },
        "fault_scope": "Turbulence-managed Concentrate routing attempts only",
        "event_source": "simulated",
        "agent_safety_scope": "seeded simulator fixtures; not external-target observations",
    }

