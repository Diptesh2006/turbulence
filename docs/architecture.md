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
