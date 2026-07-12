import { AlertTriangle, CheckCircle2, CircleDashed, Server } from "lucide-react";
import { cn } from "@/lib/utils";

export function ServiceStatusIndicator({
  status,
  label = "API",
}: {
  status?: string;
  label?: string;
}) {
  const ok = status === "ok";
  const Icon = ok ? CheckCircle2 : AlertTriangle;
  return (
    <div className="flex items-center gap-2 rounded-md border bg-white px-3 py-2 text-sm">
      <Icon className={cn("h-4 w-4", ok ? "text-emerald-600" : "text-amber-600")} />
      <span className="font-medium">{label}</span>
      <span className="metadata text-muted-foreground">{status ?? "unknown"}</span>
    </div>
  );
}

export function ModeBadge({ mode }: { mode?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border bg-muted px-2 py-1 text-xs font-medium uppercase">
      <Server className="h-3 w-3" aria-hidden="true" />
      {mode ?? "unknown"}
    </span>
  );
}

export function SourceBadge({ source }: { source: "REAL" | "SIMULATED" | "MOCK" | "SYSTEM" }) {
  const className = {
    REAL: "border-emerald-200 bg-emerald-50 text-emerald-800",
    SIMULATED: "border-sky-200 bg-sky-50 text-sky-800",
    MOCK: "border-amber-200 bg-amber-50 text-amber-800",
    SYSTEM: "border-zinc-200 bg-zinc-50 text-zinc-700",
  }[source];
  return (
    <span className={cn("inline-flex rounded-md border px-2 py-1 text-xs font-semibold", className)}>
      {source}
    </span>
  );
}

export function RunStatusBadge({ state }: { state: string }) {
  const color =
    state === "completed"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : state === "failed"
        ? "border-red-200 bg-red-50 text-red-800"
        : state === "running"
          ? "border-sky-200 bg-sky-50 text-sky-800"
          : "border-zinc-200 bg-zinc-50 text-zinc-700";
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs", color)}>
      <CircleDashed className="h-3 w-3" aria-hidden="true" />
      {state}
    </span>
  );
}

