import type { UseQueryResult } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import type { HealthResponse } from "@/lib/api";

type HealthCardProps = {
  query: UseQueryResult<HealthResponse, Error>;
};

export function HealthCard({ query }: HealthCardProps) {
  if (query.isLoading) {
    return (
      <div className="flex items-center gap-3 rounded-md border bg-muted p-4 text-sm">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Checking backend health...
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900">
        <AlertCircle className="mt-0.5 h-4 w-4" aria-hidden="true" />
        <div>
          <p className="font-medium">Backend unavailable</p>
          <p className="mt-1">{query.error.message}</p>
        </div>
      </div>
    );
  }

  const health = query.data;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="flex items-start gap-3 rounded-md border p-4">
        <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium">Status</p>
          <p className="mt-1 text-2xl font-semibold">{health?.status}</p>
        </div>
      </div>
      <dl className="grid gap-3 rounded-md border p-4 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Service</dt>
          <dd className="font-medium">{health?.service}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Version</dt>
          <dd className="font-medium">{health?.version}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Environment</dt>
          <dd className="font-medium">{health?.environment}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Simulation</dt>
          <dd className="font-medium">{health?.simulation_mode}</dd>
        </div>
      </dl>
    </div>
  );
}

