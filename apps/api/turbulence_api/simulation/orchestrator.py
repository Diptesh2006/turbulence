from __future__ import annotations

import asyncio
from time import monotonic
from uuid import uuid4

from turbulence_api.domain.faults import DeterministicFaultInjector, FaultProvenance
from turbulence_api.domain.routing import RoutingAttempt
from turbulence_api.integrations.concentrate.client import ConcentrateClientProtocol
from turbulence_api.simulation.event_bus import EventBus
from turbulence_api.simulation.events import EventSource, SimulationEvent
from turbulence_api.simulation.models import (
    AttemptRecord,
    RequestRecord,
    ScenarioConfig,
    SimulationRun,
)
from turbulence_api.simulation.store import InMemoryRunStore
from turbulence_api.workloads.registry import WorkloadRegistry, build_default_registry


class SimulationOrchestrator:
    def __init__(
        self,
        *,
        store: InMemoryRunStore,
        event_bus: EventBus,
        concentrate_client: ConcentrateClientProtocol,
        workload_registry: WorkloadRegistry | None = None,
    ) -> None:
        self._store = store
        self._event_bus = event_bus
        self._concentrate_client = concentrate_client
        self._workload_registry = workload_registry or build_default_registry()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}

    async def create_run(
        self,
        scenario: ScenarioConfig,
        *,
        run_id: str | None = None,
    ) -> SimulationRun:
        run = SimulationRun(id=run_id or f"run-{uuid4().hex}", scenario=scenario)
        await self._store.create_run(run)
        await self._emit(run.id, "run.created", "system", {"scenario_id": scenario.id})
        return run

    async def start_run(self, run_id: str) -> None:
        run = await self._require_run(run_id)
        run.transition_to("running")
        self._cancel_events[run_id] = asyncio.Event()
        await self._emit(run_id, "run.started", "system", {"scenario_id": run.scenario.id})
        task = asyncio.create_task(self._execute_run(run), name=f"simulation-{run_id}")
        self._tasks[run_id] = task

    async def run_to_completion(
        self,
        scenario: ScenarioConfig,
        *,
        run_id: str | None = None,
    ) -> SimulationRun:
        run = await self.create_run(scenario, run_id=run_id)
        await self.start_run(run.id)
        task = self._tasks[run.id]
        await task
        return await self._require_run(run.id)

    async def cancel_run(self, run_id: str) -> None:
        run = await self._require_run(run_id)
        if run.state == "running":
            run.transition_to("cancelling")
            self._cancel_events[run_id].set()
        elif run.state == "created":
            run.transition_to("running")
            run.transition_to("cancelling")
            self._cancel_events.setdefault(run_id, asyncio.Event()).set()

    async def get_run(self, run_id: str) -> SimulationRun | None:
        return await self._store.get_run(run_id)

    async def replay_events_after(
        self, run_id: str, last_event_id: int | None
    ) -> list[SimulationEvent]:
        return await self._store.replay_events_after(run_id, last_event_id)

    def subscribe(self, run_id: str):
        return self._event_bus.subscribe(run_id)

    async def _execute_run(self, run: SimulationRun) -> None:
        try:
            scenario = run.scenario
            workload = self._workload_registry.get(scenario.workload_name)
            fixtures = [
                workload.select_fixture(scenario.seed + index)
                for index in range(scenario.request_count)
            ]
            run.metrics.total_requests = len(fixtures)
            semaphore = asyncio.Semaphore(scenario.max_concurrency)
            request_tasks: list[asyncio.Task[None]] = []
            start_time = monotonic()

            for index, fixture in enumerate(fixtures):
                if self._is_cancelling(run.id):
                    break
                request = RequestRecord(
                    id=f"req-{run.id}-{index + 1}",
                    fixture_id=fixture.id,
                )
                await self._store.save_request(run.id, request)
                await self._emit(
                    run.id,
                    "request.queued",
                    "system",
                    {"request_id": request.id, "fixture_id": fixture.id},
                )
                request_tasks.append(
                    asyncio.create_task(
                        self._run_request(
                            run=run,
                            request=request,
                            fixture=fixture,
                            fixture_index=index,
                            semaphore=semaphore,
                            start_time=start_time,
                        )
                    )
                )
                await asyncio.sleep(1 / scenario.rate_per_second)

            await asyncio.gather(*request_tasks)

            if self._is_cancelling(run.id):
                await self._cancel_run(run)
            else:
                run.transition_to("completed")
                await self._emit(
                    run.id,
                    "run.completed",
                    "system",
                    {"metrics": run.metrics.model_dump()},
                )
        except Exception as exc:
            run.error = str(exc)
            if run.state == "running":
                run.transition_to("failed")
            await self._store.mark_in_progress_abandoned(run.id)
            await self._emit(run.id, "run.failed", "system", {"error": str(exc)})
        finally:
            self._tasks.pop(run.id, None)
            self._cancel_events.pop(run.id, None)

    async def _run_request(
        self,
        *,
        run: SimulationRun,
        request: RequestRecord,
        fixture,
        fixture_index: int,
        semaphore: asyncio.Semaphore,
        start_time: float,
    ) -> None:
        async with semaphore:
            if self._is_cancelling(run.id):
                request.state = "abandoned"
                run.metrics.abandoned_requests += 1
                await self._store.save_request(run.id, request)
                return

            request.state = "running"
            scenario = run.scenario
            workload = self._workload_registry.get(scenario.workload_name)
            injector = DeterministicFaultInjector(
                seed=scenario.seed,
                scenario_id=f"{scenario.id}:{request.id}",
            )
            route_attempt = scenario.routing_profile.initial_attempt()

            while route_attempt is not None:
                if self._is_cancelling(run.id):
                    await self._abandon_request(run, request)
                    return

                attempt_record = _attempt_record(request.id, route_attempt)
                request.attempts.append(attempt_record)
                await self._store.save_attempt(run.id, request.id, attempt_record)
                await self._emit_attempt_started(run.id, request.id, attempt_record, route_attempt)

                at_ms = int((monotonic() - start_time) * 1000)
                pre = injector.evaluate_pre_call(
                    rules=scenario.fault_rules,
                    attempt=route_attempt,
                    at_ms=at_ms,
                )
                await self._emit_fault_events(run.id, pre.events)
                if pre.provenance:
                    attempt_record.fault_provenance.extend(pre.provenance)
                    await self._emit_fault_injected(
                        run.id,
                        request.id,
                        attempt_record,
                        pre.provenance,
                    )

                if pre.injected_delay_ms:
                    attempt_record.injected_latency_ms += pre.injected_delay_ms
                    await self._store.save_attempt(run.id, request.id, attempt_record)
                    await asyncio.sleep(pre.injected_delay_ms / 1000)

                if not pre.should_send_upstream:
                    attempt_record.state = "blocked"
                    attempt_record.simulated_status_code = pre.simulated_status_code
                    await self._store.save_attempt(run.id, request.id, attempt_record)
                    await self._emit(
                        run.id,
                        "attempt.completed",
                        "system",
                        {
                            "request_id": request.id,
                            "attempt_id": attempt_record.id,
                            "state": attempt_record.state,
                            "simulated_status_code": pre.simulated_status_code,
                        },
                    )
                    next_attempt = scenario.routing_profile.next_attempt_after_failure(
                        route_attempt
                    )
                    if next_attempt is not None:
                        await self._emit_fallback_started(run.id, request.id, next_attempt)
                    route_attempt = next_attempt
                    continue

                try:
                    gateway_request = workload.build_request(
                        fixture,
                        model=route_attempt.model,
                        max_output_tokens=scenario.max_output_tokens,
                    )
                    gateway_request.routing = _routing_payload(run.scenario, route_attempt)
                    upstream_started = monotonic()
                    response = await self._concentrate_client.create_response(gateway_request)
                    attempt_record.upstream_latency_ms = (monotonic() - upstream_started) * 1000
                except Exception as exc:
                    attempt_record.state = "failed"
                    attempt_record.errors.append(str(exc))
                    await self._store.save_attempt(run.id, request.id, attempt_record)
                    await self._emit(
                        run.id,
                        "attempt.completed",
                        "system",
                        {
                            "request_id": request.id,
                            "attempt_id": attempt_record.id,
                            "state": attempt_record.state,
                            "errors": attempt_record.errors,
                        },
                    )
                    next_attempt = scenario.routing_profile.next_attempt_after_failure(
                        route_attempt
                    )
                    if next_attempt is not None:
                        await self._emit_fallback_started(run.id, request.id, next_attempt)
                    route_attempt = next_attempt
                    continue

                attempt_record.upstream_response_id = response.id
                attempt_record.actual_model = response.model
                attempt_record.actual_provider = response.provider
                if response.usage is not None:
                    attempt_record.input_tokens = response.usage.input_tokens
                    attempt_record.output_tokens = response.usage.output_tokens
                    attempt_record.total_tokens = response.usage.total_tokens
                if response.cost is not None:
                    attempt_record.cost_total = response.cost.total
                await self._emit(
                    run.id,
                    "gateway.response_received",
                    "real" if not response.is_mock else "simulated",
                    {
                        "request_id": request.id,
                        "attempt_id": attempt_record.id,
                        "response_id": response.id,
                        "model": response.model,
                        "provider": response.provider,
                        "is_mock": response.is_mock,
                        "usage": response.usage.model_dump()
                        if response.usage is not None
                        else None,
                        "cost": response.cost.model_dump() if response.cost is not None else None,
                        "upstream_latency_ms": attempt_record.upstream_latency_ms,
                    },
                )

                post = injector.evaluate_post_response(
                    rules=scenario.fault_rules,
                    attempt=route_attempt,
                    at_ms=int((monotonic() - start_time) * 1000),
                    response=response,
                )
                await self._emit_fault_events(run.id, post.events)
                if post.provenance:
                    attempt_record.fault_provenance.extend(post.provenance)
                    await self._emit_fault_injected(
                        run.id,
                        request.id,
                        attempt_record,
                        post.provenance,
                    )

                validation = workload.validate_response(fixture, post.response_for_validation)
                request.validation_result = validation.model_dump()
                passed = validation.score.overall_correct
                attempt_record.validation_passed = passed
                attempt_record.state = "completed" if passed else "failed"
                await self._store.save_attempt(run.id, request.id, attempt_record)

                await self._emit(
                    run.id,
                    "validation.passed" if passed else "validation.failed",
                    "system",
                    {
                        "request_id": request.id,
                        "attempt_id": attempt_record.id,
                        "score": validation.score.model_dump(),
                        "errors": validation.errors,
                    },
                )
                await self._emit(
                    run.id,
                    "attempt.completed",
                    "system",
                    {
                        "request_id": request.id,
                        "attempt_id": attempt_record.id,
                        "state": attempt_record.state,
                    },
                )

                if passed:
                    request.state = "completed"
                    run.metrics.completed_requests += 1
                    run.metrics.passed_validations += 1
                    await self._flush_fault_clears(run.id, scenario, injector, route_attempt)
                    await self._complete_request(run, request)
                    return

                next_attempt = scenario.routing_profile.next_attempt_after_failure(route_attempt)
                if next_attempt is not None:
                    await self._emit_fallback_started(run.id, request.id, next_attempt)
                route_attempt = next_attempt

            request.state = "failed"
            run.metrics.failed_requests += 1
            run.metrics.failed_validations += 1
            await self._flush_fault_clears(run.id, scenario, injector, route_attempt)
            await self._complete_request(run, request)

    async def _complete_request(self, run: SimulationRun, request: RequestRecord) -> None:
        await self._store.save_request(run.id, request)
        await self._emit(
            run.id,
            "request.completed",
            "system",
            {"request_id": request.id, "state": request.state},
        )
        await self._emit(
            run.id,
            "metrics.updated",
            "system",
            {"metrics": run.metrics.model_dump()},
        )

    async def _flush_fault_clears(
        self,
        run_id: str,
        scenario: ScenarioConfig,
        injector: DeterministicFaultInjector,
        route_attempt: RoutingAttempt | None,
    ) -> None:
        if route_attempt is None or not scenario.fault_rules:
            return
        clear_at_ms = max(rule.start_after_ms + rule.duration_ms for rule in scenario.fault_rules)
        result = injector.evaluate_pre_call(
            rules=scenario.fault_rules,
            attempt=route_attempt,
            at_ms=clear_at_ms,
        )
        await self._emit_fault_events(run_id, result.events)

    async def _abandon_request(self, run: SimulationRun, request: RequestRecord) -> None:
        request.state = "abandoned"
        run.metrics.abandoned_requests += 1
        for attempt in request.attempts:
            if attempt.state == "started":
                attempt.state = "abandoned"
        await self._store.save_request(run.id, request)

    async def _cancel_run(self, run: SimulationRun) -> None:
        await self._store.mark_in_progress_abandoned(run.id)
        run.transition_to("cancelled")
        await self._emit(run.id, "run.cancelled", "system", {"metrics": run.metrics.model_dump()})

    async def _emit_attempt_started(
        self,
        run_id: str,
        request_id: str,
        attempt_record: AttemptRecord,
        route_attempt: RoutingAttempt,
    ) -> None:
        await self._emit(
            run_id,
            "attempt.started",
            "system",
            {
                "request_id": request_id,
                "attempt_id": attempt_record.id,
                "route_index": route_attempt.index,
                "model": route_attempt.model,
                "provider": route_attempt.provider,
                "simulator_managed_fallback": route_attempt.simulator_managed_fallback,
                "label": route_attempt.label,
            },
        )

    async def _emit_fallback_started(
        self,
        run_id: str,
        request_id: str,
        next_attempt: RoutingAttempt,
    ) -> None:
        await self._emit(
            run_id,
            "fallback.started",
            "simulated",
            {
                "request_id": request_id,
                "route_index": next_attempt.index,
                "model": next_attempt.model,
                "provider": next_attempt.provider,
                "label": next_attempt.label,
            },
        )

    async def _emit_fault_events(self, run_id: str, events) -> None:
        for event in events:
            await self._emit(
                run_id,
                event.type,
                "simulated",
                {
                    "rule_id": event.rule_id,
                    "message": event.message,
                },
            )

    async def _emit_fault_injected(
        self,
        run_id: str,
        request_id: str,
        attempt_record: AttemptRecord,
        provenance: list[FaultProvenance],
    ) -> None:
        for item in provenance:
            await self._emit(
                run_id,
                "fault.injected",
                "simulated",
                {
                    "request_id": request_id,
                    "attempt_id": attempt_record.id,
                    "provenance": item.model_dump(),
                },
            )

    async def _emit(
        self,
        run_id: str,
        event_type: str,
        source: EventSource,
        payload: dict,
    ) -> SimulationEvent:
        sequence = await self._store.next_sequence(run_id)
        event = SimulationEvent.create(
            sequence=sequence,
            type=event_type,
            source=source,
            run_id=run_id,
            payload=payload,
        )
        await self._store.append_event(event)
        await self._event_bus.publish(event)
        return event

    async def _require_run(self, run_id: str) -> SimulationRun:
        run = await self._store.get_run(run_id)
        if run is None:
            raise KeyError(f"Unknown run: {run_id}")
        return run

    def _is_cancelling(self, run_id: str) -> bool:
        cancel_event = self._cancel_events.get(run_id)
        return bool(cancel_event and cancel_event.is_set())


def _attempt_record(request_id: str, route_attempt: RoutingAttempt) -> AttemptRecord:
    return AttemptRecord(
        request_id=request_id,
        index=route_attempt.index,
        model=route_attempt.model,
        provider=route_attempt.provider,
        simulator_managed_fallback=route_attempt.simulator_managed_fallback,
    )


def _routing_payload(
    scenario: ScenarioConfig,
    route_attempt: RoutingAttempt,
) -> dict[str, str] | None:
    hint = scenario.routing_profile.gateway_routing_hint()
    if hint is not None:
        return {"metric": hint.metric}
    if route_attempt.provider is not None:
        return {"provider": route_attempt.provider}
    return None
