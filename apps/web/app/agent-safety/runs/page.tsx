"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getAgentRuns } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/states";

export default function AgentRunsPage() {
  const runs = useQuery({ queryKey: ["agent-runs"], queryFn: getAgentRuns });
  return (
    <div>
      <PageHeader eyebrow="Agent Safety Lab / Runs" title="Safety run history" description="Completed deterministic evaluations and their policy outcomes." />
      {runs.isLoading ? <LoadingSkeleton /> : null}
      {runs.isError ? <ErrorState title="Run history unavailable" error={runs.error} /> : null}
      {runs.data && runs.data.items.length === 0 ? <EmptyState title="No safety runs" detail="Start a scenario in the Agent Safety Lab." /> : null}
      <div className="divide-y border-y bg-white">
        {runs.data?.items.map((run) => (
          <Link key={run.id} href={`/agent-safety/runs/${run.id}`} className="grid gap-2 px-4 py-4 hover:bg-muted/50 md:grid-cols-[1fr_130px_100px_100px]">
            <span><strong className="block font-medium">{run.scenario_id}</strong><span className="metadata text-muted-foreground">{run.id}</span></span>
            <span className="uppercase">{run.verdict}</span>
            <span>{run.safety_score}/100</span>
            <time className="text-sm text-muted-foreground">{new Date(run.created_at).toLocaleString()}</time>
          </Link>
        ))}
      </div>
    </div>
  );
}
