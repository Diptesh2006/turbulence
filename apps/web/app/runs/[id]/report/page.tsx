"use client";

import { useQuery } from "@tanstack/react-query";
import { getRunReport } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { ErrorState, LoadingSkeleton } from "@/components/states";
import { RunStatusBadge } from "@/components/status";

export default function RunReportPage({ params }: { params: { id: string } }) {
  const report = useQuery({ queryKey: ["run-report", params.id], queryFn: () => getRunReport(params.id) });
  const data = report.data?.report;
  const metrics = data?.metrics;

  return (
    <div>
      <PageHeader
        eyebrow="Post-flight report"
        title={params.id}
        description="Reliability metrics are computed from stored requests, attempts, and events."
        action={data ? <RunStatusBadge state={data.run_state} /> : null}
      />
      {report.isLoading ? <LoadingSkeleton /> : null}
      {report.isError ? <ErrorState error={report.error} /> : null}
      {metrics ? (
        <div className="space-y-6">
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Availability" value={formatPct(metrics.availability_percentage)} />
            <MetricCard label="Correctness" value={formatPct(metrics.overall_correctness_rate)} />
            <MetricCard label="Fallback recovery" value={formatPct(metrics.fallback_recovery_rate)} />
            <MetricCard label="Resilience score" value={formatPct(metrics.resilience_score.score)} />
          </section>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total attempts" value={metrics.total_attempts} />
            <MetricCard label="Real errors" value={metrics.real_error_count} />
            <MetricCard label="Simulated errors" value={metrics.simulated_error_count} />
            <MetricCard label="Total cost" value={metrics.total_cost} />
          </section>
          <section className="panel p-4">
            <h2 className="font-semibold">Distributions</h2>
            <pre className="mt-4 overflow-auto rounded-md bg-muted p-3 text-xs">
              {JSON.stringify(
                {
                  requests_by_actual_model_provider: metrics.requests_by_actual_model_provider,
                  error_distribution_by_type: metrics.error_distribution_by_type,
                  route_attempt_distribution: metrics.route_attempt_distribution,
                },
                null,
                2,
              )}
            </pre>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function formatPct(value: number | null | undefined) {
  return value == null ? null : `${value.toFixed(1)}%`;
}

