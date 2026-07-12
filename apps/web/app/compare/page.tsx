"use client";

import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { compareRuns } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/states";

export default function ComparePage() {
  const [baseline, setBaseline] = useState("");
  const [candidate, setCandidate] = useState("");
  const comparison = useMutation({
    mutationFn: () => compareRuns(baseline, candidate),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    comparison.mutate();
  }

  return (
    <div>
      <PageHeader
        eyebrow="Run comparison"
        title="Compare reliability deltas"
        description="Enter two stored run IDs to compare metric snapshots from the backend."
      />

      <form onSubmit={submit} className="panel grid gap-4 p-4 md:grid-cols-[1fr_1fr_auto]">
        <label className="text-sm">
          <span className="font-medium">Baseline run ID</span>
          <input
            value={baseline}
            onChange={(event) => setBaseline(event.target.value)}
            className="mt-2 w-full rounded-md border bg-white px-3 py-2 metadata"
            required
          />
        </label>
        <label className="text-sm">
          <span className="font-medium">Candidate run ID</span>
          <input
            value={candidate}
            onChange={(event) => setCandidate(event.target.value)}
            className="mt-2 w-full rounded-md border bg-white px-3 py-2 metadata"
            required
          />
        </label>
        <Button type="submit" className="self-end" disabled={comparison.isPending}>
          Compare
        </Button>
      </form>

      <section className="mt-6">
        {comparison.isError ? <ErrorState error={comparison.error} /> : null}
        {!comparison.data && !comparison.isError ? (
          <EmptyState title="No comparison loaded" detail="Submit two run IDs to inspect differences." />
        ) : null}
        {comparison.data ? (
          <div className="panel p-4">
            <h2 className="font-semibold">Comparison result</h2>
            <pre className="mt-4 overflow-auto rounded-md bg-muted p-3 text-xs">
              {JSON.stringify(comparison.data.comparison, null, 2)}
            </pre>
          </div>
        ) : null}
      </section>
    </div>
  );
}

