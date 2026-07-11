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

