import { Report } from "@/lib/api";

export function formatNumber(value: number | null | undefined, digits = 1): string {
  return value == null ? "N/A" : value.toFixed(digits);
}

export function formatPercent(value: number | null | undefined): string {
  return value == null ? "N/A" : `${value.toFixed(1)}%`;
}

export function formatCurrency(value: number | null | undefined): string {
  return value == null ? "N/A" : `$${value.toFixed(4)}`;
}

export function verdictLabel(verdict: string | undefined): string {
  const labels: Record<string, string> = {
    production_ready: "Production ready",
    degraded_but_recovered: "Degraded but recovered",
    unreliable: "Unreliable",
    inconclusive: "Inconclusive",
  };
  return verdict ? labels[verdict] ?? verdict : "Inconclusive";
}

export function verdictClassName(verdict: string | undefined): string {
  if (verdict === "production_ready") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (verdict === "degraded_but_recovered") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (verdict === "unreliable") {
    return "border-red-200 bg-red-50 text-red-800";
  }
  return "border-zinc-200 bg-zinc-50 text-zinc-700";
}

export function sortIncidentTimeline(report: Report) {
  return [...report.incident_timeline].sort((a, b) => a.sequence - b.sequence);
}

export function sourceBadgeValue(source: string): "REAL" | "SIMULATED" | "MOCK" | "SYSTEM" {
  if (source === "real") return "REAL";
  if (source === "simulated") return "SIMULATED";
  if (source === "mock") return "MOCK";
  return "SYSTEM";
}

export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
