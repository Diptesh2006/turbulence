"use client";

import { useQuery } from "@tanstack/react-query";
import { getScenarios, getWorkloads } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { ScenarioCard } from "@/components/scenario-card";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/states";

export default function ScenariosPage() {
  const workloads = useQuery({ queryKey: ["workloads"], queryFn: getWorkloads });
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: getScenarios });

  return (
    <div>
      <PageHeader
        eyebrow="Scenario library"
        title="Preset and custom scenario cards"
        description="Review available workloads and configured scenario definitions before starting a run."
      />

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase text-muted-foreground">Presets</h2>
        {workloads.isLoading ? <LoadingSkeleton /> : null}
        {workloads.isError ? <ErrorState error={workloads.error} /> : null}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {workloads.data?.map((workload) => (
            <ScenarioCard key={workload.name} workload={workload} />
          ))}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase text-muted-foreground">Custom</h2>
        {scenarios.isLoading ? <LoadingSkeleton /> : null}
        {scenarios.isError ? <ErrorState error={scenarios.error} /> : null}
        {scenarios.data && scenarios.data.items.length === 0 ? (
          <EmptyState
            title="No custom scenarios"
            detail="Use the configuration flow to create a scenario for repeatable runs."
          />
        ) : null}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {scenarios.data?.items.map((scenario) => (
            <ScenarioCard key={scenario.id} scenario={scenario} />
          ))}
        </div>
      </section>
    </div>
  );
}

