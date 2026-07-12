"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink } from "lucide-react";
import { getRunReport } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { ErrorState, LoadingSkeleton } from "@/components/states";
import { ModeBadge, RunStatusBadge, SourceBadge } from "@/components/status";
import { Button } from "@/components/ui/button";
import {
  downloadJson,
  formatCurrency,
  formatNumber,
  formatPercent,
  sortIncidentTimeline,
  sourceBadgeValue,
  verdictClassName,
  verdictLabel,
} from "./report-utils";

export default function RunReportPage({ params }: { params: { id: string } }) {
  const report = useQuery({
    queryKey: ["run-report", params.id],
    queryFn: () => getRunReport(params.id),
  });
  const data = report.data?.report;
  const metrics = data?.metrics;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Post-flight report"
        title={data?.scenario_id ?? params.id}
        description={data ? `Run ID: ${data.run_id}` : "Reliability report"}
        action={
          data ? (
            <div className="flex flex-wrap items-center justify-end gap-2">
              <ModeBadge mode={data.mode} />
              <RunStatusBadge state={data.run_state} />
              <Button variant="outline" asChild>
                <Link href={`/runs/${params.id}`}>
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Cockpit
                </Link>
              </Button>
              <Button
                variant="outline"
                onClick={() => downloadJson(`turbulence-report-${params.id}.json`, data)}
              >
                <Download className="mr-2 h-4 w-4" />
                Export JSON
              </Button>
            </div>
          ) : null
        }
      />

      {report.isLoading ? <LoadingSkeleton rows={6} /> : null}
      {report.isError ? <ErrorState error={report.error} /> : null}

      {data && metrics ? (
        <>
          <section className="panel p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <div className="text-xs font-medium uppercase text-muted-foreground">
                  Executive verdict
                </div>
                <div
                  className={`mt-3 inline-flex rounded-md border px-3 py-2 text-sm font-semibold ${verdictClassName(
                    data.executive_verdict?.verdict,
                  )}`}
                >
                  {verdictLabel(data.executive_verdict?.verdict)}
                </div>
                <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
                  {data.executive_verdict?.explanation ??
                    "Deterministic verdict is unavailable for this report."}
                </p>
              </div>
              <div className="metadata text-right text-xs text-muted-foreground">
                <div>Started: {data.created_at ?? "N/A"}</div>
                <div>Completed: {data.updated_at ?? "N/A"}</div>
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <MetricCard
              label="Resilience score"
              value={metrics.resilience_score.score == null ? "N/A" : `${metrics.resilience_score.score.toFixed(0)}/100`}
              detail={`${metrics.resilience_score.components.filter((item) => !item.excluded).length} active components`}
            />
            <MetricCard label="Availability" value={formatPercent(metrics.availability_percentage)} />
            <MetricCard label="Correctness" value={formatPercent(metrics.overall_correctness_rate)} />
            <MetricCard label="p95 latency" value={`${formatNumber(metrics.p95_end_to_end_latency_ms, 0)} ms`} />
            <MetricCard label="Fallback recovery" value={formatPercent(metrics.fallback_recovery_rate)} />
          </section>

          <section className="panel p-5">
            <h2 className="text-sm font-semibold">Resilience score breakdown</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {metrics.resilience_score.formula_explanation ??
                "Applicable score components are reweighted when a component is not applicable."}
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {metrics.resilience_score.components.map((component) => (
                <div key={component.name} className="rounded-md border bg-white p-3">
                  <div className="metadata text-xs uppercase text-muted-foreground">
                    {component.name.replace("_", " ")}
                  </div>
                  <div className="mt-2 text-lg font-semibold">
                    {component.excluded
                      ? "Excluded"
                      : `${formatNumber(component.earned_points, 1)} / ${formatNumber(component.max_points, 0)}`}
                  </div>
                  {component.reason ? (
                    <div className="mt-1 text-xs text-muted-foreground">{component.reason}</div>
                  ) : null}
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Schema validity" value={formatPercent(metrics.schema_valid_response_rate)} />
            <MetricCard label="Category accuracy" value={formatPercent(metrics.category_accuracy)} />
            <MetricCard label="Priority accuracy" value={formatPercent(metrics.priority_accuracy)} />
            <MetricCard label="Time to recovery" value={`${formatNumber(metrics.time_to_recovery_ms, 0)} ms`} />
            <MetricCard label="Tokens" value={metrics.tokens.total_tokens ?? "N/A"} detail={`${metrics.tokens.input_tokens ?? "N/A"} in / ${metrics.tokens.output_tokens ?? "N/A"} out`} />
            <MetricCard label="Total cost" value={formatCurrency(metrics.total_cost)} />
            <MetricCard label="Cost per success" value={formatCurrency(metrics.cost_per_successful_request)} />
            <MetricCard label="Errors" value={`${metrics.real_error_count} real / ${metrics.simulated_error_count} simulated`} />
          </section>

          <section className="panel p-5">
            <h2 className="text-sm font-semibold">Incident timeline</h2>
            <div className="mt-4 overflow-hidden rounded-md border">
              {sortIncidentTimeline(data).length ? (
                sortIncidentTimeline(data).map((event) => (
                  <div
                    key={event.sequence}
                    className="grid gap-3 border-b bg-white p-3 text-sm last:border-b-0 md:grid-cols-[80px_160px_130px_1fr]"
                  >
                    <div className="metadata">#{event.sequence}</div>
                    <div className="metadata text-muted-foreground">{new Date(event.timestamp).toLocaleString()}</div>
                    <SourceBadge source={sourceBadgeValue(event.source)} />
                    <div>
                      <div className="font-medium">{event.label}</div>
                      <div className="metadata mt-1 text-muted-foreground">
                        {event.event_type}
                        {event.request_id ? ` / ${event.request_id}` : ""}
                        {event.route_index != null ? ` / route ${event.route_index}` : ""}
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-sm text-muted-foreground">No incident events were recorded.</div>
              )}
            </div>
          </section>

          <section className="panel p-5">
            <h2 className="text-sm font-semibold">Route analysis</h2>
            <div className="mt-4 overflow-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2">Route</th>
                    <th>Requested</th>
                    <th>Actual returned</th>
                    <th>Attempts</th>
                    <th>Success</th>
                    <th>Failed</th>
                    <th>Routing mode</th>
                  </tr>
                </thead>
                <tbody>
                  {data.route_analysis.map((route) => (
                    <tr key={route.route_index} className="border-b last:border-b-0">
                      <td className="py-3 metadata">{route.route_index}</td>
                      <td className="metadata">{route.requested_model}/{route.requested_provider ?? "unspecified"}</td>
                      <td className="metadata">{route.actual_model ?? "N/A"}/{route.actual_provider ?? "N/A"}</td>
                      <td>{route.attempts}</td>
                      <td>{route.successes}</td>
                      <td>{route.failures}</td>
                      <td>{route.concentrate_native ? "Concentrate-native" : route.simulator_managed_fallback ? "Simulator-managed fallback" : "Primary route"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="panel p-5">
              <h2 className="text-sm font-semibold">Failure analysis</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {data.failure_analysis
                  ? Object.entries({
                      real: data.failure_analysis.real_failures,
                      simulated: data.failure_analysis.simulated_failures,
                      validation: data.failure_analysis.validation_failures,
                      rate_limits: data.failure_analysis.rate_limits,
                      malformed_json: data.failure_analysis.malformed_json,
                      provider_outage: data.failure_analysis.provider_outage_injections,
                    }).map(([label, value]) => (
                      <div key={label} className="rounded-md border bg-white p-3">
                        <div className="metadata text-xs uppercase text-muted-foreground">{label.replace("_", " ")}</div>
                        <div className="mt-1 text-lg font-semibold">{value}</div>
                      </div>
                    ))
                  : null}
              </div>
            </div>
            <div className="panel p-5">
              <h2 className="text-sm font-semibold">Recommendations</h2>
              <ul className="mt-4 space-y-3 text-sm">
                {data.recommendations.map((item) => (
                  <li key={item.code} className="rounded-md border bg-white p-3">
                    <div className="metadata text-xs uppercase text-muted-foreground">{item.code}</div>
                    <div className="mt-1">{item.message}</div>
                  </li>
                ))}
              </ul>
              <div className="mt-4 rounded-md border bg-muted p-3 text-xs text-muted-foreground">
                {data.ai_analysis?.label ?? "AI-generated analysis unavailable"}
              </div>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
