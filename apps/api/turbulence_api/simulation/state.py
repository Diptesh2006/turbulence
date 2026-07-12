from __future__ import annotations

from typing import Literal

RunState = Literal["created", "running", "completed", "failed", "cancelling", "cancelled"]

VALID_TRANSITIONS: dict[RunState, set[RunState]] = {
    "created": {"running"},
    "running": {"completed", "failed", "cancelling"},
    "cancelling": {"cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class InvalidRunStateTransitionError(ValueError):
    pass


def validate_transition(current: RunState, next_state: RunState) -> None:
    if next_state not in VALID_TRANSITIONS[current]:
        raise InvalidRunStateTransitionError(
            f"Invalid run state transition: {current} -> {next_state}"
        )

