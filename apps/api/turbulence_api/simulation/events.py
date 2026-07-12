from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventSource = Literal["real", "simulated", "system"]


class SimulationEvent(BaseModel):
    sequence: int = Field(ge=1)
    type: str
    source: EventSource
    timestamp: datetime
    run_id: str
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        type: str,
        source: EventSource,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> SimulationEvent:
        return cls(
            sequence=sequence,
            type=type,
            source=source,
            timestamp=datetime.now(UTC),
            run_id=run_id,
            payload=payload or {},
        )


TERMINAL_RUN_EVENTS = {"run.completed", "run.failed", "run.cancelled"}

