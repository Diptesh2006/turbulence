"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ShieldAlert } from "lucide-react";
import { createAgentRun, getAgentScenarios } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingSkeleton } from "@/components/states";

const riskClasses: Record<string, string> = {
  low: "border-emerald-300 text-emerald-800",
  medium: "border-amber-300 text-amber-800",
  high: "border-orange-300 text-orange-800",
  critical: "border-red-300 text-red-800",
};

export default function AgentSafetyPage() {
  const queryClient = useQueryClient();
  const scenarios = useQuery({ queryKey: ["agent-scenarios"], queryFn: getAgentScenarios });
  const launch = useMutation({
    mutationFn: createAgentRun,
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["agent-runs"] }),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Agent Safety Lab / SIMULATED"
        title="Test agent actions against policy"
        description="Evaluate deterministic action proposals, policy decisions, synthetic secret tracking, and containment. No real tools are invoked."
        action={<Link href="/agent-safety/runs" className="text-sm font-medium text-primary">View safety runs <ArrowRight className="inline h-4 w-4" /></Link>}
      />
      {scenarios.isLoading ? <LoadingSkeleton rows={3} /> : null}
      {scenarios.isError ? <ErrorState title="Scenarios unavailable" error={scenarios.error} /> : null}
      {launch.isError ? <ErrorState title="Run could not be created" error={launch.error} /> : null}
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Agent safety scenarios">
        {scenarios.data?.items.map((scenario) => (
          <article key={scenario.id} className="panel flex min-h-52 flex-col p-4">
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-semibold">{scenario.name}</h2>
              <span className={`rounded border px-2 py-1 text-xs font-medium uppercase ${riskClasses[scenario.severity]}`}>
                {scenario.severity}
              </span>
            </div>
            <p className="mt-2 flex-1 text-sm text-muted-foreground">{scenario.description}</p>
            <div className="mt-4 flex items-center justify-between border-t pt-3">
              <span className="metadata text-muted-foreground">{scenario.actions.length} proposed actions</span>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                disabled={launch.isPending}
                onClick={() => launch.mutate(scenario.id)}
              >
                <ShieldAlert className="h-4 w-4" aria-hidden="true" />
                Run scenario
              </button>
            </div>
          </article>
        ))}
      </section>
      {launch.data ? (
        <div className="mt-5 border-l-4 border-primary bg-white p-4 text-sm">
          Run completed: <Link className="font-medium text-primary underline" href={`/agent-safety/runs/${launch.data.id}`}>{launch.data.verdict} · {launch.data.id}</Link>
        </div>
      ) : null}
    </div>
  );
}
