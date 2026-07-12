from __future__ import annotations

from turbulence_api.reporting.metrics import MetricsAggregator
from turbulence_api.reporting.models import PostFlightReport
from turbulence_api.simulation.events import SimulationEvent
from turbulence_api.simulation.models import SimulationRun


class PostFlightReportService:
    def __init__(self, metrics_aggregator: MetricsAggregator | None = None) -> None:
        self._metrics_aggregator = metrics_aggregator or MetricsAggregator()

    def create_report(
        self,
        run: SimulationRun,
        events: list[SimulationEvent] | None = None,
    ) -> PostFlightReport:
        return PostFlightReport(
            run_id=run.id,
            scenario_id=run.scenario.id,
            run_state=run.state,
            metrics=self._metrics_aggregator.snapshot(run, events),
        )

