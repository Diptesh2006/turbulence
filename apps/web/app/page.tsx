"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ClipboardList, RadioTower, ServerCrash } from "lucide-react";
import {
  getHealth,
  getIntegrationStatus,
  getRuns,
  getScenarios,
} from "@/lib/api";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/states";
import { MetricCard } from "@/components/metric-card";
import { ModeBadge, RunStatusBadge, ServiceStatusIndicator, SourceBadge } from "@/components/status";
import { PageHeader } from "@/components/page-header";

export default function Home() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 15000 });
  const integration = useQuery({
    queryKey: ["integration", "concentrate"],
    queryFn: getIntegrationStatus,
    refetchInterval: 15000,
  });
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: getScenarios });
  const runs = useQuery({ queryKey: ["runs", 1, 5], queryFn: () => getRuns(1, 5) });

  return (
    <div>
      <PageHeader
        eyebrow="Turbulence / AI Flight Simulator"
        title="Crash-test your LLM stack before production."
        description="Run deterministic workloads through routing, fallback, and fault-injection paths before a customer finds the weak point."
        action={
          <Link
            href="/simulations/new"
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            Start simulation
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        }
      />

      <section className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Scenarios" value={scenarios.data?.items.length} detail="configured" />
        <MetricCard label="Recent runs" value={runs.data?.total} detail="stored in API" />
        <MetricCard label="API environment" value={health.data?.environment ?? null} />
        <MetricCard label="Simulation mode" value={health.data?.simulation_mode ?? null} />
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[1fr_360px]">
        <div className="panel">
          <div className="flex items-center justify-between border-b p-4">
            <div>
              <h2 className="font-semibold">Recent runs</h2>
              <p className="text-sm text-muted-foreground">Latest stored simulation runs.</p>
            </div>
            <Link href="/simulations/new" className="text-sm font-medium text-primary">
              New run
            </Link>
          </div>
          <div className="p-4">
            {runs.isLoading ? <LoadingSkeleton /> : null}
            {runs.isError ? <ErrorState error={runs.error} /> : null}
            {runs.data && runs.data.items.length === 0 ? (
              <EmptyState
                title="No runs yet"
                detail="Create a scenario run to populate the cockpit and post-flight reports."
              />
            ) : null}
            {runs.data && runs.data.items.length > 0 ? (
              <div className="divide-y">
                {runs.data.items.map((run) => (
                  <Link
                    key={run.id}
                    href={`/runs/${run.id}`}
                    className="grid gap-3 py-3 text-sm hover:bg-muted/60 md:grid-cols-[1fr_140px_140px]"
                  >
                    <div>
                      <div className="font-medium">{run.scenario_id}</div>
                      <div className="metadata text-muted-foreground">{run.id}</div>
                    </div>
                    <RunStatusBadge state={run.state} />
                    <div className="metadata text-muted-foreground">
                      {new Date(run.created_at).toLocaleString()}
                    </div>
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <aside className="space-y-6">
          <div className="panel p-4">
            <h2 className="font-semibold">Integration health</h2>
            <div className="mt-4 space-y-3">
              {health.data ? (
                <ServiceStatusIndicator status={health.data.status} label={health.data.service} />
              ) : null}
              {integration.data ? (
                <div className="flex items-center justify-between rounded-md border p-3 text-sm">
                  <div className="flex items-center gap-2">
                    <RadioTower className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                    Concentrate
                  </div>
                  <div className="flex items-center gap-2">
                    <ModeBadge mode={integration.data.mode} />
                    <SourceBadge source={integration.data.is_mock ? "MOCK" : "REAL"} />
                  </div>
                </div>
              ) : null}
              {health.isLoading || integration.isLoading ? <LoadingSkeleton rows={1} /> : null}
              {health.isError ? <ErrorState title="Health unavailable" error={health.error} /> : null}
              {integration.isError ? (
                <ErrorState title="Integration unavailable" error={integration.error} />
              ) : null}
            </div>
          </div>

          <div className="panel p-4">
            <div className="flex items-center gap-2">
              <ServerCrash className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <h2 className="font-semibold">Product overview</h2>
            </div>
            <div className="mt-4 space-y-3 text-sm text-muted-foreground">
              <p>Structured workloads validate routing, fallback, and response correctness.</p>
              <p>Faults are labeled simulated and never represented as real provider incidents.</p>
              <p>Reports preserve unknown costs and tokens as unknown, not zero.</p>
            </div>
          </div>

          <div className="panel p-4">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <h2 className="font-semibold">Configured scenarios</h2>
            </div>
            <div className="mt-3 text-3xl font-semibold">{scenarios.data?.items.length ?? "n/a"}</div>
          </div>
        </aside>
      </section>
    </div>
  );
}

