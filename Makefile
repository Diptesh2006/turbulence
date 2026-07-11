.PHONY: api-install api-dev api-test api-lint web-install web-dev web-build web-lint web-typecheck

api-install:
	cd apps/api && python -m pip install -e ".[dev]"

api-dev:
	cd apps/api && uvicorn turbulence_api.main:app --reload --host 0.0.0.0 --port 8000

api-test:
	cd apps/api && pytest

api-lint:
	cd apps/api && ruff check .

web-install:
	cd apps/web && npm install

web-dev:
	cd apps/web && npm run dev

web-build:
	cd apps/web && npm run build

web-lint:
	cd apps/web && npm run lint

web-typecheck:
	cd apps/web && npm run typecheck

