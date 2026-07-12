from __future__ import annotations

import asyncio

from turbulence_api.simulation.events import SimulationEvent
from turbulence_api.simulation.models import AttemptRecord, RequestRecord, SimulationRun


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, SimulationRun] = {}
        self._events: dict[str, list[SimulationEvent]] = {}
        self._next_sequence: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def create_run(self, run: SimulationRun) -> None:
        async with self._lock:
            self._runs[run.id] = run
            self._events[run.id] = []
            self._next_sequence[run.id] = 1

    async def get_run(self, run_id: str) -> SimulationRun | None:
        async with self._lock:
            return self._runs.get(run_id)

    async def save_request(self, run_id: str, request: RequestRecord) -> None:
        async with self._lock:
            run = self._runs[run_id]
            for index, existing in enumerate(run.requests):
                if existing.id == request.id:
                    run.requests[index] = request
                    break
            else:
                run.requests.append(request)

    async def save_attempt(self, run_id: str, request_id: str, attempt: AttemptRecord) -> None:
        async with self._lock:
            request = _find_request(self._runs[run_id], request_id)
            for index, existing in enumerate(request.attempts):
                if existing.id == attempt.id:
                    request.attempts[index] = attempt
                    break
            else:
                request.attempts.append(attempt)

    async def append_event(self, event: SimulationEvent) -> None:
        async with self._lock:
            self._events[event.run_id].append(event)

    async def next_sequence(self, run_id: str) -> int:
        async with self._lock:
            sequence = self._next_sequence[run_id]
            self._next_sequence[run_id] += 1
            return sequence

    async def replay_events_after(
        self,
        run_id: str,
        last_event_id: int | None,
    ) -> list[SimulationEvent]:
        async with self._lock:
            events = list(self._events.get(run_id, []))
        if last_event_id is None:
            return events
        return [event for event in events if event.sequence > last_event_id]

    async def mark_in_progress_abandoned(self, run_id: str) -> None:
        async with self._lock:
            run = self._runs[run_id]
            for request in run.requests:
                if request.state in {"queued", "running"}:
                    request.state = "abandoned"
                    run.metrics.abandoned_requests += 1
                for attempt in request.attempts:
                    if attempt.state == "started":
                        attempt.state = "abandoned"


def _find_request(run: SimulationRun, request_id: str) -> RequestRecord:
    for request in run.requests:
        if request.id == request_id:
            return request
    raise KeyError(f"Unknown request: {request_id}")
