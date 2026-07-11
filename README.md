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

Concentrate integration:

```bash
curl http://localhost:8000/api/integrations/concentrate/status
```

Live test requests only run when `CNAI_MODE=live` and `CNAI_API_KEY` is set:

```bash
curl -X POST http://localhost:8000/api/integrations/concentrate/test `
  -H "Content-Type: application/json" `
  -d "{}"
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

Concentrate settings:

- `CNAI_API_KEY`: required for live Concentrate requests.
- `CNAI_BASE_URL`: defaults to `https://api.concentrate.ai/v1`.
- `CNAI_TIMEOUT_SECONDS`: request timeout in seconds.
- `CNAI_MODE`: `mock` or `live`; defaults to `mock`.

## Checks

```bash
make api-lint
make api-test
make web-lint
make web-typecheck
```

Manual live Concentrate check:

```bash
cd apps/api
python scripts/manual_concentrate_check.py
```

The script exits without making a request unless `CNAI_API_KEY` exists.

## Current Boundaries

- No Redis, Celery, authentication, billing, or Kubernetes.
- No simulation engine yet.
- No fabricated provider failures, costs, tokens, or routing decisions.
