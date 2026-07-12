from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from turbulence_api.simulation.events import TERMINAL_RUN_EVENTS, SimulationEvent
from turbulence_api.simulation.orchestrator import SimulationOrchestrator

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    orchestrator: SimulationOrchestrator = request.app.state.simulation_orchestrator
    if await orchestrator.get_run(run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    last_event_id = _parse_last_event_id(request.headers.get("last-event-id"))

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

