from functools import partial

from fastapi.testclient import TestClient

from turbulence_api.app import create_app
from turbulence_api.domain.routing import RouteTarget, RoutingProfile
from turbulence_api.simulation.models import ScenarioConfig


def test_run_events_replays_after_last_event_id() -> None:
    with TestClient(create_app()) as client:
        orchestrator = client.app.state.simulation_orchestrator
        scenario = ScenarioConfig(
            id="scenario-sse",
            workload_name="support_ticket_triage",
            request_count=1,
            seed=7,
            rate_per_second=100,
            max_concurrency=1,
            model="mock-fast",
            max_output_tokens=128,
            routing_profile=RoutingProfile.single_provider(
                id="single",
                route=RouteTarget(model="mock-fast", provider="mock"),
            ),
        )
        client.portal.call(
            partial(orchestrator.run_to_completion, scenario, run_id="run-sse")
        )

        response = client.get("/api/runs/run-sse/events", headers={"Last-Event-ID": "1"})
        query_response = client.get("/api/runs/run-sse/events?last_event_id=1")

    assert response.status_code == 200
    assert "id: 1\n" not in response.text
    assert "id: 2\n" in response.text
    assert "event: run.started\n" in response.text
    assert "event: run.completed\n" in response.text
    assert query_response.status_code == 200
    assert "id: 1\n" not in query_response.text
    assert "id: 2\n" in query_response.text
