"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getRun } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { RunStatusBadge, SourceBadge } from "@/components/status";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/states";

export default function RunCockpitPage({ params }: { params: { id: string } }) {
  const run = useQuery({ queryKey: ["run", params.id], queryFn: () => getRun(params.id) });
  const data = run.data?.run;

  return (
    <div>
      <PageHeader
        eyebrow="Live cockpit"
        title={params.id}
        description="Run detail is loaded from the REST API. Live SSE event playback is not implemented in this frontend shell yet."
        action={data ? <RunStatusBadge state={data.state} /> : null}
      />

      {run.isLoading ? <LoadingSkeleton /> : null}
      {run.isError ? <ErrorState error={run.error} /> : null}
      {data ? (
        <div className="space-y-6">
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Requests" value={data.metrics.total_requests ?? 0} />
            <MetricCard label="Completed" value={data.metrics.completed_requests ?? 0} />
            <MetricCard label="Failed" value={data.metrics.failed_requests ?? 0} />
            <MetricCard label="Abandoned" value={data.metrics.abandoned_requests ?? 0} />
          </section>

          <section className="panel p-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h2 className="font-semibold">Scenario</h2>
                <p className="metadata mt-1 text-muted-foreground">{data.scenario.id}</p>
              </div>
              <SourceBadge source="SYSTEM" />
            </div>
            <dl className="mt-4 grid gap-4 text-sm md:grid-cols-3">
              <div>
                <dt className="text-muted-foreground">Workload</dt>
                <dd className="font-medium">{data.scenario.workload_name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Routing</dt>
                <dd className="font-medium">{data.scenario.routing_profile.type}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Seed</dt>
                <dd className="font-medium">{data.scenario.seed}</dd>
              </div>
            </dl>
          </section>

          <section>
            {data.requests && data.requests.length > 0 ? (
              <div className="panel overflow-hidden">
                <div className="border-b p-4 font-semibold">Stored request records</div>
                <div className="divide-y">
                  {data.requests.map((request, index) => (
                    <div key={index} className="p-4 text-sm">
                      <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">
                        {JSON.stringify(request, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyState
                title="No request records"
                detail="Start the run to populate attempts and validation results."
              />
            )}
          </section>

          <Link href={`/runs/${params.id}/report`} className="inline-flex text-sm font-medium text-primary">
            Open post-flight report
          </Link>
        </div>
      ) : null}
    </div>
  );
}

