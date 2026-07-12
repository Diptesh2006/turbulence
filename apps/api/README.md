# Turbulence API

FastAPI service for Turbulence. This initial scaffold exposes health checks and shared application wiring only; the simulation engine is intentionally not implemented yet.

## Development

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
uvicorn turbulence_api.main:app --reload --host 0.0.0.0 --port 8000
```

## Checks

```bash
pytest
ruff check .
```

## Concentrate

Environment variables:

- `CNAI_API_KEY`: required for live requests.
- `CNAI_BASE_URL`: defaults to `https://api.concentrate.ai/v1`.
- `CNAI_TIMEOUT_SECONDS`: request timeout in seconds.
- `CNAI_MODE`: `mock` or `live`; defaults to `mock`.
- `WORKLOAD_MAX_OUTPUT_TOKENS`: default max output token budget for workload runs.

Endpoints:

- `GET /api/integrations/concentrate/status`
- `POST /api/integrations/concentrate/test`

Manual live check:

```bash
python scripts/manual_concentrate_check.py
```

The manual script skips without making a request when `CNAI_API_KEY` is not set.

Run one deterministic workload fixture through the configured adapter:

```bash
python scripts/run_workload_fixture.py --workload support_ticket_triage --seed 7 --model mock-fast
```
