import { Run, RequestRecord, AttemptRecord } from "@/lib/api";
import { SimulationEvent } from "./cockpit-reducer";

export interface ResilienceComponentScore {
  name: string;
  max_points: number;
  earned_points: number | null;
  excluded: boolean;
  reason?: string;
}

export interface ResilienceScore {
  score: number | null;
  components: ResilienceComponentScore[];
  excluded_components: string[];
}

export type RiskSeverity = "nominal" | "watch" | "critical";

export interface RiskSignal {
  code: string;
  label: string;
  detail: string;
  severity: Exclude<RiskSeverity, "nominal">;
}

export interface RiskAssessment {
  severity: RiskSeverity;
  label: string;
  summary: string;
  signals: RiskSignal[];
}

export interface DerivedMetrics {
  total_logical_requests: number;
  total_attempts: number;
  successful_requests: number;
  failed_requests: number;
  availability_percentage: number | null;
  fallback_triggered_requests: number;
  successful_fallback_recoveries: number;
  fallback_recovery_rate: number | null;
  retry_count: number;
  real_error_count: number;
  simulated_error_count: number;
  schema_valid_response_rate: number | null;
  category_accuracy: number | null;
  priority_accuracy: number | null;
  overall_correctness_rate: number | null;
  p50_end_to_end_latency_ms: number | null;
  p95_end_to_end_latency_ms: number | null;
  p50_upstream_latency_ms: number | null;
  p95_upstream_latency_ms: number | null;
  total_injected_latency_ms: number | null;
  total_cost: number | null;
  cost_per_successful_request: number | null;
  time_to_recovery_ms: number | null;
  resilience_score: ResilienceScore;
  risk_assessment: RiskAssessment;
  requests_by_actual_model_provider: Record<string, number>;
  error_distribution_by_type: Record<string, number>;
  route_attempt_distribution: Record<string, number>;
}

type MetricsForRisk = Omit<DerivedMetrics, "risk_assessment">;

function percent(numerator: number, denominator: number): number | null {
  if (denominator === 0) return null;
  return (numerator / denominator) * 100;
}

function sumOptional(values: (number | null | undefined)[]): number | null {
  const filtered = values.filter((v): v is number => typeof v === "number" && !isNaN(v));
  if (filtered.length === 0) return null;
  return filtered.reduce((a, b) => a + b, 0);
}

function percentile(values: number[], pct: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const rank = Math.ceil((pct / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(rank, sorted.length - 1))];
}

export function computeMetrics(run: Run, events: SimulationEvent[]): DerivedMetrics {
  const requests = run.requests || [];
  const total_requests = run.metrics?.total_requests || requests.length || run.scenario.request_count;
  const attempts: AttemptRecord[] = requests.flatMap((r) => r.attempts || []);

  const total_attempts = attempts.length;
  const successful_requests = requests.filter((r) => r.state === "completed").length;
  const failed_requests = requests.filter((r) => r.state === "failed").length;

  const fallback_triggered = requests.filter((r) =>
    (r.attempts || []).some((a) => a.simulator_managed_fallback)
  );
  const fallback_successes = fallback_triggered.filter((r) => r.state === "completed");

  const validations = requests
    .map((r) => r.validation_result?.score)
    .filter(
      (score): score is {
        schema_valid: boolean;
        category_correct: boolean;
        priority_correct: boolean;
        summary_keyword_coverage: number;
        overall_correct: boolean;
      } => Boolean(score)
    );
  const schema_valid = validations.filter((s) => s.schema_valid === true);

  // E2E Latencies from events
  const queuedAt: Record<string, string> = {};
  const e2eLatencies: number[] = [];
  const sortedEvents = [...events].sort((a, b) => a.sequence - b.sequence);
  for (const event of sortedEvents) {
    const reqId = event.payload?.request_id;
    if (typeof reqId !== "string") continue;
    if (event.type === "request.queued") {
      queuedAt[reqId] = event.timestamp;
    } else if (event.type === "request.completed" && queuedAt[reqId]) {
      const start = new Date(queuedAt[reqId]).getTime();
      const end = new Date(event.timestamp).getTime();
      e2eLatencies.push(end - start);
    }
  }

  const upstreamLatencies = attempts
    .map((a) => a.upstream_latency_ms)
    .filter((l): l is number => typeof l === "number" && !isNaN(l));

  const injectedLatencies = attempts
    .map((a) => a.injected_latency_ms)
    .filter((l): l is number => typeof l === "number" && l > 0);

  const total_cost = sumOptional(attempts.map((a) => a.cost_total));

  // Time to recovery
  let time_to_recovery_ms: number | null = null;
  const firstFault = sortedEvents.find((e) => e.type === "fault.activated");
  if (firstFault) {
    const firstFaultTime = new Date(firstFault.timestamp).getTime();
    const fallbackRequestIds = new Set(
      sortedEvents
        .filter((e) => e.type === "fallback.started" && typeof e.payload?.request_id === "string")
        .map((e) => e.payload.request_id as string)
    );
    const successfulRequestIds = new Set(
      requests.filter((r) => r.state === "completed").map((r) => r.id)
    );

    const recoveryEvent = sortedEvents.find(
      (e) =>
        e.sequence > firstFault.sequence &&
        e.type === "request.completed" &&
        typeof e.payload?.request_id === "string" &&
        fallbackRequestIds.has(e.payload.request_id) &&
        successfulRequestIds.has(e.payload.request_id)
    );

    if (recoveryEvent) {
      time_to_recovery_ms = new Date(recoveryEvent.timestamp).getTime() - firstFaultTime;
    }
  }

  // Model-Provider counts
  const requests_by_actual_model_provider: Record<string, number> = {};
  for (const r of requests) {
    const completed = (r.attempts || []).find((a) => a.validation_passed === true);
    if (!completed) continue;
    const model = completed.actual_model || completed.model;
    const provider = completed.actual_provider || completed.provider || "unknown";
    const key = `${model}/${provider}`;
    requests_by_actual_model_provider[key] = (requests_by_actual_model_provider[key] || 0) + 1;
  }

  // Error distribution
  const error_distribution_by_type: Record<string, number> = {};
  for (const a of attempts) {
    for (const p of a.fault_provenance || []) {
      if (p.simulated_status_code !== null || p.corrupted_response) {
        const key = `simulated.${p.type}`;
        error_distribution_by_type[key] = (error_distribution_by_type[key] || 0) + 1;
      }
    }
    if (a.simulated_status_code !== null && a.simulated_status_code !== undefined) {
      const key = `simulated.http_${a.simulated_status_code}`;
      error_distribution_by_type[key] = (error_distribution_by_type[key] || 0) + 1;
    }
    if (a.errors && a.errors.length > 0) {
      error_distribution_by_type["real.gateway_error"] =
        (error_distribution_by_type["real.gateway_error"] || 0) + a.errors.length;
    }
    if (a.validation_passed === false) {
      error_distribution_by_type["validation.failed"] =
        (error_distribution_by_type["validation.failed"] || 0) + 1;
    }
  }

  // Route attempt distribution
  const route_attempt_distribution: Record<string, number> = {};
  for (const a of attempts) {
    const provider = a.provider || "unspecified";
    const key = `${a.index}:${a.model}/${provider}`;
    route_attempt_distribution[key] = (route_attempt_distribution[key] || 0) + 1;
  }

  const availability_percentage = percent(successful_requests, total_requests);
  const fallback_recovery_rate = percent(fallback_successes.length, fallback_triggered.length);
  const schema_valid_response_rate = percent(schema_valid.length, validations.length);
  const category_accuracy = percent(
    schema_valid.filter((s) => s.category_correct === true).length,
    schema_valid.length
  );
  const priority_accuracy = percent(
    schema_valid.filter((s) => s.priority_correct === true).length,
    schema_valid.length
  );
  const overall_correctness_rate = percent(
    validations.filter((s) => s.overall_correct === true).length,
    validations.length
  );

  const snapshot: Omit<DerivedMetrics, "resilience_score" | "risk_assessment"> = {
    total_logical_requests: total_requests,
    total_attempts,
    successful_requests,
    failed_requests,
    availability_percentage,
    fallback_triggered_requests: fallback_triggered.length,
    successful_fallback_recoveries: fallback_successes.length,
    fallback_recovery_rate,
    retry_count: requests.reduce((sum, r) => sum + Math.max(0, (r.attempts || []).length - 1), 0),
    real_error_count: attempts.filter((a) => a.errors && a.errors.length > 0).length,
    simulated_error_count: attempts.reduce(
      (sum, a) =>
        sum +
        (a.fault_provenance || []).filter(
          (p) => p.simulated_status_code !== null || p.corrupted_response
        ).length,
      0
    ),
    schema_valid_response_rate,
    category_accuracy,
    priority_accuracy,
    overall_correctness_rate,
    p50_end_to_end_latency_ms: percentile(e2eLatencies, 50),
    p95_end_to_end_latency_ms: percentile(e2eLatencies, 95),
    p50_upstream_latency_ms: percentile(upstreamLatencies, 50),
    p95_upstream_latency_ms: percentile(upstreamLatencies, 95),
    total_injected_latency_ms: injectedLatencies.length > 0 ? sumOptional(injectedLatencies) : null,
    total_cost,
    cost_per_successful_request:
      total_cost !== null && successful_requests > 0 ? total_cost / successful_requests : null,
    time_to_recovery_ms,
    requests_by_actual_model_provider,
    error_distribution_by_type,
    route_attempt_distribution,
  };

  const resilience_score = computeResilienceScore(run, snapshot);
  const risk_assessment = assessRunRisk(run, {
    ...snapshot,
    resilience_score,
  });

  return {
    ...snapshot,
    resilience_score,
    risk_assessment,
  };
}

export function assessRunRisk(run: Run, metrics: MetricsForRisk): RiskAssessment {
  const signals: RiskSignal[] = [];
  const scenario = run.scenario;

  if (metrics.availability_percentage !== null && metrics.availability_percentage < 99) {
    signals.push({
      code: "availability_below_target",
      label: "Availability below target",
      detail: `${metrics.availability_percentage.toFixed(1)}% availability observed against a 99.0% target.`,
      severity: metrics.availability_percentage < 90 ? "critical" : "watch",
    });
  }

  if (metrics.overall_correctness_rate !== null && metrics.overall_correctness_rate < 95) {
    signals.push({
      code: "correctness_below_target",
      label: "Correctness below target",
      detail: `${metrics.overall_correctness_rate.toFixed(1)}% correctness observed against a 95.0% target.`,
      severity: metrics.overall_correctness_rate < 85 ? "critical" : "watch",
    });
  }

  if (
    scenario.latency_slo_ms !== null &&
    scenario.latency_slo_ms !== undefined &&
    metrics.p95_end_to_end_latency_ms !== null &&
    metrics.p95_end_to_end_latency_ms > scenario.latency_slo_ms
  ) {
    const overByMs = metrics.p95_end_to_end_latency_ms - scenario.latency_slo_ms;
    signals.push({
      code: "latency_slo_breach",
      label: "p95 latency SLO breach",
      detail: `p95 latency is ${overByMs.toFixed(0)}ms over the configured ${scenario.latency_slo_ms}ms SLO.`,
      severity: metrics.p95_end_to_end_latency_ms > scenario.latency_slo_ms * 1.5 ? "critical" : "watch",
    });
  }

  if (
    scenario.recovery_time_slo_ms !== null &&
    scenario.recovery_time_slo_ms !== undefined &&
    metrics.time_to_recovery_ms !== null &&
    metrics.time_to_recovery_ms > scenario.recovery_time_slo_ms
  ) {
    const overByMs = metrics.time_to_recovery_ms - scenario.recovery_time_slo_ms;
    signals.push({
      code: "recovery_slo_breach",
      label: "Recovery SLO breach",
      detail: `Fallback recovery took ${overByMs.toFixed(0)}ms longer than the configured SLO.`,
      severity: metrics.time_to_recovery_ms > scenario.recovery_time_slo_ms * 1.5 ? "critical" : "watch",
    });
  }

  if (metrics.fallback_triggered_requests > 0 && metrics.fallback_recovery_rate === 0) {
    signals.push({
      code: "fallback_not_recovering",
      label: "Fallback did not recover",
      detail: `${metrics.fallback_triggered_requests} fallback-triggered request(s) produced no successful recovery.`,
      severity: "critical",
    });
  } else if (
    metrics.fallback_recovery_rate !== null &&
    metrics.fallback_recovery_rate < 100 &&
    metrics.fallback_triggered_requests > 0
  ) {
    signals.push({
      code: "partial_fallback_recovery",
      label: "Partial fallback recovery",
      detail: `${metrics.fallback_recovery_rate.toFixed(1)}% of fallback-triggered requests recovered successfully.`,
      severity: "watch",
    });
  }

  if (metrics.real_error_count > 0) {
    signals.push({
      code: "real_gateway_errors",
      label: "Real gateway errors",
      detail: `${metrics.real_error_count} attempt(s) reported real gateway errors.`,
      severity: "critical",
    });
  }

  if (metrics.resilience_score.score !== null && metrics.resilience_score.score < 70) {
    signals.push({
      code: "low_resilience_score",
      label: "Low resilience score",
      detail: `Composite resilience score is ${metrics.resilience_score.score.toFixed(0)}/100.`,
      severity: metrics.resilience_score.score < 50 ? "critical" : "watch",
    });
  }

  const severity = signals.some((signal) => signal.severity === "critical")
    ? "critical"
    : signals.length > 0
      ? "watch"
      : "nominal";

  if (severity === "nominal") {
    return {
      severity,
      label: "Nominal",
      summary: "No operational risk signals are currently above the configured thresholds.",
      signals,
    };
  }

  return {
    severity,
    label: severity === "critical" ? "Critical" : "Watch",
    summary:
      severity === "critical"
        ? "One or more signals indicate production-blocking reliability risk."
        : "The run is usable for analysis but has reliability signals to review.",
    signals,
  };
}

function computeResilienceScore(
  run: Run,
  snapshot: Omit<DerivedMetrics, "resilience_score" | "risk_assessment">,
): ResilienceScore {
  const components: ResilienceComponentScore[] = [];

  // 1. Availability
  if (snapshot.availability_percentage === null) {
    components.push({
      name: "availability",
      max_points: 30,
      earned_points: null,
      excluded: true,
      reason: "no logical requests",
    });
  } else {
    components.push({
      name: "availability",
      max_points: 30,
      earned_points: (snapshot.availability_percentage / 100) * 30,
      excluded: false,
    });
  }

  // 2. Recovery Time
  if (run.scenario.recovery_time_slo_ms === null || run.scenario.recovery_time_slo_ms === undefined) {
    components.push({
      name: "recovery_time",
      max_points: 20,
      earned_points: null,
      excluded: true,
      reason: "recovery-time SLO is not configured",
    });
  } else if (snapshot.time_to_recovery_ms === null) {
    components.push({
      name: "recovery_time",
      max_points: 20,
      earned_points: null,
      excluded: true,
      reason: "no measured fallback recovery after a fault",
    });
  } else {
    const ratio = run.scenario.recovery_time_slo_ms / snapshot.time_to_recovery_ms;
    const ratioBounded = Math.max(0.0, Math.min(1.0, ratio));
    components.push({
      name: "recovery_time",
      max_points: 20,
      earned_points: ratioBounded * 20,
      excluded: false,
    });
  }

  // 3. Fallback Recovery
  if (snapshot.fallback_recovery_rate === null) {
    components.push({
      name: "fallback_recovery",
      max_points: 20,
      earned_points: null,
      excluded: true,
      reason: "no fallback-triggered requests",
    });
  } else {
    components.push({
      name: "fallback_recovery",
      max_points: 20,
      earned_points: (snapshot.fallback_recovery_rate / 100) * 20,
      excluded: false,
    });
  }

  // 4. Correctness
  if (snapshot.overall_correctness_rate === null) {
    components.push({
      name: "correctness",
      max_points: 15,
      earned_points: null,
      excluded: true,
      reason: "no validated responses",
    });
  } else {
    components.push({
      name: "correctness",
      max_points: 15,
      earned_points: (snapshot.overall_correctness_rate / 100) * 15,
      excluded: false,
    });
  }

  // 5. P95 Latency
  if (run.scenario.latency_slo_ms === null || run.scenario.latency_slo_ms === undefined) {
    components.push({
      name: "p95_latency",
      max_points: 15,
      earned_points: null,
      excluded: true,
      reason: "latency SLO is not configured",
    });
  } else if (snapshot.p95_end_to_end_latency_ms === null) {
    components.push({
      name: "p95_latency",
      max_points: 15,
      earned_points: null,
      excluded: true,
      reason: "no completed request latency",
    });
  } else {
    const ratio = run.scenario.latency_slo_ms / snapshot.p95_end_to_end_latency_ms;
    const ratioBounded = Math.max(0.0, Math.min(1.0, ratio));
    components.push({
      name: "p95_latency",
      max_points: 15,
      earned_points: ratioBounded * 15,
      excluded: false,
    });
  }

  const applicable = components.filter((c) => !c.excluded);
  if (applicable.length === 0) {
    return {
      score: null,
      components,
      excluded_components: components.map((c) => c.name),
    };
  }

  const earned = applicable.reduce((sum, c) => sum + (c.earned_points || 0), 0);
  const possible = applicable.reduce((sum, c) => sum + c.max_points, 0);

  return {
    score: (earned / possible) * 100,
    components,
    excluded_components: components.filter((c) => c.excluded).map((c) => c.name),
  };
}
