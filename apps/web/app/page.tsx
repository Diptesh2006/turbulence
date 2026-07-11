"use client";

import { Activity, RadioTower } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { HealthCard } from "@/components/health-card";
import { getHealth } from "@/lib/api";

export default function Home() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 10_000,
  });

  return (
    <main className="min-h-screen bg-background">
      <section className="border-b bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <RadioTower className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-normal">Turbulence</h1>
              <p className="text-sm text-muted-foreground">AI Flight Simulator cockpit</p>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
            <Activity className="h-4 w-4 text-primary" aria-hidden="true" />
            <span>Backend health</span>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[1fr_320px]">
        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Pre-flight systems</h2>
              <p className="text-sm text-muted-foreground">
                Simulation engine pending. Health telemetry is live.
              </p>
            </div>
          </div>
          <HealthCard query={healthQuery} />
        </div>

        <aside className="rounded-lg border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-normal text-muted-foreground">
            Current scope
          </h2>
          <div className="mt-4 space-y-3 text-sm">
            <p>REST commands and Server-Sent Events are reserved for the simulator layer.</p>
            <p>Provider routing and failure reports are not generated in this scaffold.</p>
          </div>
        </aside>
      </section>
    </main>
  );
}

