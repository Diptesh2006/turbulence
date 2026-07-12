from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TokenTotals(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ResilienceComponentScore(BaseModel):
    name: str
    max_points: float
    earned_points: float | None = None
    excluded: bool = False
    reason: str | None = None


class ResilienceScore(BaseModel):
    score: float | None
    components: list[ResilienceComponentScore]
    excluded_components: list[str] = Field(default_factory=list)


class MetricsSnapshot(BaseModel):
    run_id: str
    total_logical_requests: int
    total_attempts: int
    successful_requests: int
    failed_requests: int
    availability_percentage: float | None
    fallback_triggered_requests: int
    successful_fallback_recoveries: int
    fallback_recovery_rate: float | None
    retry_count: int
    real_error_count: int
    simulated_error_count: int
    schema_valid_response_rate: float | None
    category_accuracy: float | None
    priority_accuracy: float | None
    overall_correctness_rate: float | None
    p50_end_to_end_latency_ms: float | None
    p95_end_to_end_latency_ms: float | None
    p50_upstream_latency_ms: float | None
    p95_upstream_latency_ms: float | None
    total_injected_latency_ms: int | None
    tokens: TokenTotals
    total_cost: float | None
    cost_per_successful_request: float | None
    time_to_recovery_ms: float | None
    requests_by_actual_model_provider: dict[str, int]
    error_distribution_by_type: dict[str, int]
    route_attempt_distribution: dict[str, int]
    resilience_score: ResilienceScore


class PostFlightReport(BaseModel):
    run_id: str
    scenario_id: str
    run_state: str
    metrics: MetricsSnapshot


class MetricDifference(BaseModel):
    before: Any
    after: Any
    absolute_difference: float | None
    percentage_difference: float | None


class RunComparison(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    differences: dict[str, MetricDifference]

