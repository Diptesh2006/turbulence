import type { Scenario } from "@/lib/api";

export const BUILDER_LIMITS = {
  maxRequests: 100,
  maxConcurrency: 10,
};

export type BuilderValidation = {
  errors: string[];
  warnings: string[];
  maxGatewayCalls: number;
  estimatedDurationMs: number;
};

export function validateScenarioBuilder(scenario: Scenario, liveMode: boolean): BuilderValidation {
  const errors: string[] = [];
  const warnings: string[] = [];
  const routeCount =
    scenario.routing_profile.type === "resilient_route"
      ? scenario.routing_profile.routes.length
      : 1;
  const estimatedDurationMs = (scenario.request_count / scenario.rate_per_second) * 1000;

  if (scenario.request_count > BUILDER_LIMITS.maxRequests) {
    errors.push(`Request count exceeds backend maximum of ${BUILDER_LIMITS.maxRequests}.`);
  }
  if (scenario.max_concurrency > BUILDER_LIMITS.maxConcurrency) {
    errors.push(`Concurrency exceeds backend maximum of ${BUILDER_LIMITS.maxConcurrency}.`);
  }
  if (scenario.max_concurrency > scenario.request_count) {
    errors.push("Concurrency cannot exceed logical request count.");
  }
  if (scenario.routing_profile.type === "resilient_route") {
    if (scenario.routing_profile.routes.length < 2) {
      errors.push("Resilient routing requires at least two routes.");
    }
    const seen = new Set<string>();
    for (const route of scenario.routing_profile.routes) {
      const key = `${route.provider ?? ""}/${route.model}`;
      if (seen.has(key)) {
        errors.push("Duplicate routes are not allowed.");
        break;
      }
      seen.add(key);
    }
  }
  for (const fault of scenario.fault_rules) {
    const typedFault = fault as {
      id?: string;
      probability?: number;
      start_after_ms?: number;
      duration_ms?: number;
    };
    if (
      typeof typedFault.probability === "number" &&
      (typedFault.probability < 0 || typedFault.probability > 1)
    ) {
      errors.push(`Fault ${typedFault.id ?? "unknown"} probability must be between 0 and 1.`);
    }
    const faultEnd = (typedFault.start_after_ms ?? 0) + (typedFault.duration_ms ?? 0);
    if (faultEnd > estimatedDurationMs) {
      errors.push(`Fault ${typedFault.id ?? "unknown"} window exceeds estimated run duration.`);
    }
  }
  if (liveMode) {
    warnings.push("Live mode can consume provider credits. Review request count and route count.");
  }

  return {
    errors,
    warnings,
    maxGatewayCalls: scenario.request_count * routeCount,
    estimatedDurationMs,
  };
}

export function cloneScenario(scenario: Scenario, suffix: string): Scenario {
  return {
    ...scenario,
    id: `${scenario.id}-${suffix}`,
    seed: Math.floor(Math.random() * 1_000_000),
    fault_rules: [...scenario.fault_rules],
    routing_profile: {
      ...scenario.routing_profile,
      routes: [...scenario.routing_profile.routes],
    },
  };
}

