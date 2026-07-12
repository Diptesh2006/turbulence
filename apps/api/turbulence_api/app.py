from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from turbulence_api.api.router import api_router
from turbulence_api.api.schemas import ProblemDetail
from turbulence_api.core.config import get_settings
from turbulence_api.integrations.concentrate.factory import build_concentrate_client
from turbulence_api.integrations.concentrate.mock import MockConcentrateClient
from turbulence_api.reporting.compare import CompareRunsService
from turbulence_api.reporting.reports import PostFlightReportService
from turbulence_api.repositories.scenarios import ScenarioRepository
from turbulence_api.services.errors import ServiceError
from turbulence_api.services.presets import build_seeded_presets
from turbulence_api.services.runs import RunService
from turbulence_api.services.scenarios import ScenarioService
from turbulence_api.simulation.event_bus import EventBus
from turbulence_api.simulation.orchestrator import SimulationOrchestrator
from turbulence_api.simulation.store import InMemoryRunStore
from turbulence_api.workloads.registry import build_default_registry


class RootResponse(BaseModel):
    service: str
    status: str
    version: str
    health_endpoint: str
    docs_url: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.workload_registry = build_default_registry()
    app.state.concentrate_client = build_concentrate_client(settings)
    app.state.mock_concentrate_client = MockConcentrateClient(seed=0)
    app.state.run_store = InMemoryRunStore()
    app.state.event_bus = EventBus()
    app.state.scenario_repository = ScenarioRepository()
    app.state.simulation_orchestrator = SimulationOrchestrator(
        store=app.state.run_store,
        event_bus=app.state.event_bus,
        concentrate_client=app.state.concentrate_client,
        mock_concentrate_client=app.state.mock_concentrate_client,
        workload_registry=app.state.workload_registry,
    )
    app.state.scenario_service = ScenarioService(
        repository=app.state.scenario_repository,
        run_store=app.state.run_store,
        workload_registry=app.state.workload_registry,
        settings=settings,
    )
    app.state.run_service = RunService(
        orchestrator=app.state.simulation_orchestrator,
        run_store=app.state.run_store,
        report_service=PostFlightReportService(),
        compare_service=CompareRunsService(),
    )
    await app.state.scenario_service.seed_presets(build_seeded_presets(settings))
    try:
        yield
    finally:
        await app.state.concentrate_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.service_name,
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
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

    @app.get("/", response_model=RootResponse, tags=["root"])
    async def root() -> RootResponse:
        return RootResponse(
            service=settings.service_name,
            status="ok",
            version=settings.version,
            health_endpoint="/api/health",
            docs_url="/docs",
        )

    app.add_exception_handler(ServiceError, _service_error_handler)
    app.add_exception_handler(HTTPException, _http_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    return app


async def _service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    problem = ProblemDetail(
        title=exc.title,
        status=exc.status_code,
        detail=exc.detail,
        instance=str(request.url.path),
    )
    return JSONResponse(status_code=exc.status_code, content=problem.model_dump(exclude_none=True))


async def _http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    problem = ProblemDetail(
        title="HTTP Error",
        status=exc.status_code,
        detail=str(exc.detail),
        instance=str(request.url.path),
    )
    return JSONResponse(status_code=exc.status_code, content=problem.model_dump(exclude_none=True))


async def _validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    problem = ProblemDetail(
        title="Validation Error",
        status=422,
        detail="Request validation failed",
        instance=str(request.url.path),
        errors=[
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ],
    )
    return JSONResponse(status_code=422, content=problem.model_dump(exclude_none=True))
