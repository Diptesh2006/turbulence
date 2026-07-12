from __future__ import annotations

from turbulence_api.reporting.compare import CompareRunsService
from turbulence_api.reporting.models import PostFlightReport, RunComparison
from turbulence_api.reporting.reports import PostFlightReportService
from turbulence_api.services.errors import ConflictError, NotFoundError
from turbulence_api.simulation.models import ScenarioConfig, SimulationRun
from turbulence_api.simulation.orchestrator import SimulationOrchestrator
from turbulence_api.simulation.store import InMemoryRunStore


class RunService:
    def __init__(
        self,
        *,
        orchestrator: SimulationOrchestrator,
        run_store: InMemoryRunStore,
        report_service: PostFlightReportService,
        compare_service: CompareRunsService,
    ) -> None:
        self._orchestrator = orchestrator
        self._run_store = run_store
        self._report_service = report_service
        self._compare_service = compare_service
        self._create_idempotency: dict[str, str] = {}
        self._start_idempotency: dict[tuple[str, str], str] = {}

    async def create_run(
        self,
        scenario: ScenarioConfig,
        *,
        idempotency_key: str | None,
    ) -> SimulationRun:
        if idempotency_key and idempotency_key in self._create_idempotency:
            return await self.get_run(self._create_idempotency[idempotency_key])
        run = await self._orchestrator.create_run(scenario)
        if idempotency_key:
            self._create_idempotency[idempotency_key] = run.id
        return run

    async def start_run(
        self,
        run_id: str,
        *,
        idempotency_key: str | None,
    ) -> SimulationRun:
        run = await self.get_run(run_id)
        key = (run_id, idempotency_key or "")
        if idempotency_key and key in self._start_idempotency:
            return run
        if run.state == "created":
            await self._orchestrator.start_run(run_id)
        elif run.state not in {"running", "completed", "failed", "cancelled", "cancelling"}:
            raise ConflictError("Run cannot be started")
        if idempotency_key:
            self._start_idempotency[key] = run_id
        return await self.get_run(run_id)

    async def cancel_run(self, run_id: str) -> SimulationRun:
        run = await self.get_run(run_id)
        if run.state not in {"created", "running"}:
            raise ConflictError("Run cannot be cancelled")
        await self._orchestrator.cancel_run(run_id)
        return await self.get_run(run_id)

    async def list_runs(self, *, page: int, page_size: int) -> tuple[list[SimulationRun], int]:
        return await self._run_store.list_runs(offset=(page - 1) * page_size, limit=page_size)

    async def get_run(self, run_id: str) -> SimulationRun:
        run = await self._orchestrator.get_run(run_id)
        if run is None:
            raise NotFoundError("Run not found")
        return run

    async def report(self, run_id: str) -> PostFlightReport:
        run = await self.get_run(run_id)
        events = await self._orchestrator.replay_events_after(run_id, None)
        return self._report_service.create_report(run, events)

    async def compare(self, baseline_run_id: str, candidate_run_id: str) -> RunComparison:
        baseline = await self.report(baseline_run_id)
        candidate = await self.report(candidate_run_id)
        return self._compare_service.compare(baseline.metrics, candidate.metrics)

