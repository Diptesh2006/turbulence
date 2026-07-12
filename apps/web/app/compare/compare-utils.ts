import { Comparison } from "@/lib/api";

export const comparisonMetrics = [
  "resilience_score",
  "availability_percentage",
  "overall_correctness_rate",
  "schema_valid_response_rate",
  "p95_end_to_end_latency_ms",
  "p50_end_to_end_latency_ms",
  "time_to_recovery_ms",
  "fallback_recovery_rate",
  "successful_requests",
  "failed_requests",
  "real_error_count",
  "simulated_error_count",
  "total_cost",
  "cost_per_successful_request",
];

export function metricLabel(key: string): string {
  return key
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatComparisonValue(key: string, value: unknown): string {
  if (typeof value !== "number") return "N/A";
  if (key.includes("percentage") || key.includes("rate")) return `${value.toFixed(1)}%`;
  if (key.includes("latency") || key.includes("recovery_ms")) return `${value.toFixed(0)} ms`;
  if (key.includes("cost")) return `$${value.toFixed(4)}`;
  if (key === "resilience_score") return `${value.toFixed(0)}/100`;
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function formatDelta(key: string, value: number | null): string {
  if (value == null) return "N/A";
  const sign = value > 0 ? "+" : "";
  if (key.includes("percentage") || key.includes("rate")) return `${sign}${value.toFixed(1)} pts`;
  if (key.includes("latency") || key.includes("recovery_ms")) return `${sign}${value.toFixed(0)} ms`;
  if (key.includes("cost")) return `${sign}$${value.toFixed(4)}`;
  return `${sign}${Number.isInteger(value) ? value : value.toFixed(1)}`;
}

export function formatPercentDelta(value: number | null): string {
  if (value == null) return "N/A";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function comparisonBadge(changeKind: string): string {
  if (changeKind === "improvement") return "Improvement";
  if (changeKind === "regression") return "Regression";
  if (changeKind === "no_change") return "No change";
  return "No data";
}

export function comparisonClassName(changeKind: string): string {
  if (changeKind === "improvement") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (changeKind === "regression") return "border-red-200 bg-red-50 text-red-800";
  if (changeKind === "no_change") return "border-zinc-200 bg-zinc-50 text-zinc-700";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

export function orderedDifferences(comparison: Comparison) {
  return comparisonMetrics
    .map((key) => [key, comparison.differences[key]] as const)
    .filter(([, value]) => value);
}
