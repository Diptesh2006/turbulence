from __future__ import annotations

from turbulence_api.workloads.base import Workload
from turbulence_api.workloads.support_ticket_triage import SupportTicketTriageWorkload


class WorkloadRegistry:
    def __init__(self) -> None:
        self._workloads: dict[str, Workload] = {}

    def register(self, workload: Workload) -> None:
        self._workloads[workload.name] = workload

    def get(self, name: str) -> Workload:
        try:
            return self._workloads[name]
        except KeyError as exc:
            raise KeyError(f"Unknown workload: {name}") from exc

    def list_names(self) -> list[str]:
        return sorted(self._workloads)


def build_default_registry() -> WorkloadRegistry:
    registry = WorkloadRegistry()
    registry.register(SupportTicketTriageWorkload())
    return registry

