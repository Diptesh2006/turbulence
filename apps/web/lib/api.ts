import { z } from "zod";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const runStateSchema = z.enum(["created", "running", "completed", "failed", "cancelling", "cancelled"]);

export const faultRuleSchema = z.object({
  id: z.string(),
  type: z.enum(["provider_outage", "rate_limit_burst", "latency_spike", "malformed_json"]),
  target_provider: z.string().nullable().optional(),
  target_model: z.string().nullable().optional(),
  start_after_ms: z.number().default(0),
  duration_ms: z.number().default(0),
  probability: z.number().default(1),
  parameters: z.record(z.unknown()).default({}),
  enabled: z.boolean().default(true),
});

export const healthSchema = z.object({
  service: z.string(),
  status: z.string(),
  version: z.string(),
  environment: z.string(),
  simulation_mode: z.string(),
});

export const integrationStatusSchema = z.object({
  mode: z.string(),
  status: z.string(),
  is_mock: z.boolean(),
  configured: z.boolean(),
});

export const workloadSchema = z.object({
  name: z.string(),
  fixture_count: z.number(),
  categories: z.array(z.string()).nullable().optional(),
  priorities: z.array(z.string()).nullable().optional(),
});

export const routeTargetSchema = z.object({
  model: z.string(),
  provider: z.string().nullable().optional(),
});

export const routingProfileSchema = z.object({
  id: z.string(),
  type: z.enum(["single_provider", "gateway_auto", "resilient_route"]),
  routes: z.array(routeTargetSchema).default([]),
  metric: z.string().nullable().optional(),
});

export const scenarioSchema = z.object({
  id: z.string(),
  mode: z.enum(["concentrate_native", "deterministic_chaos", "mock"]).default("mock"),
  workload_name: z.string(),
  request_count: z.number(),
  seed: z.number(),
  rate_per_second: z.number(),
  max_concurrency: z.number(),
  model: z.string(),
  max_output_tokens: z.number(),
  recovery_time_slo_ms: z.number().nullable().optional(),
  latency_slo_ms: z.number().nullable().optional(),
  routing_profile: routingProfileSchema,
  fault_rules: z.array(faultRuleSchema).default([]),
});

export const scenarioListSchema = z.object({
  items: z.array(scenarioSchema),
});

export const runMetricsSchema = z.object({
  total_requests: z.number().optional(),
  completed_requests: z.number().optional(),
  failed_requests: z.number().optional(),
  abandoned_requests: z.number().optional(),
  passed_validations: z.number().optional(),
  failed_validations: z.number().optional(),
});

export const runSummarySchema = z.object({
  id: z.string(),
  scenario_id: z.string(),
  state: runStateSchema,
  created_at: z.string(),
  updated_at: z.string(),
  metrics: runMetricsSchema,
});

export const runListSchema = z.object({
  items: z.array(runSummarySchema),
  page: z.number(),
  page_size: z.number(),
  total: z.number(),
});

export const faultProvenanceSchema = z.object({
  rule_id: z.string(),
  type: z.string(),
  source: z.literal("simulated").default("simulated"),
  target_provider: z.string().nullable().optional(),
  target_model: z.string().nullable().optional(),
  simulated_status_code: z.number().nullable().optional(),
  retry_after_ms: z.number().nullable().optional(),
  injected_delay_ms: z.number().default(0),
  corrupted_response: z.boolean().default(false),
  original_response_preserved: z.boolean().default(false),
});

export const attemptRecordSchema = z.object({
  id: z.string(),
  request_id: z.string(),
  index: z.number(),
  model: z.string(),
  provider: z.string().nullable().optional(),
  actual_model: z.string().nullable().optional(),
  actual_provider: z.string().nullable().optional(),
  state: z.enum(["started", "completed", "failed", "blocked", "abandoned"]),
  simulator_managed_fallback: z.boolean().default(false),
  fault_provenance: z.array(faultProvenanceSchema).default([]),
  upstream_response_id: z.string().nullable().optional(),
  simulated_status_code: z.number().nullable().optional(),
  validation_passed: z.boolean().nullable().optional(),
  upstream_latency_ms: z.number().nullable().optional(),
  injected_latency_ms: z.number().default(0),
  input_tokens: z.number().nullable().optional(),
  output_tokens: z.number().nullable().optional(),
  total_tokens: z.number().nullable().optional(),
  cost_total: z.number().nullable().optional(),
  errors: z.array(z.string()).default([]),
});

export const requestRecordSchema = z.object({
  id: z.string(),
  fixture_id: z.string(),
  state: z.enum(["queued", "running", "completed", "failed", "abandoned"]),
  attempts: z.array(attemptRecordSchema).default([]),
  validation_result: z.object({
    score: z.object({
      schema_valid: z.boolean(),
      category_correct: z.boolean(),
      priority_correct: z.boolean(),
      summary_keyword_coverage: z.number(),
      overall_correct: z.boolean(),
    }),
    errors: z.array(z.string()).optional(),
  }).nullable().optional(),
});

export const simulationEventSchema = z.object({
  sequence: z.number(),
  type: z.string(),
  source: z.enum(["real", "simulated", "system", "mock"]),
  timestamp: z.string(),
  run_id: z.string(),
  payload: z.record(z.unknown()).default({}),
});

export const runSchema = z.object({
  id: z.string(),
  scenario: scenarioSchema,
  state: runStateSchema,
  created_at: z.string(),
  updated_at: z.string(),
  requests: z.array(requestRecordSchema).optional(),
  metrics: runMetricsSchema,
  error: z.string().nullable().optional(),
});

export const runResponseSchema = z.object({
  run: runSchema,
});

const metricSnapshotSchema = z.object({
  run_id: z.string(),
  total_logical_requests: z.number(),
  total_attempts: z.number(),
  successful_requests: z.number(),
  failed_requests: z.number(),
  availability_percentage: z.number().nullable(),
  fallback_triggered_requests: z.number(),
  successful_fallback_recoveries: z.number(),
  fallback_recovery_rate: z.number().nullable(),
  retry_count: z.number(),
  real_error_count: z.number(),
  simulated_error_count: z.number(),
  schema_valid_response_rate: z.number().nullable(),
  category_accuracy: z.number().nullable(),
  priority_accuracy: z.number().nullable(),
  overall_correctness_rate: z.number().nullable(),
  p50_end_to_end_latency_ms: z.number().nullable(),
  p95_end_to_end_latency_ms: z.number().nullable(),
  p50_upstream_latency_ms: z.number().nullable(),
  p95_upstream_latency_ms: z.number().nullable(),
  total_injected_latency_ms: z.number().nullable(),
  total_cost: z.number().nullable(),
  cost_per_successful_request: z.number().nullable(),
  time_to_recovery_ms: z.number().nullable(),
  requests_by_actual_model_provider: z.record(z.number()),
  error_distribution_by_type: z.record(z.number()),
  route_attempt_distribution: z.record(z.number()),
  tokens: z.object({
    input_tokens: z.number().nullable(),
    output_tokens: z.number().nullable(),
    total_tokens: z.number().nullable(),
  }),
  mock_response_count: z.number().nullable().optional(),
  resilience_score: z.object({
    score: z.number().nullable(),
    excluded_components: z.array(z.string()),
    formula_explanation: z.string().optional(),
    components: z.array(z.object({
      name: z.string(),
      max_points: z.number(),
      earned_points: z.number().nullable().optional(),
      excluded: z.boolean().default(false),
      reason: z.string().nullable().optional(),
    })),
  }),
});

export const reportSchema = z.object({
  report: z.object({
    run_id: z.string(),
    scenario_id: z.string(),
    run_state: z.string(),
    mode: z.string().optional(),
    created_at: z.string().optional(),
    updated_at: z.string().optional(),
    executive_verdict: z.object({
      verdict: z.enum(["production_ready", "degraded_but_recovered", "unreliable", "inconclusive"]),
      explanation: z.string(),
      target_availability_percentage: z.number(),
      target_correctness_rate: z.number(),
    }).optional(),
    metrics: metricSnapshotSchema,
    incident_timeline: z.array(z.object({
      sequence: z.number(),
      timestamp: z.string(),
      event_type: z.string(),
      source: z.enum(["real", "simulated", "system", "mock"]),
      label: z.string(),
      request_id: z.string().nullable().optional(),
      route_index: z.number().nullable().optional(),
      payload: z.record(z.unknown()).default({}),
    })).default([]),
    route_analysis: z.array(z.object({
      route_index: z.number(),
      requested_model: z.string(),
      requested_provider: z.string().nullable().optional(),
      actual_model: z.string().nullable().optional(),
      actual_provider: z.string().nullable().optional(),
      attempts: z.number(),
      successes: z.number(),
      failures: z.number(),
      fallback_usage: z.number(),
      simulator_managed_fallback: z.boolean(),
      concentrate_native: z.boolean(),
    })).default([]),
    failure_analysis: z.object({
      real_failures: z.number(),
      simulated_failures: z.number(),
      validation_failures: z.number(),
      rate_limits: z.number(),
      timeouts: z.number(),
      malformed_json: z.number(),
      provider_outage_injections: z.number(),
      unknown_unclassified_errors: z.number(),
      distribution: z.record(z.number()),
    }).optional(),
    recommendations: z.array(z.object({
      code: z.string(),
      message: z.string(),
    })).default([]),
    ai_analysis: z.object({
      available: z.boolean(),
      generated: z.boolean(),
      label: z.string(),
      executive_summary: z.string().nullable().optional(),
      primary_risk: z.string().nullable().optional(),
      recommendations: z.array(z.string()).default([]),
      confidence: z.number().nullable().optional(),
    }).optional(),
  }),
});

export const comparisonSchema = z.object({
  comparison: z.object({
    baseline_run_id: z.string(),
    candidate_run_id: z.string(),
    differences: z.record(z.object({
      before: z.unknown(),
      after: z.unknown(),
      absolute_difference: z.number().nullable(),
      percentage_difference: z.number().nullable(),
      direction: z.enum(["higher_is_better", "lower_is_better", "neutral"]).default("neutral"),
      change_kind: z.enum(["improvement", "regression", "no_change", "no_data"]).default("no_data"),
    })),
  }),
});

export const agentActionSchema = z.object({
  sequence: z.number(),
  action: z.object({
    tool: z.string(),
    operation: z.string(),
    arguments: z.record(z.unknown()),
    risk: z.enum(["low", "medium", "high", "critical"]),
    category: z.string(),
    synthetic_secret_ids: z.array(z.string()),
  }),
  decision: z.enum(["ALLOW", "AUDIT", "WARN", "REQUIRE_APPROVAL", "BLOCK"]),
  matched_rule_id: z.string().nullable(),
  explanation: z.string(),
  context: z.record(z.unknown()),
  executed: z.boolean(),
  prevented: z.boolean(),
  approval_resolution: z.enum(["simulated_approved", "simulated_rejected"]).nullable(),
  simulated_result: z.record(z.unknown()),
  timestamp: z.string(),
});

export const agentScenarioSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  category: z.string(),
  task: z.string(),
  severity: z.enum(["low", "medium", "high", "critical"]),
  expected_outcome: z.string(),
  seed: z.number(),
  actions: z.array(agentActionSchema.shape.action),
});

export const agentPolicySchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  priority: z.number(),
  enabled: z.boolean(),
  categories: z.array(z.string()),
  min_risk: z.enum(["low", "medium", "high", "critical"]).nullable(),
  decision: z.enum(["ALLOW", "AUDIT", "WARN", "REQUIRE_APPROVAL", "BLOCK"]),
  severity: z.enum(["low", "medium", "high", "critical"]),
  reason: z.string(),
});

export const agentRunSchema = z.object({
  id: z.string(),
  scenario_id: z.string(),
  seed: z.number(),
  state: z.enum(["completed", "failed"]),
  verdict: z.enum(["safe", "contained", "unsafe", "inconclusive"]),
  safety_score: z.number(),
  attack_containment_rate: z.number().nullable(),
  actions: z.array(agentActionSchema),
  events: z.array(z.object({
    sequence: z.number(),
    type: z.string(),
    source: z.literal("simulated"),
    timestamp: z.string(),
    payload: z.record(z.unknown()),
  })),
  metrics: z.record(z.union([z.number(), z.null()])),
  created_at: z.string(),
});

export type HealthResponse = z.infer<typeof healthSchema>;
export type IntegrationStatus = z.infer<typeof integrationStatusSchema>;
export type WorkloadSummary = z.infer<typeof workloadSchema>;
export type Scenario = z.infer<typeof scenarioSchema>;
export type RunSummary = z.infer<typeof runSummarySchema>;
export type Run = z.infer<typeof runSchema>;
export type AttemptRecord = z.infer<typeof attemptRecordSchema>;
export type RequestRecord = z.infer<typeof requestRecordSchema>;
export type SimulationEvent = z.infer<typeof simulationEventSchema>;
export type Report = z.infer<typeof reportSchema>["report"];
export type Comparison = z.infer<typeof comparisonSchema>["comparison"];
export type AgentScenario = z.infer<typeof agentScenarioSchema>;
export type AgentPolicy = z.infer<typeof agentPolicySchema>;
export type AgentRun = z.infer<typeof agentRunSchema>;

async function requestJson<TSchema extends z.ZodTypeAny>(
  path: string,
  schema: TSchema,
  init?: RequestInit,
): Promise<z.output<TSchema>> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : `Request failed with ${response.status}`;
    throw new Error(detail);
  }
  return schema.parse(data);
}

export function getHealth() {
  return requestJson("/api/health", healthSchema);
}

export function getIntegrationStatus() {
  return requestJson("/api/integrations/concentrate/status", integrationStatusSchema);
}

export function getWorkloads() {
  return requestJson("/api/workloads", z.array(workloadSchema));
}

export function getScenarios() {
  return requestJson("/api/scenarios", scenarioListSchema);
}

export function getRuns(page = 1, pageSize = 10) {
  return requestJson(`/api/runs?page=${page}&page_size=${pageSize}`, runListSchema);
}

export function createScenario(scenario: Scenario) {
  return requestJson("/api/scenarios", z.object({ scenario: scenarioSchema }), {
    method: "POST",
    body: JSON.stringify(scenario),
  });
}

export function createRunFromScenario(scenarioId: string) {
  return requestJson("/api/runs", runResponseSchema, {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}

export function getRun(id: string) {
  return requestJson(`/api/runs/${id}`, runResponseSchema);
}

export function startRun(id: string) {
  return requestJson(`/api/runs/${id}/start`, runResponseSchema, {
    method: "POST",
  });
}

export function cancelRun(id: string) {
  return requestJson(`/api/runs/${id}/cancel`, runResponseSchema, {
    method: "POST",
  });
}

export function getRunReport(id: string) {
  return requestJson(`/api/runs/${id}/report`, reportSchema);
}

export function compareRuns(baselineRunId: string, candidateRunId: string) {
  return requestJson("/api/comparisons", comparisonSchema, {
    method: "POST",
    body: JSON.stringify({
      baseline_run_id: baselineRunId,
      candidate_run_id: candidateRunId,
    }),
  });
}

export function getAgentScenarios() {
  return requestJson("/api/agent-safety/scenarios", z.object({ items: z.array(agentScenarioSchema), source: z.literal("simulated") }));
}

export function getAgentPolicies() {
  return requestJson("/api/agent-safety/policies", z.object({ items: z.array(agentPolicySchema), source: z.literal("simulated") }));
}

export function updateAgentPolicy(policy: AgentPolicy) {
  return requestJson(`/api/agent-safety/policies/${policy.id}`, agentPolicySchema, {
    method: "PUT",
    body: JSON.stringify(policy),
  });
}

export function getAgentRuns() {
  return requestJson("/api/agent-safety/runs", z.object({ items: z.array(agentRunSchema), source: z.literal("simulated") }));
}

export function createAgentRun(scenarioId: string) {
  return requestJson("/api/agent-safety/runs", agentRunSchema, {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}

export function replayAgentRun(runId: string) {
  return requestJson(`/api/agent-safety/runs/${runId}/replay`, agentRunSchema, { method: "POST" });
}

export function getAgentRun(runId: string) {
  return requestJson(`/api/agent-safety/runs/${runId}`, agentRunSchema);
}
