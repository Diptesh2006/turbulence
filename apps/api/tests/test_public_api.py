from __future__ import annotations

import time

from fastapi.testclient import TestClient

from turbulence_api.app import create_app


def scenario_payload(scenario_id: str = "api-scenario") -> dict:
    return {
        "id": scenario_id,
        "workload_name": "support_ticket_triage",
        "request_count": 1,
        "seed": 7,
        "rate_per_second": 100,
        "max_concurrency": 1,
        "model": "mock-fast",
        "max_output_tokens": 96,
        "recovery_time_slo_ms": 1000,
        "latency_slo_ms": 2000,
        "routing_profile": {
            "id": "single",
            "type": "single_provider",
            "routes": [{"model": "mock-fast", "provider": "mock"}],
        },
        "fault_rules": [],
    }


def test_catalog_endpoints() -> None:
    with TestClient(create_app()) as client:
        workloads = client.get("/api/workloads")
        profiles = client.get("/api/routing-profiles")

    assert workloads.status_code == 200
    assert workloads.json()[0]["name"] == "support_ticket_triage"
    assert profiles.status_code == 200
    assert {profile["type"] for profile in profiles.json()} == {
        "single_provider",
        "gateway_auto",
        "resilient_route",
    }


def test_agent_safety_scenarios_runs_and_replay() -> None:
    with TestClient(create_app()) as client:
        scenarios = client.get("/api/agent-safety/scenarios")
        policies = client.get("/api/agent-safety/policies")
        created = client.post(
            "/api/agent-safety/runs",
            json={"scenario_id": "agent-destructive-command", "seed": 8},
        )
        run_id = created.json()["id"]
        replay = client.post(f"/api/agent-safety/runs/{run_id}/replay")
        fetched = client.get(f"/api/agent-safety/runs/{run_id}")
        policy_response = client.get("/api/agent-safety/policies")
        policies = policy_response.json()["items"]
        block_rule = next(rule for rule in policies if rule["id"] == "block-critical-actions")
        block_rule["decision"] = "WARN"
        changed = client.put("/api/agent-safety/policies/block-critical-actions", json=block_rule)
        changed_replay = client.post(f"/api/agent-safety/runs/{run_id}/replay")

    assert scenarios.status_code == 200
    assert scenarios.json()["source"] == "simulated"
    assert len(scenarios.json()["items"]) >= 5
    assert policy_response.status_code == 200
    assert created.status_code == 201
    assert created.json()["actions"][0]["simulated_result"]["executed"] is False
    assert replay.status_code == 201
    assert replay.json()["seed"] == 8
    assert replay.json()["actions"][0]["decision"] == fetched.json()["actions"][0]["decision"]
    assert changed.status_code == 200
    assert changed_replay.json()["verdict"] == "unsafe"
    assert changed_replay.json()["actions"][0]["decision"] == "WARN"


def test_scenario_crud_and_delete_safety() -> None:
    with TestClient(create_app()) as client:
        create = client.post("/api/scenarios", json=scenario_payload())
        assert create.status_code == 201
        assert client.get("/api/scenarios/api-scenario").status_code == 200

        updated_payload = scenario_payload()
        updated_payload["seed"] = 8
        update = client.put("/api/scenarios/api-scenario", json=updated_payload)
        assert update.status_code == 200
        assert update.json()["scenario"]["seed"] == 8

        delete_free = client.delete("/api/scenarios/api-scenario")
        assert delete_free.status_code == 204

        assert client.post("/api/scenarios", json=scenario_payload()).status_code == 201
        run = client.post("/api/runs", json={"scenario_id": "api-scenario"})
        assert run.status_code == 201
        blocked_delete = client.delete("/api/scenarios/api-scenario")

    assert blocked_delete.status_code == 409
    assert blocked_delete.json()["title"] == "Conflict"


def test_run_lifecycle_idempotency_pagination_report_and_comparison() -> None:
    with TestClient(create_app()) as client:
        assert client.post("/api/scenarios", json=scenario_payload("scenario-a")).status_code == 201
        assert client.post("/api/scenarios", json=scenario_payload("scenario-b")).status_code == 201

        first = client.post(
            "/api/runs",
            json={"scenario_id": "scenario-a"},
            headers={"Idempotency-Key": "create-a"},
        )
        repeated = client.post(
            "/api/runs",
            json={"scenario_id": "scenario-a"},
            headers={"Idempotency-Key": "create-a"},
        )
        assert first.status_code == 201
        assert repeated.json()["run"]["id"] == first.json()["run"]["id"]
        run_a = first.json()["run"]["id"]

        start = client.post(f"/api/runs/{run_a}/start", headers={"Idempotency-Key": "start-a"})
        repeat_start = client.post(
            f"/api/runs/{run_a}/start",
            headers={"Idempotency-Key": "start-a"},
        )
        assert start.status_code == 200
        assert repeat_start.status_code == 200
        _wait_terminal(client, run_a)

        second = client.post("/api/runs", json={"scenario_id": "scenario-b"})
        run_b = second.json()["run"]["id"]
        assert client.post(f"/api/runs/{run_b}/start").status_code == 200
        _wait_terminal(client, run_b)

        listing = client.get("/api/runs?page=1&page_size=1")
        report = client.get(f"/api/runs/{run_a}/report")
        comparison = client.post(
            "/api/comparisons",
            json={"baseline_run_id": run_a, "candidate_run_id": run_b},
        )

    assert listing.status_code == 200
    assert listing.json()["page"] == 1
    assert listing.json()["page_size"] == 1
    assert listing.json()["total"] == 2
    assert "requests" not in listing.json()["items"][0]
    assert report.status_code == 200
    assert report.json()["report"]["metrics"]["total_logical_requests"] == 1
    assert comparison.status_code == 200
    assert comparison.json()["comparison"]["baseline_run_id"] == run_a


def test_problem_detail_for_invalid_traffic_settings() -> None:
    payload = scenario_payload("unsafe")
    payload["request_count"] = 1
    payload["max_concurrency"] = 2

    with TestClient(create_app()) as client:
        response = client.post("/api/scenarios", json=payload)

    assert response.status_code == 422
    assert response.json()["title"] == "Validation Error"
    assert "max_concurrency" in response.json()["detail"]


def test_cancel_run_endpoint() -> None:
    payload = scenario_payload("cancel-scenario")
    payload["request_count"] = 3
    payload["rate_per_second"] = 1

    with TestClient(create_app()) as client:
        assert client.post("/api/scenarios", json=payload).status_code == 201
        run = client.post("/api/runs", json={"scenario_id": "cancel-scenario"}).json()["run"]
        assert client.post(f"/api/runs/{run['id']}/start").status_code == 200
        cancel = client.post(f"/api/runs/{run['id']}/cancel")

    assert cancel.status_code == 200
    assert cancel.json()["run"]["state"] in {"cancelling", "cancelled"}


def _wait_terminal(client: TestClient, run_id: str) -> dict:
    for _ in range(100):
        run = client.get(f"/api/runs/{run_id}").json()["run"]
        if run["state"] in {"completed", "failed", "cancelled"}:
            return run
        time.sleep(0.02)
    raise AssertionError("run did not reach terminal state")
