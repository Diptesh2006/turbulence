from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from turbulence_api.core.config import Settings, get_settings
from turbulence_api.integrations.concentrate.client import ConcentrateClientProtocol
from turbulence_api.integrations.concentrate.exceptions import (
    ConcentrateAuthenticationError,
    ConcentrateConfigurationError,
    ConcentrateError,
    ConcentrateGatewayError,
    ConcentrateInsufficientCreditsError,
    ConcentrateMalformedResponseError,
    ConcentrateProviderDependencyError,
    ConcentrateRateLimitError,
    ConcentrateTimeoutError,
)
from turbulence_api.integrations.concentrate.models import (
    ConcentrateHealth,
    ConcentrateMetadata,
    ConcentrateResponseRequest,
    JsonSchemaFormat,
    NormalizedConcentrateResponse,
    TextOptions,
)

router = APIRouter(prefix="/integrations/concentrate", tags=["integrations"])


class ConcentrateTestRequest(BaseModel):
    model: str = "concentrate-small"
    request_id: str | None = None
    run_id: str | None = None
    scenario_id: str | None = None


class ConcentrateStatusResponse(BaseModel):
    mode: str
    status: str
    is_mock: bool
    configured: bool


class ConcentrateTestResponse(BaseModel):
    response: NormalizedConcentrateResponse


def get_concentrate_client(request: Request) -> ConcentrateClientProtocol:
    return request.app.state.concentrate_client


@router.get("/status", response_model=ConcentrateStatusResponse)
async def concentrate_status(
    client: Annotated[ConcentrateClientProtocol, Depends(get_concentrate_client)],
) -> ConcentrateStatusResponse:
    try:
        health = await client.health_check()
    except ConcentrateError as exc:
        raise _http_error(exc) from exc

    return _status_response(health)


@router.post("/test", response_model=ConcentrateTestResponse)
async def concentrate_test(
    payload: ConcentrateTestRequest,
    client: Annotated[ConcentrateClientProtocol, Depends(get_concentrate_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConcentrateTestResponse:
    if settings.cnai_mode != "live":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Concentrate test requests only run when CNAI_MODE=live",
        )

    request = ConcentrateResponseRequest(
        model=payload.model,
        input="Return a compact JSON object confirming the integration check.",
        instructions="Return only JSON matching the requested schema.",
        max_output_tokens=32,
        temperature=0,
        metadata=ConcentrateMetadata(
            app="turbulence",
            run_id=payload.run_id,
            request_id=payload.request_id,
            scenario_id=payload.scenario_id,
        ),
        text=TextOptions(
            format=JsonSchemaFormat(
                name="turbulence_concentrate_check",
                schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "ok": {"type": "boolean"},
                        "message": {"type": "string"},
                    },
                    "required": ["ok", "message"],
                },
            )
        ),
        store=False,
    )

    try:
        response = await client.create_response(request)
    except ConcentrateError as exc:
        raise _http_error(exc) from exc

    return ConcentrateTestResponse(response=response)


def _status_response(health: ConcentrateHealth) -> ConcentrateStatusResponse:
    return ConcentrateStatusResponse(
        mode=health.mode,
        status=health.status,
        is_mock=health.is_mock,
        configured=health.configured,
    )


def _http_error(exc: ConcentrateError) -> HTTPException:
    if isinstance(exc, ConcentrateConfigurationError):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, ConcentrateAuthenticationError):
        code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(exc, ConcentrateInsufficientCreditsError):
        code = status.HTTP_402_PAYMENT_REQUIRED
    elif isinstance(exc, ConcentrateProviderDependencyError):
        code = status.HTTP_424_FAILED_DEPENDENCY
    elif isinstance(exc, ConcentrateRateLimitError):
        code = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(exc, ConcentrateTimeoutError):
        code = status.HTTP_504_GATEWAY_TIMEOUT
    elif isinstance(exc, ConcentrateMalformedResponseError):
        code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(exc, ConcentrateGatewayError):
        code = status.HTTP_502_BAD_GATEWAY
    else:
        code = status.HTTP_502_BAD_GATEWAY

    return HTTPException(status_code=code, detail=str(exc))

