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

