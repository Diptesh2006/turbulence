"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { getAgentRun, replayAgentRun } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingSkeleton } from "@/components/states";

export default function AgentRunDetailPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const run = useQuery({ queryKey: ["agent-run", params.id], queryFn: () => getAgentRun(params.id) });
  const replay = useMutation({
    mutationFn: replayAgentRun,
    onSuccess: (result) => queryClient.setQueryData(["agent-run", result.id], result),
  });
  if (run.isLoading) return <LoadingSkeleton rows={4} />;
  if (run.isError || !run.data) {
    return <ErrorState title="Run unavailable" error={run.error ?? new Error("Run not found.")} />;
  }
  return (
    <div>
      <PageHeader
        eyebrow="Agent Safety Lab / SIMULATED RUN"
        title={run.data.scenario_id}
        description={`Verdict: ${run.data.verdict.toUpperCase()} · seed ${run.data.seed} · run ${run.data.id}`}
        action={<button className="rounded-md border bg-white px-3 py-2 text-sm font-medium" onClick={() => replay.mutate(run.data.id)} disabled={replay.isPending}>Replay</button>}
      />
      <section className="mb-6 grid gap-3 md:grid-cols-3">
        <div className="border bg-white p-4"><div className="text-sm text-muted-foreground">Safety score</div><div className="mt-1 text-2xl font-semibold">{run.data.safety_score}/100</div></div>
        <div className="border bg-white p-4"><div className="text-sm text-muted-foreground">Attack containment</div><div className="mt-1 text-2xl font-semibold">{run.data.attack_containment_rate === null ? "N/A" : `${run.data.attack_containment_rate}%`}</div></div>
        <div className="border bg-white p-4"><div className="text-sm text-muted-foreground">Synthetic secrets tracked</div><div className="mt-1 text-2xl font-semibold">{run.data.metrics.synthetic_secrets_tracked ?? 0}</div></div>
      </section>
      <section aria-label="Agent action trajectory" className="divide-y border-y bg-white">
        {run.data.actions.map((item) => (
          <article key={item.sequence} className="grid gap-3 p-4 lg:grid-cols-[44px_1fr_145px]">
            <div className="metadata pt-1 text-muted-foreground">{String(item.sequence).padStart(2, "0")}</div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-medium">{item.action.tool} / {item.action.operation}</h2>
                <span className="rounded border px-2 py-0.5 text-xs uppercase">{item.action.risk}</span>
                {item.action.synthetic_secret_ids.length ? <span className="rounded border border-amber-400 px-2 py-0.5 text-xs">Synthetic secret fixture</span> : null}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{item.explanation}</p>
              {item.approval_resolution ? <p className="mt-2 text-xs font-medium uppercase">{item.approval_resolution.replaceAll("_", " ")} · no human reviewer</p> : null}
              {item.matched_rule_id ? <p className="metadata mt-2">Matched policy: {item.matched_rule_id}</p> : null}
              <details className="mt-3 text-xs">
                <summary className="cursor-pointer font-medium">Decision context</summary>
                <pre className="mt-2 overflow-x-auto bg-muted p-3">{JSON.stringify(item.context, null, 2)}</pre>
              </details>
              <pre className="mt-3 overflow-x-auto bg-muted p-3 text-xs">{JSON.stringify(item.simulated_result, null, 2)}</pre>
            </div>
            <div className={`text-sm font-bold ${item.prevented ? "text-red-700" : "text-emerald-700"}`}>
              {item.decision}{item.prevented ? " · PREVENTED" : " · SIMULATED"}
            </div>
          </article>
        ))}
      </section>
      <details className="mt-6 border-y bg-white">
        <summary className="cursor-pointer px-4 py-3 font-semibold">Simulation event timeline ({run.data.events.length})</summary>
        <ol className="divide-y">
          {run.data.events.map((event) => (
            <li key={event.sequence} className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[56px_220px_1fr]">
              <span className="metadata text-muted-foreground">{String(event.sequence).padStart(3, "0")}</span>
              <span className="font-medium">{event.type}</span>
              <span className="text-muted-foreground">{JSON.stringify(event.payload)}</span>
            </li>
          ))}
        </ol>
      </details>
      {replay.data ? <p className="mt-4 text-sm">Replay created: <Link className="text-primary underline" href={`/agent-safety/runs/${replay.data.id}`}>{replay.data.id}</Link></p> : null}
    </div>
  );
}
