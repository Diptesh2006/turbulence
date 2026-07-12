import pytest
from fastapi.testclient import TestClient

from turbulence_api.app import create_app
from turbulence_api.core.config import Settings
from turbulence_api.repositories.scenarios import ScenarioRepository
from turbulence_api.services.presets import build_seeded_presets
from turbulence_api.services.scenarios import ScenarioService
from turbulence_api.simulation.store import InMemoryRunStore
from turbulence_api.workloads.registry import build_default_registry


def test_presets_are_seeded_idempotently() -> None:
    with TestClient(create_app()) as client:
        first = client.get("/api/scenarios").json()["items"]
        second = client.get("/api/scenarios").json()["items"]

    ids = {item["id"] for item in first}
    assert {"preset-clear-skies", "preset-provider-mayday", "preset-perfect-storm"} <= ids
    assert len(first) == len(second)
    assert len([item for item in first if item["id"] == "preset-clear-skies"]) == 1


def test_provider_mayday_preset_shape() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/scenarios/preset-provider-mayday")

    scenario = response.json()["scenario"]
    assert scenario["mode"] == "mock"
    assert scenario["request_count"] == 15
    assert scenario["max_concurrency"] == 3
    assert scenario["routing_profile"]["type"] == "resilient_route"
    assert [route["provider"] for route in scenario["routing_profile"]["routes"]] == [
        "openai",
        "anthropic",
        "google",
    ]
    assert scenario["fault_rules"][0]["type"] == "provider_outage"
    assert scenario["fault_rules"][0]["target_provider"] == "openai"


def test_live_backend_seeded_presets_remain_safe_mock_by_default() -> None:
    presets = build_seeded_presets(Settings(CNAI_MODE="live"))

    assert {preset.id: preset.mode for preset in presets} == {
        "preset-clear-skies": "mock",
        "preset-provider-mayday": "mock",
        "preset-perfect-storm": "mock",
    }


@pytest.mark.asyncio
async def test_existing_seeded_mock_scenarios_do_not_become_live_silently() -> None:
    repository = ScenarioRepository()
    service = ScenarioService(
        repository=repository,
        run_store=InMemoryRunStore(),
        workload_registry=build_default_registry(),
        settings=Settings(CNAI_MODE="live"),
    )
    original = build_seeded_presets(Settings(CNAI_MODE="mock"))[0]
    await service.seed_presets([original])
    live_replacement = original.model_copy(update={"mode": "concentrate_native"})

    await service.seed_presets([live_replacement])

    stored = await service.get(original.id)
    assert stored.mode == "mock"


def test_builder_validation_rejects_duplicate_routes() -> None:
    payload = _scenario_payload()
    payload["routing_profile"]["routes"] = [
        {"model": "gpt-4.1-mini", "provider": "openai"},
        {"model": "gpt-4.1-mini", "provider": "openai"},
    ]

    with TestClient(create_app()) as client:
        response = client.post("/api/scenarios", json=payload)

    assert response.status_code == 422
    assert "duplicate routes" in response.json()["detail"]


def test_builder_validation_rejects_fault_windows_outside_estimated_duration() -> None:
    payload = _scenario_payload()
    payload["fault_rules"] = [
        {
            "id": "too-late",
            "type": "latency_spike",
            "start_after_ms": 10_000,
            "duration_ms": 1000,
            "probability": 1,
            "parameters": {"delay_ms": 100},
            "enabled": True,
        }
    ]

    with TestClient(create_app()) as client:
        response = client.post("/api/scenarios", json=payload)

    assert response.status_code == 422
    assert "fault window" in response.json()["detail"]


def _scenario_payload() -> dict:
    return {
        "id": "builder-validation",
        "mode": "deterministic_chaos",
        "workload_name": "support_ticket_triage",
        "request_count": 6,
        "seed": 42,
        "rate_per_second": 2,
        "max_concurrency": 2,
        "model": "gpt-4.1-mini",
        "max_output_tokens": 96,
        "recovery_time_slo_ms": 1000,
        "latency_slo_ms": 2000,
        "routing_profile": {
            "id": "builder-resilient",
            "type": "resilient_route",
            "routes": [
                {"model": "gpt-4.1-mini", "provider": "openai"},
                {"model": "claude-3-5-haiku-latest", "provider": "anthropic"},
            ],
        },
        "fault_rules": [],
    }
