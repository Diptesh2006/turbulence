"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AgentPolicy, getAgentPolicies, updateAgentPolicy } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingSkeleton } from "@/components/states";

export default function AgentPoliciesPage() {
  const queryClient = useQueryClient();
  const policies = useQuery({ queryKey: ["agent-policies"], queryFn: getAgentPolicies });
  const update = useMutation({
    mutationFn: updateAgentPolicy,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agent-policies"] }),
  });
  return (
    <div>
      <PageHeader eyebrow="Control Plane / Policies / SIMULATED" title="Agent safety policies" description="Baseline deterministic rules applied to the simulated action stream." />
      {policies.isLoading ? <LoadingSkeleton rows={3} /> : null}
      {policies.isError ? <ErrorState title="Policies unavailable" error={policies.error} /> : null}
      {update.isError ? <ErrorState title="Policy update failed" error={update.error} /> : null}
      <div className="divide-y border-y bg-white">
        {policies.data?.items.map((rule) => (
          <article key={rule.id} className="grid gap-3 px-4 py-4 md:grid-cols-[100px_1fr_130px]">
            <div className="metadata text-muted-foreground">Priority {rule.priority}</div>
            <div>
              <h2 className="font-medium">{rule.name}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{rule.description}</p>
              <p className="mt-2 text-xs">Matches: {rule.categories.length ? rule.categories.join(", ") : "fallback rule"}</p>
            </div>
            <label className="grid gap-1 text-xs text-muted-foreground">
              Decision
              <select
                className="h-9 rounded-md border bg-white px-2 text-sm font-semibold text-foreground"
                value={rule.decision}
                disabled={update.isPending}
                onChange={(event) => update.mutate({ ...rule, decision: event.target.value as AgentPolicy["decision"] })}
              >
                {["ALLOW", "AUDIT", "WARN", "REQUIRE_APPROVAL", "BLOCK"].map((decision) => <option key={decision}>{decision}</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm md:col-start-2">
              <input
                type="checkbox"
                checked={rule.enabled}
                disabled={update.isPending}
                onChange={(event) => update.mutate({ ...rule, enabled: event.target.checked })}
              />
              Enabled
            </label>
          </article>
        ))}
      </div>
    </div>
  );
}
