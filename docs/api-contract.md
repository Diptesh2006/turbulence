# API Contract

The Turbulence backend exposes a public local API under `/api`. Authentication is intentionally not implemented at this stage.

Errors use problem-detail responses:

```json
{
  "type": "about:blank",
  "title": "Validation Error",
  "status": 422,
  "detail": "Request validation failed",
  "instance": "/api/scenarios"
}
```

## Health

`GET /api/health`

Returns service name, status, version, environment, and simulation mode.

## Workloads

`GET /api/workloads`

Returns available workload summaries. Listing responses do not include raw prompts.

## Routing Profiles

`GET /api/routing-profiles`

Returns supported routing profile types:

- `single_provider`
- `gateway_auto`
- `resilient_route`

`gateway_auto` documents supported metrics: `cost`, `performance`, `p50_latency`, `uptime`.

## Scenarios

`GET /api/scenarios`

Returns all stored scenarios.

`GET /api/scenarios/{id}`

Returns one scenario or `404`.

`POST /api/scenarios`

Creates a scenario.

`PUT /api/scenarios/{id}`

Updates an existing scenario. The path id must match the body id.

`DELETE /api/scenarios/{id}`

Deletes a scenario only when no historical run depends on it. Returns `409` when runs exist.

Scenario validation:

- workload must exist
- routing profile must satisfy its own shape constraints
- SLO values must be positive when provided
- fault windows, probability, and duration are validated by the fault schema
- `request_count` must not exceed `MAX_SIMULATION_REQUESTS`
- `max_concurrency` must not exceed `MAX_SIMULATION_CONCURRENCY`
- `max_concurrency` must not exceed `request_count`

Example scenario:

```json
{
  "id": "support-triage-smoke",
  "mode": "mock",
  "workload_name": "support_ticket_triage",
  "request_count": 3,
  "seed": 42,
  "rate_per_second": 2,
  "max_concurrency": 2,
  "model": "mock-fast",
  "max_output_tokens": 96,
  "recovery_time_slo_ms": 1000,
  "latency_slo_ms": 2000,
  "routing_profile": {
    "id": "single-mock",
    "type": "single_provider",
    "routes": [{"model": "mock-fast", "provider": "mock"}]
  },
  "fault_rules": []
}
```

## Seeded Presets

The backend seeds three scenarios idempotently during startup. Model identifiers come from backend configuration:

- `OPENAI_MODEL_ID`
- `ANTHROPIC_MODEL_ID`
- `GOOGLE_MODEL_ID`
- `MOCK_MODEL_ID`

`preset-clear-skies`

- Purpose: establish baseline
- Mode: `concentrate_native` in live environments, `mock` otherwise
- 12 logical requests
- concurrency 2
- no injected faults
- gateway auto routing
- performance metric

`preset-provider-mayday`

- Purpose: show deterministic failover and recovery
- Mode: `deterministic_chaos`
- 15 logical requests
- concurrency 3
- resilient route using OpenAI primary, Anthropic fallback, and Google fallback
- `provider_outage` against the primary provider during the middle third of the estimated run

`preset-perfect-storm`

- Purpose: demonstrate compound degradation
- Mode: `deterministic_chaos`
- 18 logical requests
- concurrency 3
- resilient route
- starts with latency spike
- follows with a short rate-limit burst
- corrupts a small percentage of structured outputs

Builder validation mirrors backend validation:

- request and concurrency limits are enforced by `MAX_SIMULATION_REQUESTS` and `MAX_SIMULATION_CONCURRENCY`
- fault probability must be between 0 and 1
- fault windows must fit within estimated run duration: `request_count / rate_per_second * 1000`
- resilient routing requires at least two routes
- duplicate routes are rejected
- live mode shows a credit-consumption warning
- the UI shows maximum possible gateway calls, not a fabricated dollar estimate

## Runs

`POST /api/runs`

Creates a run from either `scenario_id` or an inline `scenario`. Supports optional `Idempotency-Key`.

```json
{"scenario_id": "support-triage-smoke"}
```

`POST /api/runs/{id}/start`

Starts a created run. Supports optional `Idempotency-Key`.

`POST /api/runs/{id}/cancel`

Requests cooperative cancellation.

`GET /api/runs?page=1&page_size=25`

Returns paginated run summaries. Listing responses omit raw prompts and upstream response bodies.

`GET /api/runs/{id}`

Returns the stored run, including requests and attempts. The stored model contains normalized metadata and scores, not raw prompts.

`GET /api/runs/{id}/events`

Server-Sent Events stream. Event ids are sequence numbers. `Last-Event-ID` replays persisted events after that sequence. Heartbeats are sent as SSE comments. The stream closes after `run.completed`, `run.failed`, or `run.cancelled`.

`GET /api/runs/{id}/report`

Returns the post-flight report for the run. The report includes:

- run metadata: run id, scenario id, run state, mode, created and updated timestamps
- deterministic executive verdict
- metrics snapshot and resilience score breakdown
- incident timeline
- route analysis
- failure analysis
- deterministic recommendations
- optional AI analysis status

Executive verdicts are deterministic and are never LLM-judged:

- `production_ready`: run is `completed`, availability is at least `99%`, correctness is at least `95%`, no fatal error exists, and no degradation signals were measured.
- `degraded_but_recovered`: run is `completed`, availability is greater than zero, and fallback, validation, fault, error, failed request, or latency degradation occurred.
- `unreliable`: run is `failed`, a fatal run error exists, availability is below `94%`, or correctness is below `95%`.
- `inconclusive`: run is cancelled, required metrics are missing, or no logical request completed successfully.

Unknown costs and token values remain `null`. Simulated provider outage injections are labelled simulated and must not be described as real upstream incidents.

## Comparisons

`POST /api/comparisons`

Compares two runs by their metric snapshots.

```json
{
  "baseline_run_id": "run-a",
  "candidate_run_id": "run-b"
}
```

Comparison differences include before, after, absolute difference, percentage difference, metric direction, and change kind. Percentage difference is `null` when the baseline is zero or unknown.

Higher is better for:

- resilience score
- availability
- correctness
- schema validity
- fallback recovery
- successful requests

Lower is better for:

- p50 and p95 latency
- time to recovery
- failed requests
- real and simulated errors
- total cost
- cost per successful request

## Agent Safety Lab

The `/api/agent-safety` routes evaluate deterministic scenarios against an in-memory policy set. These results are simulated and do not represent actions on real systems.

`GET /api/agent-safety/scenarios`

Returns seeded agent scenarios and `source: "simulated"`.

`GET /api/agent-safety/policies`

Returns policy rules in priority order.

`PUT /api/agent-safety/policies/{id}`

Updates a policy rule for subsequent evaluations. The path id must match the rule id. Replay the prior run after a policy change to compare outcomes.

`POST /api/agent-safety/runs`

Evaluates a scenario immediately. The request accepts `scenario_id` and an optional non-negative `seed`; omitting the seed uses the scenario's default seed.

`GET /api/agent-safety/runs` and `GET /api/agent-safety/runs/{id}`

Return simulated run records and the ordered action trajectory, including context, matched rule, decision, approval resolution, fixture result, and a sequenced simulated event trail.

`POST /api/agent-safety/runs/{id}/replay`

Reruns the same scenario and seed under the current policy set. Run history and policy edits are in memory and reset when the API process restarts.

Decisions are `ALLOW`, `AUDIT`, `WARN`, `REQUIRE_APPROVAL`, and `BLOCK`. `REQUIRE_APPROVAL` resolves according to the scenario's deterministic approval setting; no human reviewer is implied. Each action reports expected and actual decisions. Critical unmatched actions fail closed. Simulated fixture outcomes never invoke a shell, filesystem, database, network, credential, or MCP tool.

## Concentrate Integration

`GET /api/integrations/concentrate/status`

Returns Concentrate adapter mode/status without exposing the API key or partial key.

`POST /api/integrations/concentrate/test`

Sends one short structured-output request only in live mode. It never returns the API key or a partial key.

## Notes

- No end-user accounts, billing, Redis, Celery, or Kubernetes are part of this API. The invite-only hosted demo adds a shared web passcode and a server-to-server token; neither provides per-user identity or authorization.
- Provider failures, costs, tokens, and routing decisions are never fabricated.
- Injected faults are labeled `simulated`.
- Concentrate-specific payload assumptions remain behind the Concentrate adapter.

# BreakMyBot integration contract

`GET /api/integrations/breakmybot/capabilities` returns the `breakmybot-turbulence-v1` manifest. Turbulence currently simulates faults at its own Concentrate routing boundary and records simulated provenance. It does not inject tool faults into an arbitrary external agent or provide an external-target HTTP fault proxy. Agent-safety scenario results are seeded simulator fixtures, not observations of the connected BreakMyBot target. Consumers must not count these results toward a target application's reliability score.
