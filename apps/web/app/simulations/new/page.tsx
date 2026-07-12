"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getScenarios, getWorkloads } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/states";
import { ScenarioCard } from "@/components/scenario-card";

export default function NewSimulationPage() {
  const workloads = useQuery({ queryKey: ["workloads"], queryFn: getWorkloads });
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: getScenarios });

  return (
    <div>
      <PageHeader
        eyebrow="Simulation setup"
        title="Scenario configuration flow"
        description="Select a preset or saved scenario. Run creation controls will use the public API; live SSE cockpit is intentionally deferred."
      />

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <section className="space-y-4">
          <div className="panel p-4">
            <h2 className="font-semibold">1. Choose workload</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Workloads define deterministic fixtures and validation rules.
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              {workloads.isLoading ? <LoadingSkeleton rows={2} /> : null}
              {workloads.isError ? <ErrorState error={workloads.error} /> : null}
              {workloads.data?.map((workload) => (
                <ScenarioCard key={workload.name} workload={workload} />
              ))}
            </div>
          </div>

          <div className="panel p-4">
            <h2 className="font-semibold">2. Select saved configuration</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Saved scenarios come from the backend and can be used to create runs.
            </p>
            <div className="mt-4">
              {scenarios.isLoading ? <LoadingSkeleton /> : null}
              {scenarios.isError ? <ErrorState error={scenarios.error} /> : null}
              {scenarios.data && scenarios.data.items.length === 0 ? (
                <EmptyState
                  title="No saved scenarios"
                  detail="Create scenarios through the API to enable one-click run creation here."
                />
              ) : null}
              <div className="grid gap-4 md:grid-cols-2">
                {scenarios.data?.items.map((scenario) => (
                  <ScenarioCard key={scenario.id} scenario={scenario} />
                ))}
              </div>
            </div>
          </div>
        </section>

        <aside className="panel p-4">
          <h2 className="font-semibold">Configuration checklist</h2>
          <ol className="mt-4 space-y-3 text-sm text-muted-foreground">
            <li>1. Pick a workload fixture set.</li>
            <li>2. Confirm routing profile and fault rules.</li>
            <li>3. Set request rate, concurrency, seed, and SLOs.</li>
            <li>4. Start the run and inspect the cockpit.</li>
          </ol>
          <Link href="/scenarios" className="mt-5 inline-flex text-sm font-medium text-primary">
            Review scenarios
          </Link>
        </aside>
      </div>
    </div>
  );
}

