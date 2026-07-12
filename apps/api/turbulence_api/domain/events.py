from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    id: str
    type: Literal["fault.activated", "fault.cleared"]
    source: Literal["simulated"] = "simulated"
    rule_id: str
    at_ms: int = Field(ge=0)
    message: str

