from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

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
    ConcentrateModel,
    ConcentrateResponseRequest,
    Cost,
    NormalizedConcentrateResponse,
    Usage,
)

logger = logging.getLogger(__name__)


class ConcentrateClientProtocol(Protocol):
    async def health_check(self) -> ConcentrateHealth: ...
    async def list_models(self) -> list[ConcentrateModel]: ...
    async def create_response(
        self, request: ConcentrateResponseRequest
    ) -> NormalizedConcentrateResponse: ...
    async def aclose(self) -> None: ...


class ConcentrateClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._configured = bool(api_key)
        self._owns_client = http_client is None
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "turbulence-api/0.1.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            headers=headers,
        )

    async def health_check(self) -> ConcentrateHealth:
        if not self._configured:
            return ConcentrateHealth(
                mode="live",
                status="not_configured",
                is_mock=False,
                configured=False,
            )

        try:
            response = await self._client.get("/health")
            self._raise_for_status(response)
            return ConcentrateHealth(
                mode="live",
                status="ok",
                is_mock=False,
                configured=True,
            )
        except ConcentrateError:
            raise
        except httpx.TimeoutException as exc:
            raise ConcentrateTimeoutError() from exc
        except httpx.HTTPError as exc:
            logger.warning("Concentrate health check failed: %s", exc.__class__.__name__)
            raise ConcentrateGatewayError("Concentrate health check failed") from exc

    async def list_models(self) -> list[ConcentrateModel]:
        self._require_configured()
        response = await self._request("GET", "/models")
        data = self._parse_json(response)
        models_data = data.get("data", data if isinstance(data, list) else [])
        if not isinstance(models_data, list):
            raise ConcentrateMalformedResponseError("Concentrate models payload is not a list")

        models: list[ConcentrateModel] = []
        for item in models_data:
            if isinstance(item, Mapping) and item.get("id"):
                models.append(
                    ConcentrateModel(
                        id=str(item["id"]),
                        name=_optional_str(item.get("name")),
                        provider=_optional_str(item.get("provider")),
                    )
                )
        return models

    async def create_response(
        self, request: ConcentrateResponseRequest
    ) -> NormalizedConcentrateResponse:
        self._require_configured()
        payload = request.model_dump(by_alias=True, exclude_none=True)
        response = await self._request("POST", "/responses", json=payload)
        data = self._parse_json(response)
        return _normalize_response(data)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _require_configured(self) -> None:
        if not self._configured:
            raise ConcentrateConfigurationError("CNAI_API_KEY is required when CNAI_MODE=live")

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise ConcentrateTimeoutError() from exc
        except httpx.HTTPError as exc:
            logger.warning("Concentrate request failed: %s", exc.__class__.__name__)
            raise ConcentrateGatewayError("Concentrate request failed") from exc

        self._raise_for_status(response)
        return response

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return

        message = _extract_error_message(response)
        if response.status_code == 401:
            raise ConcentrateAuthenticationError(message, status_code=response.status_code)
        if response.status_code == 402:
            raise ConcentrateInsufficientCreditsError(message, status_code=response.status_code)
        if response.status_code == 424:
            raise ConcentrateProviderDependencyError(message, status_code=response.status_code)
        if response.status_code == 429:
            raise ConcentrateRateLimitError(message, status_code=response.status_code)
        if response.status_code == 400:
            raise ConcentrateGatewayError(message, status_code=response.status_code)
        if response.status_code >= 500:
            raise ConcentrateGatewayError(message, status_code=response.status_code)
        raise ConcentrateGatewayError(message, status_code=response.status_code)

    @staticmethod
    def _parse_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise ConcentrateMalformedResponseError("Concentrate returned invalid JSON") from exc


def _extract_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except json.JSONDecodeError:
        return f"Concentrate request failed with HTTP {response.status_code}"

    if isinstance(data, Mapping):
        error = data.get("error")
        if isinstance(error, Mapping):
            message = error.get("message") or error.get("code")
            if message:
                return str(message)
        if isinstance(error, str):
            return error
        if data.get("message"):
            return str(data["message"])
    return f"Concentrate request failed with HTTP {response.status_code}"


def _normalize_response(data: Any) -> NormalizedConcentrateResponse:
    if not isinstance(data, Mapping):
        raise ConcentrateMalformedResponseError("Concentrate response payload is not an object")

    response_id = _first_str(data, "id", "response_id")
    if response_id is None:
        raise ConcentrateMalformedResponseError("Concentrate response is missing id")

    return NormalizedConcentrateResponse(
        id=response_id,
        model=_first_str(data, "model", "returned_model"),
        provider=_parse_provider(data),
        assistant_text=_parse_assistant_text(data),
        usage=_parse_usage(data.get("usage")),
        cost=_parse_cost(data.get("cost")),
        status=_optional_str(data.get("status")),
        errors=_parse_errors(data.get("error") or data.get("errors")),
        is_mock=False,
    )


def _parse_provider(data: Mapping[str, Any]) -> str | None:
    provider = data.get("provider")
    if provider is not None:
        return _optional_str(provider)

    routing = data.get("routing")
    if isinstance(routing, Mapping):
        return _optional_str(routing.get("provider"))

    provider_info = data.get("provider_info")
    if isinstance(provider_info, Mapping):
        return _optional_str(provider_info.get("name") or provider_info.get("id"))
    return None


def _parse_assistant_text(data: Mapping[str, Any]) -> str | None:
    direct = _first_str(data, "output_text", "text", "assistant_text")
    if direct:
        return direct

    output = data.get("output")
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if isinstance(item, Mapping):
                content = item.get("content")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    parts.extend(_text_parts(content))
        return "\n".join(parts) if parts else None

    choices = data.get("choices")
    if isinstance(choices, list):
        return _parse_choices_text(choices)
    return None


def _parse_choices_text(choices: list[Any]) -> str | None:
    parts: list[str] = []
    for choice in choices:
        if not isinstance(choice, Mapping):
            continue
        message = choice.get("message")
        if isinstance(message, Mapping):
            content = message.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                parts.extend(_text_parts(content))
        elif isinstance(choice.get("text"), str):
            parts.append(str(choice["text"]))
    return "\n".join(parts) if parts else None


def _text_parts(content: list[Any]) -> list[str]:
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, Mapping):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return parts


def _parse_usage(raw_usage: Any) -> Usage | None:
    if raw_usage is None:
        return None
    if not isinstance(raw_usage, Mapping):
        raise ConcentrateMalformedResponseError("Concentrate usage payload is malformed")

    return Usage(
        input_tokens=_optional_int(
            raw_usage.get("input_tokens")
            or raw_usage.get("prompt_tokens")
            or raw_usage.get("input")
        ),
        output_tokens=_optional_int(
            raw_usage.get("output_tokens")
            or raw_usage.get("completion_tokens")
            or raw_usage.get("output")
        ),
        total_tokens=_optional_int(raw_usage.get("total_tokens") or raw_usage.get("total")),
    )


def _parse_cost(raw_cost: Any) -> Cost | None:
    if raw_cost is None:
        return None
    if isinstance(raw_cost, Mapping):
        return Cost(total=_optional_float(raw_cost.get("total")))
    raise ConcentrateMalformedResponseError("Concentrate cost payload is malformed")


def _parse_errors(raw_errors: Any) -> list[str]:
    if raw_errors is None:
        return []
    if isinstance(raw_errors, str):
        return [raw_errors]
    if isinstance(raw_errors, Mapping):
        message = raw_errors.get("message") or raw_errors.get("code")
        return [str(message)] if message else []
    if isinstance(raw_errors, list):
        errors: list[str] = []
        for item in raw_errors:
            if isinstance(item, str):
                errors.append(item)
            elif isinstance(item, Mapping):
                message = item.get("message") or item.get("code")
                if message:
                    errors.append(str(message))
        return errors
    return []


def _first_str(data: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        parsed = _optional_str(value)
        if parsed is not None:
            return parsed
    return None


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
