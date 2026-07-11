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
