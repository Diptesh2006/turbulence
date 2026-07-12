from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from turbulence_api.domain.faults import FaultProvenance, FaultRule
from turbulence_api.domain.routing import RoutingProfile
from turbulence_api.simulation.state import RunState, validate_transition

RequestState = Literal["queued", "running", "completed", "failed", "abandoned"]
AttemptState = Literal["started", "completed", "failed", "blocked", "abandoned"]


class ScenarioConfig(BaseModel):
    id: str
    workload_name: str = "support_ticket_triage"
    request_count: int = Field(default=1, ge=1)
    seed: int = 0
    rate_per_second: float = Field(default=1, gt=0)
    max_concurrency: int = Field(default=1, ge=1)
    model: str = "mock-fast"
    max_output_tokens: int = Field(default=128, ge=1)
    routing_profile: RoutingProfile
    fault_rules: list[FaultRule] = Field(default_factory=list)


class RunMetrics(BaseModel):
    total_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    abandoned_requests: int = 0
    passed_validations: int = 0
    failed_validations: int = 0


class AttemptRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"att-{uuid4().hex}")
    request_id: str
    index: int
    model: str
    provider: str | None = None
    state: AttemptState = "started"
    simulator_managed_fallback: bool = False
    fault_provenance: list[FaultProvenance] = Field(default_factory=list)
    upstream_response_id: str | None = None
    simulated_status_code: int | None = None
    validation_passed: bool | None = None
    errors: list[str] = Field(default_factory=list)


class RequestRecord(BaseModel):
    id: str
    fixture_id: str
    state: RequestState = "queued"
    attempts: list[AttemptRecord] = Field(default_factory=list)
    validation_result: dict | None = None


class SimulationRun(BaseModel):
    id: str
    scenario: ScenarioConfig
    state: RunState = "created"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    requests: list[RequestRecord] = Field(default_factory=list)
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    error: str | None = None

    def transition_to(self, next_state: RunState) -> None:
        validate_transition(self.state, next_state)
        self.state = next_state
        self.updated_at = datetime.now(UTC)

