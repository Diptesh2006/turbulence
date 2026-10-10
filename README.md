# Turbulence

**Pre-Production Flight Simulator for LLMs and Autonomous Agents**

Turbulence answers two pre-production questions: what happens when model infrastructure fails, and what happens when an autonomous agent proposes an unsafe action? The Provider Reliability Lab exercises deterministic workloads, provider routing, injected faults, fallback, and recovery through Concentrate AI. The Agent Safety Lab evaluates deterministic action proposals against policy and records simulated outcomes.

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
- Agent Safety Lab with destructive command, synthetic secret, MCP poisoning, and database misuse scenarios.
- Priority-ordered policy evaluation, simulated tool outcomes, action inspection, safety metrics, and deterministic replay.

Agent Safety runs are isolated simulations. They do not execute shell commands or access real filesystems, databases, networks, credentials, cloud services, or MCP servers. `ALLOW`, `AUDIT`, and `WARN` produce fixture-only outcomes; `BLOCK` prevents the simulated operation. Approval decisions are deterministic and labeled simulated. These features evaluate sample policies; they are not endpoint protection, a production interceptor, EDR, DLP, IAM, or a replacement for an agent security gateway.

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

## Deployment Readiness

CI runs the backend lint/tests and the frontend tests, type check, and production build on pushes to `main` and pull requests.

The current application is a pre-release test bench, not a multi-user production service:

- The API has no authentication or tenant isolation. Anyone who can reach it can call its read and write endpoints; CORS does not restrict non-browser clients.
- Run history, simulation events, scenarios, and Agent Safety policies are held in process memory. They disappear on restart and are not shared between API instances. The configured SQLAlchemy database is not yet wired into these stores.
- Live provider mode uses the server's configured provider credential. There are no per-user quotas, billing, or spend attribution.

Do not expose this API to unrestricted real users or enable shared live-provider access until persistence, authentication/authorization, tenant isolation, and usage controls are implemented and tested. An invite-only mock demo is a lower-risk interim release, but its data is temporary and the API still needs an access restriction at the hosting layer.

For a Vercel + Render deployment, configure `NEXT_PUBLIC_API_BASE_URL` in the Vercel project to the HTTPS API origin. Configure `CORS_ORIGINS` on the API to the exact HTTPS frontend origin (comma-separated if there are multiple). Keep `CNAI_MODE=mock` for a demo. If live mode is later enabled, put `CNAI_API_KEY` only in the API host's secret configuration; `NEXT_PUBLIC_*` variables are delivered to browsers and must never contain credentials.

Use separate preview/staging and production environments. Before promoting a release, verify the health endpoint, frontend-to-API requests, database backup/restore (once persistence is in use), and the provider mode and spend limits.

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
- `/agent-safety` runs simulated agent-safety scenarios.
- `/agent-safety/runs` and `/agent-safety/runs/{id}` show the action trajectory and outcomes.
- `/agent-safety/policies` reviews and changes baseline policy decisions for replay.

Agent Safety API routes are under `/api/agent-safety`: `GET /scenarios`, `GET/PUT /policies`, `POST/GET /runs`, `GET /runs/{id}`, and `POST /runs/{id}/replay`. Agent scenarios, policies, and runs currently use in-memory storage and reset when the API process restarts. Provider scenario persistence remains as implemented by the existing repository.

The safety score is policy decision accuracy: `correct expected-versus-actual decisions / evaluated actions × 100`. Attack containment is `blocked attack actions / attack actions × 100`, and is `N/A` when a scenario contains no attack action. Both metrics are deterministic and describe simulated fixtures only. Approval-required actions resolve from the scenario's deterministic approval setting; no human reviewer is implied.

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
