# Project Rules

- Never fabricate provider failures, costs, tokens or routing decisions.
- Clearly label events as real or simulated.
- Keep Concentrate-specific logic behind one adapter.
- Make simulations reproducible through a random seed.
- Add tests with every business-logic module.
- Do not implement features belonging to later stages unless necessary.

## Engineering Boundaries

- Backend: Python, FastAPI, Pydantic v2, async SQLAlchemy, Alembic, httpx, pytest.
- Frontend: Next.js, TypeScript, Tailwind, shadcn/ui-compatible structure, TanStack Query, Recharts.
- Communication: REST for commands and Server-Sent Events for live simulation events.
- Local database: SQLite, with SQLAlchemy configuration kept PostgreSQL-compatible.
- Do not add Redis, Celery, authentication, billing, or Kubernetes.
- Do not implement the simulation engine until that stage is explicitly requested.

