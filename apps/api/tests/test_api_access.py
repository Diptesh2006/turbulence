from fastapi.testclient import TestClient

from turbulence_api import app as app_module
from turbulence_api.app import create_app
from turbulence_api.core.config import Settings


def test_non_development_api_requires_internal_token(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: Settings(ENVIRONMENT="staging", API_ACCESS_TOKEN="t" * 32),
    )

    with TestClient(create_app()) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/agent-safety/scenarios").status_code == 401
        authorized = client.get(
            "/api/agent-safety/scenarios",
            headers={"X-Internal-API-Token": "t" * 32},
        )
        assert authorized.status_code == 200
        assert client.get("/docs").status_code == 401


def test_non_development_api_fails_closed_without_token(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: Settings(ENVIRONMENT="staging"),
    )

    with TestClient(create_app()) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/agent-safety/scenarios").status_code == 503
