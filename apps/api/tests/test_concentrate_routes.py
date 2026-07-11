from fastapi.testclient import TestClient

from turbulence_api.app import create_app


def test_concentrate_status_uses_mock_mode_without_exposing_credentials() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/integrations/concentrate/status")

    assert response.status_code == 200
    assert response.json() == {
        "mode": "mock",
        "status": "ok",
        "is_mock": True,
        "configured": True,
    }

