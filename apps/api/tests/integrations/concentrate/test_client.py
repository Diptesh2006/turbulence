from __future__ import annotations

import httpx
import pytest
import respx

from turbulence_api.integrations.concentrate.client import ConcentrateClient
from turbulence_api.integrations.concentrate.exceptions import (
    ConcentrateMalformedResponseError,
    ConcentrateProviderDependencyError,
    ConcentrateRateLimitError,
    ConcentrateTimeoutError,
)
from turbulence_api.integrations.concentrate.models import (
    ConcentrateMetadata,
    ConcentrateResponseRequest,
)

BASE_URL = "https://unit.test/v1"


def request_payload() -> ConcentrateResponseRequest:
    return ConcentrateResponseRequest(
        model="cnai-test",
        input="short prompt",
        instructions="be brief",
        max_output_tokens=16,
        temperature=0,
        metadata=ConcentrateMetadata(
            app="turbulence",
            run_id="run-1",
            request_id="req-1",
            scenario_id="scenario-1",
        ),
        routing={"strategy": "lowest_latency"},
        store=False,
    )


@pytest.fixture
async def client() -> ConcentrateClient:
    async_client = httpx.AsyncClient(base_url=BASE_URL, timeout=1)
    concentrate = ConcentrateClient(
        api_key="test-key",
        base_url=BASE_URL,
        timeout_seconds=1,
        http_client=async_client,
    )
    yield concentrate
    await async_client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_create_response_parses_successful_response(client: ConcentrateClient) -> None:
    respx.post(f"{BASE_URL}/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "resp-1",
                "model": "cnai-test-returned",
                "provider": "provider-a",
                "output_text": "hello",
                "usage": {
                    "input_tokens": 3,
                    "output_tokens": 2,
                    "total_tokens": 5,
                },
                "cost": {"total": 0.001},
                "status": "completed",
            },
        )
    )

    response = await client.create_response(request_payload())

    assert response.id == "resp-1"
    assert response.model == "cnai-test-returned"
    assert response.provider == "provider-a"
    assert response.assistant_text == "hello"
    assert response.usage is not None
    assert response.usage.total_tokens == 5
    assert response.cost is not None
    assert response.cost.total == 0.001
    assert response.status == "completed"
    assert response.is_mock is False


@pytest.mark.asyncio
@respx.mock
async def test_create_response_keeps_usage_null_when_missing(client: ConcentrateClient) -> None:
    respx.post(f"{BASE_URL}/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "resp-2",
                "model": "cnai-test",
                "output_text": "hello",
                "cost": {"total": 0.001},
            },
        )
    )

    response = await client.create_response(request_payload())

    assert response.usage is None


@pytest.mark.asyncio
@respx.mock
async def test_create_response_keeps_cost_null_when_missing(client: ConcentrateClient) -> None:
    respx.post(f"{BASE_URL}/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "resp-3",
                "model": "cnai-test",
                "output_text": "hello",
                "usage": {"total_tokens": 5},
            },
        )
    )

    response = await client.create_response(request_payload())

    assert response.cost is None


@pytest.mark.asyncio
@respx.mock
async def test_create_response_maps_424(client: ConcentrateClient) -> None:
    respx.post(f"{BASE_URL}/responses").mock(
        return_value=httpx.Response(
            424,
            json={"error": {"message": "provider unavailable"}},
        )
    )

    with pytest.raises(ConcentrateProviderDependencyError):
        await client.create_response(request_payload())


@pytest.mark.asyncio
@respx.mock
async def test_create_response_maps_429(client: ConcentrateClient) -> None:
    respx.post(f"{BASE_URL}/responses").mock(
        return_value=httpx.Response(
            429,
            json={"error": {"message": "too many requests"}},
        )
    )

    with pytest.raises(ConcentrateRateLimitError):
        await client.create_response(request_payload())


@pytest.mark.asyncio
@respx.mock
async def test_create_response_maps_timeout(client: ConcentrateClient) -> None:
    respx.post(f"{BASE_URL}/responses").mock(side_effect=httpx.ReadTimeout("timeout"))

    with pytest.raises(ConcentrateTimeoutError):
        await client.create_response(request_payload())


@pytest.mark.asyncio
@respx.mock
async def test_create_response_rejects_malformed_json(client: ConcentrateClient) -> None:
    respx.post(f"{BASE_URL}/responses").mock(
        return_value=httpx.Response(
            200,
            content=b"not json",
            headers={"content-type": "application/json"},
        )
    )

    with pytest.raises(ConcentrateMalformedResponseError):
        await client.create_response(request_payload())

