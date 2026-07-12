from __future__ import annotations

from turbulence_api.core.config import Settings
from turbulence_api.repositories.scenarios import ScenarioRepository
from turbulence_api.services.errors import ConflictError, NotFoundError, ValidationServiceError
from turbulence_api.simulation.models import ScenarioConfig
from turbulence_api.simulation.store import InMemoryRunStore
from turbulence_api.workloads.registry import WorkloadRegistry


class ScenarioService:
    def __init__(
        self,
        *,
        repository: ScenarioRepository,
        run_store: InMemoryRunStore,
        workload_registry: WorkloadRegistry,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._run_store = run_store
        self._workload_registry = workload_registry
        self._settings = settings

    async def list(self) -> list[ScenarioConfig]:
        return await self._repository.list()

    async def get(self, scenario_id: str) -> ScenarioConfig:
        scenario = await self._repository.get(scenario_id)
        if scenario is None:
            raise NotFoundError("Scenario not found")
        return scenario

    async def create(self, scenario: ScenarioConfig) -> ScenarioConfig:
        if await self._repository.get(scenario.id) is not None:
            raise ConflictError("Scenario already exists")
        self._validate(scenario)
        return await self._repository.upsert(scenario)

    async def seed_presets(self, presets: list[ScenarioConfig]) -> None:
        for preset in presets:
            self._validate(preset)
            await self._repository.upsert(preset)

    async def update(self, scenario_id: str, scenario: ScenarioConfig) -> ScenarioConfig:
        if scenario.id != scenario_id:
            raise ValidationServiceError("Scenario id in path and body must match")
        if await self._repository.get(scenario_id) is None:
            raise NotFoundError("Scenario not found")
        self._validate(scenario)
        return await self._repository.upsert(scenario)

    async def delete(self, scenario_id: str) -> None:
        if await self._repository.get(scenario_id) is None:
            raise NotFoundError("Scenario not found")
        historical_runs = await self._run_store.list_runs_by_scenario(scenario_id)
        if historical_runs:
            raise ConflictError("Scenario has historical runs and cannot be deleted")
        await self._repository.delete(scenario_id)

    def validate(self, scenario: ScenarioConfig) -> None:
        self._validate(scenario)

    def _validate(self, scenario: ScenarioConfig) -> None:
        if scenario.workload_name not in self._workload_registry.list_names():
            raise ValidationServiceError("Unknown workload")
        if scenario.request_count > self._settings.max_simulation_requests:
            raise ValidationServiceError("Scenario request_count exceeds configured limit")
        if scenario.max_concurrency > self._settings.max_simulation_concurrency:
            raise ValidationServiceError("Scenario max_concurrency exceeds configured limit")
        if scenario.max_concurrency > scenario.request_count:
            raise ValidationServiceError("max_concurrency cannot exceed request_count")
        if scenario.routing_profile.type == "resilient_route":
            seen_routes: set[tuple[str, str | None]] = set()
            for route in scenario.routing_profile.routes:
                key = (route.model, route.provider)
                if key in seen_routes:
                    raise ValidationServiceError(
                        "resilient routing cannot contain duplicate routes"
                    )
                seen_routes.add(key)

        estimated_duration_ms = scenario.request_count / scenario.rate_per_second * 1000
        for rule in scenario.fault_rules:
            if rule.probability < 0 or rule.probability > 1:
                raise ValidationServiceError("fault probability must be between 0 and 1")
            if rule.start_after_ms + rule.duration_ms > estimated_duration_ms:
                raise ValidationServiceError("fault window must fit within estimated run duration")
