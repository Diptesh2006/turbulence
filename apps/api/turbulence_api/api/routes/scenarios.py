from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from turbulence_api.api.schemas import ScenarioListResponse, ScenarioRequest, ScenarioResponse
from turbulence_api.services.scenarios import ScenarioService

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _service(request: Request) -> ScenarioService:
    return request.app.state.scenario_service


@router.get("", response_model=ScenarioListResponse)
async def list_scenarios(request: Request) -> ScenarioListResponse:
    return ScenarioListResponse(items=await _service(request).list())


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: str, request: Request) -> ScenarioResponse:
    return ScenarioResponse(scenario=await _service(request).get(scenario_id))


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(payload: ScenarioRequest, request: Request) -> ScenarioResponse:
    scenario = await _service(request).create(payload.to_config())
    return ScenarioResponse(scenario=scenario)


@router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: str,
    payload: ScenarioRequest,
    request: Request,
) -> ScenarioResponse:
    scenario = await _service(request).update(scenario_id, payload.to_config())
    return ScenarioResponse(scenario=scenario)


@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_scenario(scenario_id: str, request: Request) -> None:
    await _service(request).delete(scenario_id)
