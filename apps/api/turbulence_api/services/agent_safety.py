from __future__ import annotations

from turbulence_api.agent_safety.engine import run_scenario
from turbulence_api.agent_safety.models import (
    AgentRun,
    AgentScenario,
    PolicyRule,
    default_policy_rules,
    seeded_agent_scenarios,
)
from turbulence_api.services.errors import NotFoundError


class AgentSafetyService:
    def __init__(self) -> None:
        self.scenarios = {item.id: item for item in seeded_agent_scenarios()}
        self.rules = {item.id: item for item in default_policy_rules()}
        self.runs: dict[str, AgentRun] = {}

    def list_scenarios(self) -> list[AgentScenario]:
        return list(self.scenarios.values())

    def get_scenario(self, scenario_id: str) -> AgentScenario:
        try:
            return self.scenarios[scenario_id]
        except KeyError as exc:
            raise NotFoundError("Agent safety scenario not found") from exc

    def list_policies(self) -> list[PolicyRule]:
        return sorted(self.rules.values(), key=lambda rule: (rule.priority, rule.id))

    def create_run(self, scenario_id: str, seed: int | None = None) -> AgentRun:
        scenario = self.get_scenario(scenario_id)
        run = run_scenario(scenario, self.list_policies(), seed=seed)
        self.runs[run.id] = run
        return run

    def get_run(self, run_id: str) -> AgentRun:
        try:
            return self.runs[run_id]
        except KeyError as exc:
            raise NotFoundError("Agent safety run not found") from exc

    def replay(self, run_id: str) -> AgentRun:
        previous = self.get_run(run_id)
        return self.create_run(previous.scenario_id, previous.seed)
