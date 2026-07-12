from fastapi import APIRouter

from turbulence_api.api.routes.concentrate import router as concentrate_router
from turbulence_api.api.routes.health import router as health_router
from turbulence_api.api.routes.runs import router as runs_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(concentrate_router)
api_router.include_router(runs_router)
