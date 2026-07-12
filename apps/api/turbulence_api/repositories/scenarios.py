from __future__ import annotations

import asyncio

from turbulence_api.simulation.models import ScenarioConfig


class ScenarioRepository:
    def __init__(self) -> None:
        self._scenarios: dict[str, ScenarioConfig] = {}
        self._lock = asyncio.Lock()

    async def list(self) -> list[ScenarioConfig]:
        async with self._lock:
            return sorted(self._scenarios.values(), key=lambda scenario: scenario.id)

    async def get(self, scenario_id: str) -> ScenarioConfig | None:
        async with self._lock:
            return self._scenarios.get(scenario_id)

    async def upsert(self, scenario: ScenarioConfig) -> ScenarioConfig:
        async with self._lock:
            self._scenarios[scenario.id] = scenario
        return scenario

    async def delete(self, scenario_id: str) -> bool:
        async with self._lock:
            return self._scenarios.pop(scenario_id, None) is not None

