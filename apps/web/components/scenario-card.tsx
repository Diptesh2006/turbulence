import Link from "next/link";
import type { Scenario, WorkloadSummary } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function ScenarioCard({
  scenario,
  workload,
}: {
  scenario?: Scenario;
  workload?: WorkloadSummary;
}) {
  const title = scenario?.id ?? workload?.name ?? "Custom scenario";
  const workloadName = scenario?.workload_name ?? workload?.name ?? "support_ticket_triage";
  return (
    <article className="panel p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="metadata mt-1 text-muted-foreground">{workloadName}</p>
        </div>
        <span className="rounded-md border bg-muted px-2 py-1 text-xs">
          {scenario ? "custom" : "preset"}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-muted-foreground">Requests</dt>
          <dd className="font-medium">{scenario?.request_count ?? workload?.fixture_count ?? "n/a"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Routing</dt>
          <dd className="font-medium">{scenario?.routing_profile.type ?? "configurable"}</dd>
        </div>
      </dl>
      <Button asChild className="mt-4 w-full">
        <Link href="/simulations/new">Configure run</Link>
      </Button>
    </article>
  );
}

