from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from turbulence_api.integrations.concentrate.models import (
    ConcentrateResponseRequest,
    NormalizedConcentrateResponse,
)


class WorkloadFixture(BaseModel):
    id: str


class WorkloadScore(BaseModel):
    schema_valid: bool
    category_correct: bool
    priority_correct: bool
    summary_keyword_coverage: float
    overall_correct: bool


class WorkloadValidationResult(BaseModel):
    fixture_id: str
    parsed_output: dict[str, Any] | None
    score: WorkloadScore
    errors: list[str]


class Workload(Protocol):
    name: str

    def select_fixture(self, seed: int) -> WorkloadFixture: ...

    def build_request(
        self,
        fixture: WorkloadFixture,
        *,
        model: str,
        max_output_tokens: int,
    ) -> ConcentrateResponseRequest: ...

    def validate_response(
        self,
        fixture: WorkloadFixture,
        response: NormalizedConcentrateResponse,
    ) -> WorkloadValidationResult: ...
