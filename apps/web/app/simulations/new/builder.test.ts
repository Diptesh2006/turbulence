import { describe, expect, it } from "vitest";
import type { Scenario } from "@/lib/api";
import { validateScenarioBuilder } from "./builder";

const baseScenario: Scenario = {
  id: "builder",
  mode: "deterministic_chaos",
  workload_name: "support_ticket_triage",
  request_count: 6,
  seed: 1,
  rate_per_second: 2,
  max_concurrency: 2,
  model: "gpt-4.1-mini",
  max_output_tokens: 96,
  recovery_time_slo_ms: 1000,
  latency_slo_ms: 2000,
  routing_profile: {
    id: "r",
    type: "resilient_route",
    routes: [
      { model: "gpt-4.1-mini", provider: "openai" },
      { model: "claude-3-5-haiku-latest", provider: "anthropic" },
    ],
  },
  fault_rules: [],
};

describe("scenario builder validation", () => {
  it("calculates maximum possible gateway calls", () => {
    const result = validateScenarioBuilder(baseScenario, false);
    expect(result.errors).toEqual([]);
    expect(result.maxGatewayCalls).toBe(12);
  });

  it("rejects duplicate routes", () => {
    const result = validateScenarioBuilder(
      {
        ...baseScenario,
        routing_profile: {
          ...baseScenario.routing_profile,
          routes: [
            { model: "same", provider: "openai" },
            { model: "same", provider: "openai" },
          ],
        },
      },
      false,
    );
    expect(result.errors.join(" ")).toContain("Duplicate routes");
  });

  it("rejects fault windows outside estimated run duration", () => {
    const result = validateScenarioBuilder(
      {
        ...baseScenario,
        fault_rules: [
          {
            id: "late",
            type: "latency_spike",
            start_after_ms: 4000,
            duration_ms: 500,
            probability: 1,
            parameters: { delay_ms: 10 },
            enabled: true,
          },
        ],
      },
      false,
    );
    expect(result.errors.join(" ")).toContain("window exceeds");
  });

  it("warns when live mode can consume credits", () => {
    const result = validateScenarioBuilder(
      { ...baseScenario, mode: "concentrate_native" },
      true,
      true,
    );
    expect(result.warnings.join(" ")).toContain("consume provider credits");
  });

  it("does not warn for mock deterministic mode on a live backend", () => {
    const result = validateScenarioBuilder({ ...baseScenario, mode: "mock" }, true, true);
    expect(result.warnings.join(" ")).not.toContain("consume provider credits");
  });

  it("rejects live mode when the backend is not live", () => {
    const result = validateScenarioBuilder(
      { ...baseScenario, mode: "concentrate_native" },
      false,
      false,
    );
    expect(result.errors.join(" ")).toContain("requires backend CNAI_MODE=live");
  });
});
