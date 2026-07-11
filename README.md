# Turbulence

Turbulence is an AI Flight Simulator that crash-tests LLM applications before production. It will send structured workloads through Concentrate AI, inject deterministic client-boundary faults, exercise routing and fallback strategies, stream live events to a cockpit UI, and create post-flight reliability reports.

This repository is the initial monorepo scaffold. The simulation engine is intentionally not implemented yet.

## Structure

```text
apps/
  api/   FastAPI backend
  web/   Next.js cockpit UI
docs/
  architecture.md
```

## Backend

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
uvicorn turbulence_api.main:app --reload --host 0.0.0.0 --port 8000
```

Health endpoint:

```bash
curl http://localhost:8000/api/health
```

## Frontend

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`.

## Configuration

Copy `.env.example` to `.env` for local settings. Backend CORS is controlled by `CORS_ORIGINS`, a comma-separated list of allowed origins.

## Checks

```bash
make api-lint
make api-test
make web-lint
make web-typecheck
```

## Current Boundaries

- No Redis, Celery, authentication, billing, or Kubernetes.
- No simulation engine yet.
- No fabricated provider failures, costs, tokens, or routing decisions.

