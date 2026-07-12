from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from turbulence_api.api.router import api_router
from turbulence_api.core.config import get_settings
from turbulence_api.integrations.concentrate.factory import build_concentrate_client
from turbulence_api.simulation.event_bus import EventBus
from turbulence_api.simulation.orchestrator import SimulationOrchestrator
from turbulence_api.simulation.store import InMemoryRunStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.concentrate_client = build_concentrate_client(get_settings())
    app.state.run_store = InMemoryRunStore()
    app.state.event_bus = EventBus()
    app.state.simulation_orchestrator = SimulationOrchestrator(
        store=app.state.run_store,
        event_bus=app.state.event_bus,
        concentrate_client=app.state.concentrate_client,
    )
    try:
        yield
    finally:
        await app.state.concentrate_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.service_name,
        version=settings.version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")
    return app
