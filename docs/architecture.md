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

Concentrate-specific request and response handling must stay behind a single adapter so routing and reporting code depend on Turbulence contracts, not provider details.

### Persistence

Local development uses SQLite through async SQLAlchemy. Configuration remains URL-driven so PostgreSQL can be used later without changing application code.

### Event Stream

Simulation events will be streamed over Server-Sent Events. Events must identify whether they are real or simulated and must never invent provider failures, costs, token counts, or routing decisions.

