# Turbulence

Turbulence is an AI Flight Simulator for crash-testing LLM applications before production. It runs deterministic workloads through Concentrate AI, injects reproducible client-boundary faults, exercises routing and fallback strategies, streams simulation events to a cockpit UI, and produces post-flight reliability reports.

The current implementation includes:

- FastAPI backend with Pydantic v2, async-ready SQLAlchemy configuration, Alembic, httpx, and pytest.
- Next.js frontend with TypeScript, Tailwind, TanStack Query, and Recharts.
- Concentrate AI adapter with mock and live modes.
- `support_ticket_triage` workload with deterministic fixtures and local scoring.
- Routing profiles: single provider, gateway auto, and resilient route.
- Deterministic fault injection: provider outage, rate-limit burst, latency spike, and malformed JSON.
- Server-Sent Events cockpit for live run telemetry.
- Scenario presets and scenario builder.
- Post-flight reports with deterministic verdicts and recommendations.
- Run comparison UI.

## Repository Layout

```text
apps/
  api/   FastAPI backend and simulation services
  web/   Next.js operations console
docs/
  architecture.md
  api-contract.md
```

## Requirements

- Python 3.13+
- Node.js 20+
- npm

No Redis, Celery, authentication, billing, or Kubernetes are required.

## Backend Setup

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
uvicorn turbulence_api.main:app --reload --host 0.0.0.0 --port 8000
```

Useful endpoints:

```bash
curl http://localhost:8000/
curl http://localhost:8000/docs
curl http://localhost:8000/api/health
curl http://localhost:8000/api/integrations/concentrate/status
```

## Frontend Setup

```bash
cd apps/web
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## Configuration

Copy `.env.example` to the backend environment file before local development:

```bash
copy .env.example apps\api\.env
```

Important backend variables:

- `CNAI_MODE`: `mock` or `live`.
- `CNAI_API_KEY`: required only for live Concentrate calls.
- `CNAI_BASE_URL`: defaults to `https://api.concentrate.ai/v1`.
- `CNAI_TIMEOUT_SECONDS`: request timeout in seconds.
- `CORS_ORIGINS`: comma-separated frontend origins.
- `WORKLOAD_MAX_OUTPUT_TOKENS`: max output budget for workload requests.
- `MAX_SIMULATION_REQUESTS`: backend safety cap for logical requests.
- `MAX_SIMULATION_CONCURRENCY`: backend safety cap for concurrency.

Frontend API base URL:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Mock vs Live Runs

Mock mode is safe for demos and consumes no provider credits. Mock responses are deterministic and are labelled as mock/simulated in the UI.

Live mode uses Concentrate AI and can consume credits. API keys are never exposed to the frontend.

To run a small live check:

1. Set `CNAI_MODE=live` and `CNAI_API_KEY` in `apps/api/.env`.
2. Restart the backend from `apps/api`.
3. Confirm:

   ```bash
   curl http://localhost:8000/api/integrations/concentrate/status
   ```

   Expected: `mode=live`, `is_mock=false`.

4. Open `/simulations/new`.
5. Select `preset-clear-skies`.
6. Choose `Live Concentrate mode`.
7. Click `Use 1-request live smoke settings`.
8. Save the scenario, create the run, and start it from the cockpit.

Preset scenarios remain mock by default so switching the backend to live does not silently burn credits.

## Main Workflows

- `/` shows product overview, recent runs, and integration health.
- `/scenarios` lists preset and custom scenarios.
- `/simulations/new` configures and launches simulations.
- `/runs/{id}` shows the live cockpit and SSE event stream.
- `/runs/{id}/report` shows the post-flight reliability report.
- `/compare` compares two completed or terminal runs.

## Post-Flight Verdicts

Reports use deterministic threshold logic, not an LLM judge:

- `production_ready`: completed, availability at least 99%, correctness at least 95%, no fatal error, and no degradation signals.
- `degraded_but_recovered`: completed with fallback, simulated fault, validation, error, failed request, or latency degradation signals, and availability above zero.
- `unreliable`: fatal run failure, materially poor availability, or poor correctness.
- `inconclusive`: cancelled, missing required metrics, or no successful logical request.

Unknown cost or token values remain `null`/`N/A`; they are never treated as zero.

## Checks

Backend:

```bash
cd apps/api
ruff check .
pytest
```

Frontend:

```bash
cd apps/web
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

Root Makefile shortcuts:

```bash
make api-lint
make api-test
make web-lint
make web-typecheck
```

## Utility Scripts

Manual live Concentrate check:

```bash
cd apps/api
python scripts/manual_concentrate_check.py
```

The script exits without making a request unless `CNAI_API_KEY` exists.

Run one deterministic mock workload fixture:

```bash
cd apps/api
python scripts/run_workload_fixture.py --workload support_ticket_triage --seed 7 --model mock-fast
```

## Troubleshooting

If Next.js fails on Windows/OneDrive with a cache error such as `EINVAL: invalid argument, readlink apps/web/.next/types/package.json`, remove the Next cache and restart:

```powershell
cd apps/web
cmd /c rmdir /s /q .next
npm run dev
```

If it persists:

```powershell
cmd /c rmdir /s /q .next
cmd /c rmdir /s /q node_modules
del package-lock.json
npm install
npm run dev
```

If the same error continues after reinstalling dependencies, move the repository outside OneDrive. Next.js cache operations can fail inside synced folders on Windows.

## Project Rules

- Never fabricate provider failures, costs, tokens, or routing decisions.
- Clearly label events as real, simulated, mock, or system.
- Keep Concentrate-specific logic behind the Concentrate adapter.
- Make simulations reproducible through a random seed.
- Add tests with every business-logic module.
- Do not add Redis, Celery, authentication, billing, or Kubernetes at this stage.
