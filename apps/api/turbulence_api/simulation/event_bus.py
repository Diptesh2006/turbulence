from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from turbulence_api.simulation.events import SimulationEvent


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[SimulationEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, event: SimulationEvent) -> None:
        async with self._lock:
            subscribers = list(self._subscribers.get(event.run_id, set()))
        for queue in subscribers:
            queue.put_nowait(event)

    async def subscribe(self, run_id: str) -> AsyncIterator[SimulationEvent]:
        queue: asyncio.Queue[SimulationEvent] = asyncio.Queue()
        async with self._lock:
            self._subscribers[run_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[run_id].discard(queue)
                if not self._subscribers[run_id]:
                    self._subscribers.pop(run_id, None)

