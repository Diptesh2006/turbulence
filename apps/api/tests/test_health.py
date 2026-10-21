from fastapi.testclient import TestClient

from turbulence_api.app import create_app


def test_health_returns_service_metadata() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "turbulence-api",
        "status": "ok",
        "version": "0.1.0",
        "environment": "development",
        "simulation_mode": "disabled",
    }


def test_breakmybot_manifest_does_not_claim_external_target_injection() -> None:
    client = TestClient(create_app())

    response = client.get("/api/integrations/breakmybot/capabilities")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["contract"] == "breakmybot-turbulence-v1"
    assert manifest["capabilities"]["provider_boundary_simulation"] is True
    assert manifest["capabilities"]["external_target_tool_injection"] is False
    assert manifest["event_source"] == "simulated"


def test_root_returns_service_metadata_and_links() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "turbulence-api",
        "status": "ok",
        "version": "0.1.0",
        "health_endpoint": "/api/health",
        "docs_url": "/docs",
    }


def test_documentation_routes_are_mounted_at_root() -> None:
    client = TestClient(create_app())

    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/redoc").status_code == 200
