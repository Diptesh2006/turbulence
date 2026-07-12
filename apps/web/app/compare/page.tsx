"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { compareRuns, getRuns } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/states";
import { RunStatusBadge } from "@/components/status";
import { downloadJson } from "@/app/runs/[id]/report/report-utils";
import {
  comparisonBadge,
  comparisonClassName,
  formatComparisonValue,
  formatDelta,
  formatPercentDelta,
  metricLabel,
  orderedDifferences,
} from "./compare-utils";

export default function ComparePage() {
  const [baseline, setBaseline] = useState("");
  const [candidate, setCandidate] = useState("");
  const runs = useQuery({ queryKey: ["runs", "compare"], queryFn: () => getRuns(1, 100) });
  const comparison = useMutation({
    mutationFn: () => compareRuns(baseline, candidate),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    comparison.mutate();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Run comparison"
        title="Compare reliability deltas"
        description="Select a baseline and candidate run. Unknown values remain N/A and are not treated as zero."
        action={
          comparison.data ? (
            <Button
              variant="outline"
              onClick={() =>
                downloadJson("turbulence-comparison.json", comparison.data?.comparison)
              }
            >
              <Download className="mr-2 h-4 w-4" />
              Export JSON
            </Button>
          ) : null
        }
      />

      <form onSubmit={submit} className="panel grid gap-4 p-4 md:grid-cols-[1fr_1fr_auto]">
        <RunSelect
          label="Baseline run"
          value={baseline}
          onChange={setBaseline}
          runs={runs.data?.items ?? []}
        />
        <RunSelect
          label="Candidate run"
          value={candidate}
          onChange={setCandidate}
          runs={runs.data?.items ?? []}
        />
        <Button type="submit" className="self-end" disabled={comparison.isPending || !baseline || !candidate}>
          Compare
        </Button>
      </form>

      {runs.isLoading ? <LoadingSkeleton rows={2} /> : null}
      {runs.isError ? <ErrorState title="Run list failed" error={runs.error} /> : null}
      {comparison.isError ? <ErrorState error={comparison.error} /> : null}

      {!comparison.data && !comparison.isError ? (
        <EmptyState title="No comparison loaded" detail="Select two runs to inspect reliability differences." />
      ) : null}

      {comparison.data ? (
        <section className="panel p-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-sm font-semibold">Comparison result</h2>
              <p className="metadata mt-1 text-muted-foreground">
                Baseline {comparison.data.comparison.baseline_run_id} vs candidate{" "}
                {comparison.data.comparison.candidate_run_id}
              </p>
            </div>
          </div>
          <div className="mt-4 overflow-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="border-b text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-2">Metric</th>
                  <th>Baseline</th>
                  <th>Candidate</th>
                  <th>Delta</th>
                  <th>Percent</th>
                  <th>Assessment</th>
                </tr>
              </thead>
              <tbody>
                {orderedDifferences(comparison.data.comparison).map(([key, diff]) => (
                  <tr key={key} className="border-b last:border-b-0">
                    <td className="py-3 font-medium">{metricLabel(key)}</td>
                    <td className="metadata">{formatComparisonValue(key, diff.before)}</td>
                    <td className="metadata">{formatComparisonValue(key, diff.after)}</td>
                    <td className="metadata">{formatDelta(key, diff.absolute_difference)}</td>
                    <td className="metadata">{formatPercentDelta(diff.percentage_difference)}</td>
                    <td>
                      <span
                        className={`inline-flex rounded-md border px-2 py-1 text-xs font-semibold ${comparisonClassName(
                          diff.change_kind,
                        )}`}
                      >
                        {comparisonBadge(diff.change_kind)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function RunSelect({
  label,
  value,
  onChange,
  runs,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  runs: Array<{ id: string; scenario_id: string; state: string }>;
}) {
  return (
    <label className="text-sm">
      <span className="font-medium">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-md border bg-white px-3 py-2 metadata"
        required
      >
        <option value="">Select a run</option>
        {runs.map((run) => (
          <option key={run.id} value={run.id}>
            {run.scenario_id} / {run.id} / {run.state}
          </option>
        ))}
      </select>
      {value ? (
        <div className="mt-2">
          <RunStatusBadge state={runs.find((run) => run.id === value)?.state ?? "unknown"} />
        </div>
      ) : null}
    </label>
  );
}
