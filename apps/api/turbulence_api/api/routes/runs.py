from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from turbulence_api.api.schemas import (
    ReportResponse,
    RunCreateRequest,
    RunListResponse,
    RunResponse,
    RunSummary,
)
from turbulence_api.services.errors import NotFoundError, ValidationServiceError
from turbulence_api.services.runs import RunService
from turbulence_api.services.scenarios import ScenarioService
from turbulence_api.simulation.events import TERMINAL_RUN_EVENTS, SimulationEvent
from turbulence_api.simulation.models import SimulationRun
from turbulence_api.simulation.orchestrator import SimulationOrchestrator

router = APIRouter(prefix="/runs", tags=["runs"])


def _run_service(request: Request) -> RunService:
    return request.app.state.run_service


def _scenario_service(request: Request) -> ScenarioService:
    return request.app.state.scenario_service


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunResponse:
    if payload.scenario_id and payload.scenario:
        raise ValidationServiceError("Provide either scenario_id or scenario, not both")
    if payload.scenario_id:
        scenario = await _scenario_service(request).get(payload.scenario_id)
    elif payload.scenario:
        scenario = payload.scenario.to_config()
        _scenario_service(request).validate(scenario)
    else:
        raise ValidationServiceError("Provide scenario_id or inline scenario")

    run = await _run_service(request).create_run(
        scenario,
        idempotency_key=idempotency_key,
    )
    return RunResponse(run=run)


@router.post("/{run_id}/start", response_model=RunResponse)
async def start_run(
    run_id: str,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RunResponse:
    run = await _run_service(request).start_run(run_id, idempotency_key=idempotency_key)
    return RunResponse(run=run)


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(run_id: str, request: Request) -> RunResponse:
    run = await _run_service(request).cancel_run(run_id)
    return RunResponse(run=run)


@router.get("", response_model=RunListResponse)
async def list_runs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> RunListResponse:
    runs, total = await _run_service(request).list_runs(page=page, page_size=page_size)
    return RunListResponse(
        items=[_run_summary(run) for run in runs],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, request: Request) -> RunResponse:
    return RunResponse(run=await _run_service(request).get_run(run_id))


@router.get("/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    orchestrator: SimulationOrchestrator = request.app.state.simulation_orchestrator
    if await orchestrator.get_run(run_id) is None:
        raise NotFoundError("Run not found")

    last_event_id = _parse_last_event_id(
        request.headers.get("last-event-id")
        or request.query_params.get("last_event_id")
    )

    async def stream() -> AsyncIterator[str]:
        replayed = await orchestrator.replay_events_after(run_id, last_event_id)
        for event in replayed:
            yield _format_sse(event)
            if event.type in TERMINAL_RUN_EVENTS:
                return

        subscription = orchestrator.subscribe(run_id)
        iterator = subscription.__aiter__()
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event = await asyncio.wait_for(iterator.__anext__(), timeout=15)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                yield _format_sse(event)
                if event.type in TERMINAL_RUN_EVENTS:
                    return
        finally:
            await subscription.aclose()

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/{run_id}/report", response_model=ReportResponse)
async def get_report(run_id: str, request: Request) -> ReportResponse:
    return ReportResponse(report=await _run_service(request).report(run_id))


def _parse_last_event_id(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _format_sse(event: SimulationEvent) -> str:
    payload = event.model_dump(mode="json")
    return (
        f"id: {event.sequence}\n"
        f"event: {event.type}\n"
        f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
    )


def _run_summary(run: SimulationRun) -> RunSummary:
    return RunSummary(
        id=run.id,
        scenario_id=run.scenario.id,
        state=run.state,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
        metrics=run.metrics.model_dump(),
    )
