from fastapi import APIRouter, Request, status

from turbulence_api.agent_safety.models import AgentRun, AgentRunRequest, PolicyRule
from turbulence_api.services.agent_safety import AgentSafetyService

router = APIRouter(prefix="/agent-safety", tags=["agent-safety"])


def _service(request: Request) -> AgentSafetyService:
    return request.app.state.agent_safety_service


@router.get("/scenarios")
async def list_scenarios(request: Request) -> dict:
    return {"items": _service(request).list_scenarios(), "source": "simulated"}


@router.get("/policies")
async def list_policies(request: Request) -> dict:
    return {"items": _service(request).list_policies(), "source": "simulated"}


@router.put("/policies/{policy_id}", response_model=PolicyRule)
async def update_policy(policy_id: str, rule: PolicyRule, request: Request) -> PolicyRule:
    return _service(request).update_policy(policy_id, rule)


@router.post("/runs", response_model=AgentRun, status_code=status.HTTP_201_CREATED)
async def create_run(payload: AgentRunRequest, request: Request) -> AgentRun:
    return _service(request).create_run(payload.scenario_id, payload.seed)


@router.get("/runs")
async def list_runs(request: Request) -> dict:
    runs = sorted(_service(request).runs.values(), key=lambda run: run.created_at, reverse=True)
    return {"items": runs, "source": "simulated"}


@router.get("/runs/{run_id}", response_model=AgentRun)
async def get_run(run_id: str, request: Request) -> AgentRun:
    return _service(request).get_run(run_id)


@router.post("/runs/{run_id}/replay", response_model=AgentRun, status_code=status.HTTP_201_CREATED)
async def replay_run(run_id: str, request: Request) -> AgentRun:
    return _service(request).replay(run_id)
