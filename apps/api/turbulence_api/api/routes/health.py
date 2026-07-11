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

