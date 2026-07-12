import { describe, expect, it } from "vitest";
import {
  comparisonBadge,
  formatComparisonValue,
  formatDelta,
  formatPercentDelta,
  orderedDifferences,
} from "./compare-utils";
import { Comparison } from "@/lib/api";

describe("compare utils", () => {
  it("formats N/A values without treating them as zero", () => {
    expect(formatComparisonValue("total_cost", null)).toBe("N/A");
    expect(formatDelta("total_cost", null)).toBe("N/A");
    expect(formatPercentDelta(null)).toBe("N/A");
  });

  it("formats latency and correctness values by metric type", () => {
    expect(formatComparisonValue("p95_end_to_end_latency_ms", 123.4)).toBe("123 ms");
    expect(formatComparisonValue("overall_correctness_rate", 98.25)).toBe("98.3%");
  });

  it("labels improvement and regression states", () => {
    expect(comparisonBadge("improvement")).toBe("Improvement");
    expect(comparisonBadge("regression")).toBe("Regression");
    expect(comparisonBadge("no_data")).toBe("No data");
  });

  it("orders known comparison metrics and skips missing entries", () => {
    const comparison = {
      baseline_run_id: "a",
      candidate_run_id: "b",
      differences: {
        p95_end_to_end_latency_ms: {
          before: 200,
          after: 100,
          absolute_difference: -100,
          percentage_difference: -50,
          direction: "lower_is_better",
          change_kind: "improvement",
        },
        overall_correctness_rate: {
          before: 90,
          after: 100,
          absolute_difference: 10,
          percentage_difference: 11.1,
          direction: "higher_is_better",
          change_kind: "improvement",
        },
      },
    } as Comparison;

    expect(orderedDifferences(comparison).map(([key]) => key)).toEqual([
      "overall_correctness_rate",
      "p95_end_to_end_latency_ms",
    ]);
  });
});
