from __future__ import annotations

from fastapi import APIRouter, Request

from turbulence_api.api.schemas import ComparisonRequest, ComparisonResponse
from turbulence_api.services.runs import RunService

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.post("", response_model=ComparisonResponse)
async def compare_runs(payload: ComparisonRequest, request: Request) -> ComparisonResponse:
    service: RunService = request.app.state.run_service
    comparison = await service.compare(payload.baseline_run_id, payload.candidate_run_id)
    return ComparisonResponse(comparison=comparison)

