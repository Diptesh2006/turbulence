from fastapi import APIRouter

from turbulence_api.api.routes.agent_safety import router as agent_safety_router
from turbulence_api.api.routes.comparisons import router as comparisons_router
from turbulence_api.api.routes.concentrate import router as concentrate_router
from turbulence_api.api.routes.health import router as health_router
from turbulence_api.api.routes.routing_profiles import router as routing_profiles_router
from turbulence_api.api.routes.runs import router as runs_router
from turbulence_api.api.routes.scenarios import router as scenarios_router
from turbulence_api.api.routes.workloads import router as workloads_router

api_router = APIRouter()
api_router.include_router(agent_safety_router)
api_router.include_router(health_router)
api_router.include_router(workloads_router)
api_router.include_router(routing_profiles_router)
api_router.include_router(scenarios_router)
api_router.include_router(concentrate_router)
api_router.include_router(runs_router)
api_router.include_router(comparisons_router)
