"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  createRunFromScenario,
  createScenario,
  getIntegrationStatus,
  getScenarios,
  type Scenario,
} from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingSkeleton } from "@/components/states";
import { cloneScenario, validateScenarioBuilder } from "./builder";

export default function NewSimulationPage() {
  const router = useRouter();
  const concentrateStatus = useQuery({
    queryKey: ["concentrate-status"],
    queryFn: getIntegrationStatus,
  });
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: getScenarios });
  const presets = scenarios.data?.items.filter((scenario) => scenario.id.startsWith("preset-")) ?? [];
  const [draft, setDraft] = useState<Scenario | null>(null);
  const backendLive = concentrateStatus.data?.mode === "live" && concentrateStatus.data?.is_mock === false;
  const liveConfigured = concentrateStatus.data?.configured === true;
  const validation = useMemo(
    () => (draft ? validateScenarioBuilder(draft, backendLive, liveConfigured) : null),
    [draft, backendLive, liveConfigured],
  );

  const saveAndLaunch = useMutation({
    mutationFn: async () => {
      if (!draft) throw new Error("Select a preset before launching.");
      const saved = await createScenario(draft);
      const run = await createRunFromScenario(saved.scenario.id);
      return run.run;
    },
    onSuccess: (run) => router.push(`/runs/${run.id}`),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft || validation?.errors.length) return;
    saveAndLaunch.mutate();
  }

  return (
    <div>
      <PageHeader
        eyebrow="Simulation setup"
        title="Scenario builder"
        description="Configure deterministic traffic, routing, faults, and SLOs. Native routing delegates to Concentrate; deterministic chaos uses Turbulence-managed fallback and simulated faults."
      />

      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <section className="space-y-4">
          <BuilderSection title="1. Workload">
            {scenarios.isLoading ? <LoadingSkeleton rows={2} /> : null}
            {scenarios.isError ? <ErrorState error={scenarios.error} /> : null}
            <div className="grid gap-4 md:grid-cols-3">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => setDraft(cloneScenario(preset, "custom"))}
                  className="panel p-4 text-left hover:border-primary focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold">{preset.id}</h3>
                      <p className="metadata mt-1 text-muted-foreground">{preset.mode}</p>
                    </div>
                    <span className="rounded-md border bg-muted px-2 py-1 text-xs">preset</span>
                  </div>
                  <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <dt className="text-muted-foreground">Requests</dt>
                      <dd className="font-medium">{preset.request_count}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Routing</dt>
                      <dd className="font-medium">{preset.routing_profile.type}</dd>
                    </div>
                  </dl>
                </button>
              ))}
            </div>
            </BuilderSection>

          <form onSubmit={submit} className="space-y-4">
            <BuilderSection title="2. Execution mode">
              <div className="grid gap-3 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => updateDraft(setDraft, { mode: "mock" })}
                  className={`rounded-md border p-4 text-left ${
                    draft?.mode === "mock" ? "border-primary bg-muted" : "bg-white"
                  }`}
                >
                  <div className="font-semibold">Mock deterministic mode</div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Safe local execution. Uses deterministic mock responses and consumes no credits.
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => updateDraft(setDraft, { mode: "concentrate_native" })}
                  className={`rounded-md border p-4 text-left ${
                    draft?.mode === "concentrate_native" ? "border-primary bg-muted" : "bg-white"
                  }`}
                >
                  <div className="font-semibold">Live Concentrate mode</div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Real Concentrate API calls. Provider credits may be consumed; API keys never leave the backend.
                  </p>
                  <p className="metadata mt-2 text-xs text-muted-foreground">
                    Status: {concentrateStatus.data?.mode ?? "unknown"} /{" "}
                    {concentrateStatus.data?.configured ? "configured" : "not configured"}
                  </p>
                </button>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() => applyLiveSmokeDefaults(setDraft)}
                disabled={!draft}
              >
                Use 1-request live smoke settings
              </Button>
            </BuilderSection>

            <BuilderSection title="3. Traffic">
              <div className="grid gap-3 md:grid-cols-4">
                <NumberField label="Requests" value={draft?.request_count} onChange={(v) => updateDraft(setDraft, { request_count: v })} />
                <NumberField label="Concurrency" value={draft?.max_concurrency} onChange={(v) => updateDraft(setDraft, { max_concurrency: v })} />
                <NumberField label="Rate / sec" value={draft?.rate_per_second} onChange={(v) => updateDraft(setDraft, { rate_per_second: v })} />
                <NumberField label="Seed" value={draft?.seed} onChange={(v) => updateDraft(setDraft, { seed: v })} />
              </div>
              <Button type="button" variant="outline" onClick={() => updateDraft(setDraft, { seed: Math.floor(Math.random() * 1_000_000) })}>
                Generate seed
              </Button>
            </BuilderSection>

            <BuilderSection title="4. Routing">
              <p className="text-sm text-muted-foreground">
                {draft?.mode === "concentrate_native"
                  ? "Native mode sends model=auto and does not claim a selected provider unless Concentrate returns one."
                  : "Deterministic chaos mode advances through configured routes after explicit real or simulated failures."}
              </p>
              <pre className="mt-3 overflow-auto rounded-md bg-muted p-3 text-xs">
                {JSON.stringify(draft?.routing_profile ?? {}, null, 2)}
              </pre>
            </BuilderSection>

            <BuilderSection title="5. Fault schedule">
              <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">
                {JSON.stringify(draft?.fault_rules ?? [], null, 2)}
              </pre>
            </BuilderSection>

            <BuilderSection title="6. SLOs">
              <div className="grid gap-3 md:grid-cols-2">
                <NumberField label="Recovery SLO ms" value={draft?.recovery_time_slo_ms ?? undefined} onChange={(v) => updateDraft(setDraft, { recovery_time_slo_ms: v })} />
                <NumberField label="Latency SLO ms" value={draft?.latency_slo_ms ?? undefined} onChange={(v) => updateDraft(setDraft, { latency_slo_ms: v })} />
              </div>
            </BuilderSection>

            <BuilderSection title="7. Review and launch">
              <div className="grid gap-3 text-sm md:grid-cols-3">
                <ReviewItem label="Estimated duration" value={validation ? `${(validation.estimatedDurationMs / 1000).toFixed(1)}s` : "N/A"} />
                <ReviewItem label="Maximum gateway calls" value={validation?.maxGatewayCalls ?? "N/A"} />
                <ReviewItem label="Mode" value={draft?.mode ?? "N/A"} />
              </div>
              {validation?.warnings.map((warning) => (
                <div key={warning} className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  {warning} No dollar estimate is shown because costs depend on provider responses.
                </div>
              ))}
              {validation?.errors.map((error) => (
                <div key={error} className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900">
                  {error}
                </div>
              ))}
              {saveAndLaunch.isError ? <ErrorState error={saveAndLaunch.error} /> : null}
              <Button type="submit" disabled={!draft || Boolean(validation?.errors.length) || saveAndLaunch.isPending}>
                Save scenario and create run
              </Button>
            </BuilderSection>
          </form>
        </section>

        <aside className="panel p-4">
          <h2 className="font-semibold">Current draft</h2>
          <pre className="mt-4 max-h-[44rem] overflow-auto rounded-md bg-muted p-3 text-xs">
            {JSON.stringify(draft ?? { status: "Select a preset to begin" }, null, 2)}
          </pre>
        </aside>
      </div>
    </div>
  );
}

function BuilderSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel p-4">
      <h2 className="font-semibold">{title}</h2>
      <div className="mt-4 space-y-3">{children}</div>
    </section>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | undefined;
  onChange: (value: number) => void;
}) {
  return (
    <label className="text-sm">
      <span className="font-medium">{label}</span>
      <input
        type="number"
        value={value ?? ""}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-2 w-full rounded-md border bg-white px-3 py-2 metadata"
      />
    </label>
  );
}

function ReviewItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="metadata mt-1 font-semibold">{value}</div>
    </div>
  );
}

function updateDraft(
  setDraft: (updater: (draft: Scenario | null) => Scenario | null) => void,
  patch: Partial<Scenario>,
) {
  setDraft((draft) => (draft ? { ...draft, ...patch } : draft));
}

function applyLiveSmokeDefaults(
  setDraft: (updater: (draft: Scenario | null) => Scenario | null) => void,
) {
  setDraft((draft) =>
    draft
      ? {
          ...draft,
          mode: "concentrate_native",
          request_count: 1,
          max_concurrency: 1,
          rate_per_second: 1,
          fault_rules: [],
          routing_profile: {
            id: `${draft.id}-live-gateway-auto`,
            type: "gateway_auto",
            routes: [],
            metric: "performance",
          },
          model: "auto",
        }
      : draft,
  );
}
