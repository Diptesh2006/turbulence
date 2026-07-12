from fastapi.testclient import TestClient

from turbulence_api.app import create_app
from turbulence_api.core.config import get_settings


def test_concentrate_status_uses_mock_mode_without_exposing_credentials(monkeypatch) -> None:
    monkeypatch.setenv("CNAI_MODE", "mock")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.get("/api/integrations/concentrate/status")
    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {
        "mode": "mock",
        "status": "ok",
        "is_mock": True,
        "configured": True,
    }


def test_concentrate_status_reflects_live_mode_without_exposing_credentials(monkeypatch) -> None:
    monkeypatch.setenv("CNAI_MODE", "live")
    monkeypatch.setenv("CNAI_API_KEY", "")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.get("/api/integrations/concentrate/status")
    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {
        "mode": "live",
        "status": "not_configured",
        "is_mock": False,
        "configured": False,
    }
