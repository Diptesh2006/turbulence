from __future__ import annotations

from fastapi import APIRouter, Request

from turbulence_api.api.schemas import WorkloadSummary
from turbulence_api.workloads.support_ticket_triage import SUPPORT_TICKET_TRIAGE_FIXTURES

router = APIRouter(prefix="/workloads", tags=["workloads"])


@router.get("", response_model=list[WorkloadSummary])
async def list_workloads(request: Request) -> list[WorkloadSummary]:
    registry = request.app.state.workload_registry
    summaries: list[WorkloadSummary] = []
    for name in registry.list_names():
        if name == "support_ticket_triage":
            summaries.append(
                WorkloadSummary(
                    name=name,
                    fixture_count=len(SUPPORT_TICKET_TRIAGE_FIXTURES),
                    categories=["billing", "technical", "account", "security", "other"],
                    priorities=["low", "medium", "high", "critical"],
                )
            )
        else:
            summaries.append(WorkloadSummary(name=name, fixture_count=0))
    return summaries

