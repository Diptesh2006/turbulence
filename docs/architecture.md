# Architecture

Turbulence is organized as a monorepo with a FastAPI backend and a Next.js cockpit UI.

## High-Level Data Flow

```text
Operator
  -> Cockpit UI
  -> REST command API
  -> Simulation orchestration layer
  -> Concentrate adapter
  -> Concentrate AI / model providers
  -> Normalized events
  -> Server-Sent Events stream
  -> Cockpit UI
  -> Post-flight report store
```

## Components

### Cockpit UI

The web app sends REST commands to start, inspect, and eventually stop simulation runs. It consumes Server-Sent Events for live run telemetry. The initial scaffold only displays backend health.

### API

The FastAPI app owns command validation, configuration, persistence boundaries, and live event streaming. It exposes `/api/health` now and reserves future endpoints for simulation commands and reports.

### Simulation Orchestration

The orchestration layer will generate deterministic workloads, apply seeded fault injection at the client boundary, and evaluate fallback behavior. It is not implemented in this scaffold.

Routing and fault-injection primitives exist as domain modules, but they do not yet form a full simulation engine.

`SimulationOrchestrator` in `turbulence_api.simulation.orchestrator` is the first asynchronous execution layer. It loads a scenario, selects workload fixtures deterministically from the scenario seed, paces request generation by `rate_per_second`, enforces bounded concurrency with an asyncio semaphore, selects routes, applies pre-call and post-response faults, calls Concentrate only when a pre-call fault does not block the attempt, validates/scored outputs locally, advances fallback routes according to policy, persists in-process request/attempt/event records, updates metrics after each completed request, and supports cooperative cancellation.

The run state machine is strict:

```text
created -> running -> completed
created -> running -> failed
created -> running -> cancelling -> cancelled
```

Invalid transitions raise an error. On cancellation or fatal failure, queued/running requests and started attempts are marked `abandoned`.

This is still not final reporting logic. The current persistence implementation is in-process memory for orchestration and SSE replay; durable database tables can be added when the reporting model is designed.

### Routing Policies

Routing policies live in `turbulence_api.domain.routing`.

`single_provider` contains exactly one ordered route. It is intended to demonstrate brittle behavior because a failed attempt has no client-side fallback.

`gateway_auto` sends `model="auto"` to Concentrate and may include a routing metric of `cost`, `performance`, `p50_latency`, or `uptime`. This is native gateway routing. Turbulence must not claim which provider Concentrate should select or did select unless Concentrate returns that provider in the normalized response.

`resilient_route` contains an ordered route plan with primary and fallback model/provider combinations. Every successful model call still goes through Concentrate. In deterministic chaos mode, Turbulence advances through the ordered route plan only after an injected or real failure. This is simulator-managed deterministic fallback and must be labeled that way in events and reports.

Native routing versus deterministic simulation routing:

- Native routing: Concentrate receives `model="auto"` and owns provider/model selection according to its gateway behavior.
- Deterministic simulation routing: Turbulence owns the ordered fallback plan and advances through that plan after failures. This is not a claim about Concentrate provider incidents or gateway selection.

### Fault Injection

Fault rules live in `turbulence_api.domain.faults`. They are deterministic for the same seed, scenario, rule, target, attempt, and timestamp. Faults never monkey-patch global networking; callers evaluate faults at the client boundary before or after a Concentrate adapter call.

Fault rule fields:

- `id`
- `type`
- `target_provider`
- `target_model`
- `start_after_ms`
- `duration_ms`
- `probability`
- `parameters`
- `enabled`

MVP fault types:

- `provider_outage`: pre-call simulated fault. Produces a simulated `424` and does not send the affected attempt upstream.
- `rate_limit_burst`: pre-call simulated fault. Produces a simulated `429` and `retry_after_ms`.
- `latency_spike`: pre-call simulated delay. Injected delay is recorded separately from upstream latency.
- `malformed_json`: post-response simulated fault. Corrupts a copy of the response before local validation and preserves the original upstream response internally for auditability.

Every affected attempt records fault provenance with `source="simulated"`. Domain events `fault.activated` and `fault.cleared` are also marked with `source="simulated"`. Injected faults must never be described as actual provider incidents.

### Event Bus and SSE

The in-process `EventBus` uses asyncio queues per subscribed run. Events are persisted before publication so disconnected clients do not affect simulation execution.

Each `SimulationEvent` has:

- monotonic `sequence`
- event `type`
- `source` of `real`, `simulated`, or `system`
- timestamp
- run id
- structured payload

The run event stream is exposed at:

```text
GET /api/runs/{run_id}/events
```

SSE behavior:

- SSE event IDs use the persisted sequence number.
- `Last-Event-ID` replays persisted events after that sequence.
- Heartbeats are sent as SSE comments while waiting for new events.
- The stream closes after `run.completed`, `run.failed`, or `run.cancelled`.
- Client disconnects close the subscription only; they do not stop the simulation.

### Metrics and Reports

`MetricsAggregator` computes incremental snapshots for the live UI from the stored run, requests, attempts, and persisted events. `PostFlightReportService` wraps a final snapshot with run metadata after the run is terminal and adds deterministic post-flight analysis: executive verdict, incident timeline, route analysis, failure analysis, and rule-based recommendations.

Unknown upstream values remain `null`. Missing cost, missing token counts, missing latency samples, or missing validation results are never interpreted as zero.

Metric formulas:

- Total logical requests: configured/stored logical request count.
- Total attempts: count of stored attempt records.
- Successful requests: requests with state `completed`.
- Failed requests: requests with state `failed`.
- Availability percentage: `successful_requests / total_logical_requests * 100`; `null` if total is zero.
- Fallback-triggered requests: requests with at least one simulator-managed fallback attempt.
- Successful fallback recoveries: fallback-triggered requests that completed successfully.
- Fallback recovery rate: `successful_fallback_recoveries / fallback_triggered_requests * 100`; `null` when no fallback was triggered.
- Retry count: sum of `max(0, attempts_per_request - 1)`.
- Real error count: count of stored gateway/adapter errors on attempts.
- Simulated error count: count of simulated fault occurrences that produce an error condition, such as simulated HTTP status or corrupted response.
- Schema-valid response rate: `schema_valid_outputs / validated_outputs * 100`; `null` when no validation occurred.
- Category accuracy: `category_correct / schema_valid_outputs * 100`; `null` when no schema-valid outputs exist.
- Priority accuracy: `priority_correct / schema_valid_outputs * 100`; `null` when no schema-valid outputs exist.
- Overall correctness rate: `overall_correct / validated_outputs * 100`; `null` when no validation occurred.
- p50/p95 latency: nearest-rank percentile over available samples. Rank is `ceil(percentile / 100 * sample_count)`.
- End-to-end latency: `request.completed.timestamp - request.queued.timestamp`.
- Upstream latency: measured adapter call duration, excluding injected latency.
- Total injected latency: sum of injected latency samples; `null` when none were injected.
- Input/output/total tokens: sum of available token fields; `null` when no attempts returned that field.
- Total cost: sum of available `cost_total`; `null` when no attempts returned cost.
- Cost per successful request: `total_cost / successful_requests`; `null` when cost is unknown or successful requests is zero.
- Time to recovery after a fault begins: first `fault.activated` timestamp to the first successful fallback `request.completed`; `null` when no such recovery exists.
- Requests by actual model/provider: successful requests grouped by returned model/provider when present, falling back to attempted model/provider and `unknown` provider.
- Error distribution by type: counts simulated fault types/status labels, validation failures, and real gateway errors separately.
- Route-attempt distribution: attempts grouped by `route_index:model/provider`.

Resilience score is transparent and ranges from 0 to 100:

- Availability: 30 points from `availability_percentage / 100 * 30`.
- Recovery against configured recovery-time SLO: 20 points. Full points when recovery time is at or below SLO; otherwise `recovery_slo_ms / time_to_recovery_ms * 20`.
- Fallback recovery rate: 20 points from `fallback_recovery_rate / 100 * 20`.
- Correctness: 15 points from `overall_correctness_rate / 100 * 15`.
- p95 latency against configured latency SLO: 15 points. Full points when p95 latency is at or below SLO; otherwise `latency_slo_ms / p95_latency_ms * 15`.

When a component is not applicable, it is excluded and recorded with a reason. Applicable components are reweighted proportionally: `sum(earned applicable points) / sum(max applicable points) * 100`.

`CompareRunsService` compares two metric snapshots and returns absolute differences plus percentage differences where the baseline value is numeric and non-zero.

Post-flight verdicts are deterministic and threshold-based:

- `production_ready`: run state is `completed`, availability is at least 99%, correctness is at least 95%, no unresolved fatal error exists, and no degradation signals were measured.
- `degraded_but_recovered`: run state is `completed`, availability is greater than zero, and at least one degradation signal occurred, including failed requests, fallback use, validation degradation, simulated faults, real errors, or p95 latency above SLO.
- `unreliable`: run state is `failed`, a fatal run error exists, availability is below 94%, or correctness is below 95%.
- `inconclusive`: run is cancelled, required metrics are missing, no logical request completed successfully, or the result does not fit a stronger verdict.

The report never uses an LLM for the deterministic verdict. Optional AI incident analysis is currently marked unavailable; when added, it must remain secondary to measured metrics and deterministic recommendations.

Comparison direction is deterministic:

- Higher is better for resilience score, availability, correctness, schema validity, fallback recovery, and successful requests.
- Lower is better for p50/p95 latency, time to recovery, failed requests, real errors, simulated errors, total cost, and cost per successful request.
- Percentage differences are omitted when the baseline is zero or unknown.

### Workloads

Workloads live behind `turbulence_api.workloads`. Each workload exposes deterministic fixture selection by random seed, prompt construction, Concentrate request construction, and local validation/scoring. `WorkloadRegistry` is the lookup boundary for runnable workloads.

The first workload is `support_ticket_triage`. It contains 15 deterministic fixtures. Each fixture has:

- `id`
- `ticket_text`
- `expected_category`
- `expected_priority`
- `required_summary_keywords`

Allowed categories:

- `billing`
- `technical`
- `account`
- `security`
- `other`

Allowed priorities:

- `low`
- `medium`
- `high`
- `critical`

The expected model output is strict JSON:

```json
{
  "category": "billing | technical | account | security | other",
  "priority": "low | medium | high | critical",
  "summary": "short factual summary",
  "confidence": 0.0,
  "requires_human": true
}
```

The Concentrate request uses structured output with `text.format.type=json_schema`, a strict schema, a small configurable `max_output_tokens`, `temperature=0`, and metadata identifying the Turbulence app and fixture scenario.

Scoring is local and deterministic. Turbulence does not use an LLM judge for the primary correctness metric.

- `schema_valid`: output parses as JSON and validates against the strict Pydantic schema, including no extra fields.
- `category_correct`: parsed category exactly matches the fixture.
- `priority_correct`: parsed priority exactly matches the fixture.
- `summary_keyword_coverage`: fraction of required factual keywords found in the summary.
- `overall_correct`: true only when schema is valid, category and priority are correct, and summary keyword coverage is complete.

### Concentrate Adapter

Concentrate-specific request and response handling stays behind `turbulence_api.integrations.concentrate`. Routes and future simulation code use normalized Turbulence contracts rather than upstream payload shapes.

The adapter owns:

- Live and mock client implementations with the same interface.
- Concentrate request construction for responses, models, health checks, routing, metadata, and structured output.
- Upstream status-code mapping for 400, 401, 402, 424, 429, and 5xx responses.
- Normalized response parsing for response id, returned model, provider only when present, assistant text, usage, cost, status, and errors.
- Sensitive-data handling. API keys, authorization headers, and complete prompts must not be logged or returned by endpoints.

`CNAI_MODE=mock` returns deterministic mock responses and marks them as mock. `CNAI_MODE=live` uses one reusable `httpx.AsyncClient` managed by FastAPI lifespan.

Concentrate endpoints currently exposed by the API:

- `GET /api/integrations/concentrate/status`
- `POST /api/integrations/concentrate/test`

The test endpoint sends one short structured-output request only in live mode. It never exposes the configured API key or a partial key.

### Persistence

Local development uses SQLite through async SQLAlchemy. Configuration remains URL-driven so PostgreSQL can be used later without changing application code.

### Event Stream

Simulation events will be streamed over Server-Sent Events. Events must identify whether they are real or simulated and must never invent provider failures, costs, token counts, or routing decisions.
