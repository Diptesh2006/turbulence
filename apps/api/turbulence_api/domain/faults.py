from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from turbulence_api.domain.events import DomainEvent
from turbulence_api.domain.routing import RoutingAttempt
from turbulence_api.integrations.concentrate.models import NormalizedConcentrateResponse

FaultType = Literal["provider_outage", "rate_limit_burst", "latency_spike", "malformed_json"]


class FaultRule(BaseModel):
    id: str
    type: FaultType
    target_provider: str | None = None
    target_model: str | None = None
    start_after_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    probability: float = Field(ge=0, le=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_duration(self) -> FaultRule:
        if self.enabled and self.duration_ms == 0:
            raise ValueError("enabled fault rules require duration_ms > 0")
        return self

    def is_in_window(self, at_ms: int) -> bool:
        return self.start_after_ms <= at_ms < self.start_after_ms + self.duration_ms

    def matches(self, attempt: RoutingAttempt) -> bool:
        provider_matches = (
            self.target_provider is None or self.target_provider == attempt.provider
        )
        model_matches = self.target_model is None or self.target_model == attempt.model
        return provider_matches and model_matches


class FaultProvenance(BaseModel):
    rule_id: str
    type: FaultType
    source: Literal["simulated"] = "simulated"
    target_provider: str | None = None
    target_model: str | None = None
    simulated_status_code: int | None = None
    retry_after_ms: int | None = None
    injected_delay_ms: int = 0
    corrupted_response: bool = False
    original_response_preserved: bool = False


class PreCallFaultResult(BaseModel):
    should_send_upstream: bool = True
    simulated_status_code: int | None = None
    retry_after_ms: int | None = None
    injected_delay_ms: int = 0
    provenance: list[FaultProvenance] = Field(default_factory=list)
    events: list[DomainEvent] = Field(default_factory=list)


class PostResponseFaultResult(BaseModel):
    response_for_validation: NormalizedConcentrateResponse
    original_response: NormalizedConcentrateResponse
    provenance: list[FaultProvenance] = Field(default_factory=list)
    events: list[DomainEvent] = Field(default_factory=list)


class DeterministicFaultInjector:
    def __init__(self, *, seed: int, scenario_id: str) -> None:
        self._seed = seed
        self._scenario_id = scenario_id
        self._active_rule_ids: set[str] = set()

    def evaluate_pre_call(
        self,
        *,
        rules: list[FaultRule],
        attempt: RoutingAttempt,
        at_ms: int,
    ) -> PreCallFaultResult:
        events = self._window_events(rules, at_ms)
        provenance: list[FaultProvenance] = []
        result = PreCallFaultResult(events=events)

        for rule in rules:
            if not self._applies(rule, attempt, at_ms):
                continue
            if not self._rolls_true(rule, attempt, at_ms):
                continue

            if rule.type == "provider_outage":
                provenance.append(
                    _provenance(rule, simulated_status_code=424)
                )
                result.should_send_upstream = False
                result.simulated_status_code = 424
                break
            if rule.type == "rate_limit_burst":
                retry_after_ms = int(rule.parameters.get("retry_after_ms", 1000))
                provenance.append(
                    _provenance(
                        rule,
                        simulated_status_code=429,
                        retry_after_ms=retry_after_ms,
                    )
                )
                result.should_send_upstream = False
                result.simulated_status_code = 429
                result.retry_after_ms = retry_after_ms
                break
            if rule.type == "latency_spike":
                delay_ms = int(rule.parameters.get("delay_ms", 0))
                provenance.append(_provenance(rule, injected_delay_ms=delay_ms))
                result.injected_delay_ms += delay_ms

        result.provenance = provenance
        return result

    def evaluate_post_response(
        self,
        *,
        rules: list[FaultRule],
        attempt: RoutingAttempt,
        at_ms: int,
        response: NormalizedConcentrateResponse,
    ) -> PostResponseFaultResult:
        events = self._window_events(rules, at_ms)
        response_for_validation = response.model_copy(deep=True)
        provenance: list[FaultProvenance] = []

        for rule in rules:
            if rule.type != "malformed_json":
                continue
            if not self._applies(rule, attempt, at_ms):
                continue
            if not self._rolls_true(rule, attempt, at_ms):
                continue

            response_for_validation.assistant_text = _corrupt_json_copy(
                response_for_validation.assistant_text
            )
            provenance.append(
                _provenance(
                    rule,
                    corrupted_response=True,
                    original_response_preserved=True,
                )
            )

        return PostResponseFaultResult(
            response_for_validation=response_for_validation,
            original_response=response,
            provenance=provenance,
            events=events,
        )

    def _applies(self, rule: FaultRule, attempt: RoutingAttempt, at_ms: int) -> bool:
        return rule.enabled and rule.is_in_window(at_ms) and rule.matches(attempt)

    def _rolls_true(self, rule: FaultRule, attempt: RoutingAttempt, at_ms: int) -> bool:
        value = _stable_unit_interval(
            self._seed,
            self._scenario_id,
            rule.id,
            str(attempt.index),
            attempt.model,
            attempt.provider or "",
            str(at_ms),
        )
        return value < rule.probability

    def _window_events(self, rules: list[FaultRule], at_ms: int) -> list[DomainEvent]:
        currently_active = {
            rule.id for rule in rules if rule.enabled and rule.is_in_window(at_ms)
        }
        events: list[DomainEvent] = []
        for rule_id in sorted(currently_active - self._active_rule_ids):
            events.append(
                DomainEvent(
                    id=_event_id("fault.activated", rule_id, at_ms),
                    type="fault.activated",
                    rule_id=rule_id,
                    at_ms=at_ms,
                    message=f"Simulated fault rule {rule_id} activated.",
                )
            )
        for rule_id in sorted(self._active_rule_ids - currently_active):
            events.append(
                DomainEvent(
                    id=_event_id("fault.cleared", rule_id, at_ms),
                    type="fault.cleared",
                    rule_id=rule_id,
                    at_ms=at_ms,
                    message=f"Simulated fault rule {rule_id} cleared.",
                )
            )
        self._active_rule_ids = currently_active
        return events


def _provenance(
    rule: FaultRule,
    *,
    simulated_status_code: int | None = None,
    retry_after_ms: int | None = None,
    injected_delay_ms: int = 0,
    corrupted_response: bool = False,
    original_response_preserved: bool = False,
) -> FaultProvenance:
    return FaultProvenance(
        rule_id=rule.id,
        type=rule.type,
        target_provider=rule.target_provider,
        target_model=rule.target_model,
        simulated_status_code=simulated_status_code,
        retry_after_ms=retry_after_ms,
        injected_delay_ms=injected_delay_ms,
        corrupted_response=corrupted_response,
        original_response_preserved=original_response_preserved,
    )


def _corrupt_json_copy(value: str | None) -> str:
    if not value:
        return "{"
    try:
        json.loads(value)
    except json.JSONDecodeError:
        return value + "{"
    return value.rstrip()[:-1] if value.rstrip().endswith("}") else value + "{"


def _stable_unit_interval(*parts: str | int) -> float:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"\0")
    integer = int.from_bytes(digest.digest()[:8], "big")
    return integer / 2**64


def _event_id(event_type: str, rule_id: str, at_ms: int) -> str:
    digest = hashlib.sha256(f"{event_type}:{rule_id}:{at_ms}".encode()).hexdigest()
    return f"evt-{digest[:16]}"

