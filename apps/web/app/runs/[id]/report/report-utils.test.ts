import { describe, expect, it } from "vitest";
import {
  formatCurrency,
  formatPercent,
  sortIncidentTimeline,
  sourceBadgeValue,
  verdictLabel,
} from "./report-utils";
import { Report } from "@/lib/api";

describe("report utils", () => {
  it("renders deterministic verdict labels", () => {
    expect(verdictLabel("production_ready")).toBe("Production ready");
    expect(verdictLabel("degraded_but_recovered")).toBe("Degraded but recovered");
    expect(verdictLabel("unreliable")).toBe("Unreliable");
  });

  it("formats unknown cost as N/A", () => {
    expect(formatCurrency(null)).toBe("N/A");
    expect(formatCurrency(0.01234)).toBe("$0.0123");
  });

  it("formats unknown percentages as N/A", () => {
    expect(formatPercent(null)).toBe("N/A");
    expect(formatPercent(99.95)).toBe("100.0%");
  });

  it("orders incident timeline by sequence", () => {
    const report = {
      incident_timeline: [
        { sequence: 3, timestamp: "", event_type: "run.completed", source: "system", label: "done", payload: {} },
        { sequence: 1, timestamp: "", event_type: "fault.activated", source: "simulated", label: "fault", payload: {} },
      ],
    } as Report;

    expect(sortIncidentTimeline(report).map((event) => event.sequence)).toEqual([1, 3]);
  });

  it("maps source badges without relabeling simulated behavior as real", () => {
    expect(sourceBadgeValue("real")).toBe("REAL");
    expect(sourceBadgeValue("simulated")).toBe("SIMULATED");
    expect(sourceBadgeValue("mock")).toBe("MOCK");
    expect(sourceBadgeValue("system")).toBe("SYSTEM");
  });
});
