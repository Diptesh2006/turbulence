from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from turbulence_api.domain.faults import FaultRule
from turbulence_api.domain.routing import RoutingProfile
from turbulence_api.reporting.models import PostFlightReport, RunComparison
from turbulence_api.simulation.models import ScenarioConfig, SimulationRun


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    errors: list[dict[str, Any]] | None = None


class WorkloadSummary(BaseModel):
    name: str
    fixture_count: int
    categories: list[str] | None = None
    priorities: list[str] | None = None


class RoutingProfileSummary(BaseModel):
    type: str
    description: str
    supported_metrics: list[str] | None = None


class ScenarioRequest(BaseModel):
    id: str = Field(examples=["support-triage-smoke"])
    workload_name: str = Field(default="support_ticket_triage", examples=["support_ticket_triage"])
    request_count: int = Field(default=5, ge=1, examples=[5])
    seed: int = Field(default=0, examples=[42])
    rate_per_second: float = Field(default=1, gt=0, examples=[2])
    max_concurrency: int = Field(default=1, ge=1, examples=[2])
    model: str = Field(default="mock-fast", examples=["mock-fast"])
    max_output_tokens: int = Field(default=128, ge=1, examples=[96])
    recovery_time_slo_ms: int | None = Field(default=None, ge=1, examples=[1000])
    latency_slo_ms: int | None = Field(default=None, ge=1, examples=[2000])
    routing_profile: RoutingProfile
    fault_rules: list[FaultRule] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "support-triage-smoke",
                    "workload_name": "support_ticket_triage",
                    "request_count": 3,
                    "seed": 42,
                    "rate_per_second": 2,
                    "max_concurrency": 2,
                    "model": "mock-fast",
                    "max_output_tokens": 96,
                    "recovery_time_slo_ms": 1000,
                    "latency_slo_ms": 2000,
                    "routing_profile": {
                        "id": "single-mock",
                        "type": "single_provider",
                        "routes": [{"model": "mock-fast", "provider": "mock"}],
                    },
                    "fault_rules": [],
                }
            ]
        }
    )

    def to_config(self) -> ScenarioConfig:
        return ScenarioConfig(**self.model_dump())


class ScenarioResponse(BaseModel):
    scenario: ScenarioConfig


class ScenarioListResponse(BaseModel):
    items: list[ScenarioConfig]


class RunCreateRequest(BaseModel):
    scenario_id: str | None = Field(default=None, examples=["support-triage-smoke"])
    scenario: ScenarioRequest | None = None


class RunResponse(BaseModel):
    run: SimulationRun


class RunSummary(BaseModel):
    id: str
    scenario_id: str
    state: str
    created_at: str
    updated_at: str
    metrics: dict[str, Any]


class RunListResponse(BaseModel):
    items: list[RunSummary]
    page: int
    page_size: int
    total: int


class ComparisonRequest(BaseModel):
    baseline_run_id: str = Field(examples=["run-a"])
    candidate_run_id: str = Field(examples=["run-b"])


class ComparisonResponse(BaseModel):
    comparison: RunComparison


class ReportResponse(BaseModel):
    report: PostFlightReport

