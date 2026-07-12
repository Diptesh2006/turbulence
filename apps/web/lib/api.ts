import { z } from "zod";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
  fault_rules: z.array(z.unknown()),
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
  state: z.string(),
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

export const runSchema = z.object({
  id: z.string(),
  scenario: scenarioSchema,
  state: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  requests: z.array(z.unknown()).optional(),
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
  resilience_score: z.object({
    score: z.number().nullable(),
    excluded_components: z.array(z.string()),
    components: z.array(z.unknown()),
  }),
});

export const reportSchema = z.object({
  report: z.object({
    run_id: z.string(),
    scenario_id: z.string(),
    run_state: z.string(),
    metrics: metricSnapshotSchema,
  }),
});

export const comparisonSchema = z.object({
  comparison: z.object({
    baseline_run_id: z.string(),
    candidate_run_id: z.string(),
    differences: z.record(z.unknown()),
  }),
});

export type HealthResponse = z.infer<typeof healthSchema>;
export type IntegrationStatus = z.infer<typeof integrationStatusSchema>;
export type WorkloadSummary = z.infer<typeof workloadSchema>;
export type Scenario = z.infer<typeof scenarioSchema>;
export type RunSummary = z.infer<typeof runSummarySchema>;
export type Run = z.infer<typeof runSchema>;
export type Report = z.infer<typeof reportSchema>["report"];
export type Comparison = z.infer<typeof comparisonSchema>["comparison"];

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

export function getRun(id: string) {
  return requestJson(`/api/runs/${id}`, runResponseSchema);
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
