from __future__ import annotations

from typing import Any, Literal

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
    formula_explanation: str = (
        "Score = sum earned points for applicable components divided by sum possible "
        "points for applicable components, then scaled to 100. Excluded components "
        "are reweighted out."
    )


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
    mock_response_count: int | None = None
    total_cost: float | None
    cost_per_successful_request: float | None
    time_to_recovery_ms: float | None
    requests_by_actual_model_provider: dict[str, int]
    error_distribution_by_type: dict[str, int]
    route_attempt_distribution: dict[str, int]
    resilience_score: ResilienceScore


Verdict = Literal[
    "production_ready",
    "degraded_but_recovered",
    "unreliable",
    "inconclusive",
]


class ExecutiveVerdict(BaseModel):
    verdict: Verdict
    explanation: str
    target_availability_percentage: float
    target_correctness_rate: float


class IncidentTimelineItem(BaseModel):
    sequence: int
    timestamp: str
    event_type: str
    source: Literal["real", "simulated", "system", "mock"]
    label: str
    request_id: str | None = None
    route_index: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RouteAnalysisItem(BaseModel):
    route_index: int
    requested_model: str
    requested_provider: str | None = None
    actual_model: str | None = None
    actual_provider: str | None = None
    attempts: int
    successes: int
    failures: int
    fallback_usage: int
    simulator_managed_fallback: bool
    concentrate_native: bool


class FailureAnalysis(BaseModel):
    real_failures: int
    simulated_failures: int
    validation_failures: int
    rate_limits: int
    timeouts: int
    malformed_json: int
    provider_outage_injections: int
    unknown_unclassified_errors: int
    distribution: dict[str, int]


class DeterministicRecommendation(BaseModel):
    code: str
    message: str


class AiIncidentAnalysis(BaseModel):
    available: bool = False
    generated: bool = False
    label: str = "AI-generated analysis unavailable"
    executive_summary: str | None = None
    primary_risk: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    confidence: float | None = None


class PostFlightReport(BaseModel):
    run_id: str
    scenario_id: str
    run_state: str
    mode: str
    created_at: str
    updated_at: str
    executive_verdict: ExecutiveVerdict
    metrics: MetricsSnapshot
    incident_timeline: list[IncidentTimelineItem] = Field(default_factory=list)
    route_analysis: list[RouteAnalysisItem] = Field(default_factory=list)
    failure_analysis: FailureAnalysis
    recommendations: list[DeterministicRecommendation] = Field(default_factory=list)
    ai_analysis: AiIncidentAnalysis = Field(default_factory=AiIncidentAnalysis)


class MetricDifference(BaseModel):
    before: Any
    after: Any
    absolute_difference: float | None
    percentage_difference: float | None
    direction: Literal["higher_is_better", "lower_is_better", "neutral"] = "neutral"
    change_kind: Literal["improvement", "regression", "no_change", "no_data"] = "no_data"


class RunComparison(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    differences: dict[str, MetricDifference]
