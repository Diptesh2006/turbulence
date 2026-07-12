"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  getRun,
  startRun,
  cancelRun,
  Run,
  RequestRecord,
  AttemptRecord,
} from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { RunStatusBadge } from "@/components/status";
import { LoadingSkeleton, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import {
  cockpitReducer,
  SimulationEvent,
  formatScenarioName,
  SseStatus,
  CockpitState,
  getCockpitActionState,
  getSourceBadgeLabel,
  buildRunEventsUrl,
} from "./cockpit-reducer";
import { computeMetrics, DerivedMetrics } from "./cockpit-metrics";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  Play,
  StopCircle,
  Clock,
  Database,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  Eye,
  Server,
  Coins,
  ShieldAlert,
  FileText,
} from "lucide-react";

const eventTypes = [
  "run.created",
  "run.started",
  "request.queued",
  "attempt.started",
  "fault.activated",
  "fault.injected",
  "gateway.response_received",
  "validation.passed",
  "validation.failed",
  "fallback.started",
  "attempt.completed",
  "request.completed",
  "metrics.updated",
  "fault.cleared",
  "run.completed",
  "run.failed",
  "run.cancelled",
];

const COLORS = ["#0ea5e9", "#10b981", "#f59e0b", "#6366f1", "#ec4899", "#8b5cf6"];

export default function RunCockpitPage({ params }: { params: { id: string } }) {
  const [state, dispatch] = useReducer(cockpitReducer, {
    run: null,
    events: [],
    eventsBySeq: {},
    activeFaults: [],
    sseStatus: "connecting" as SseStatus,
    actionError: null,
    lastSequence: null,
  });

  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [expandedEventSeq, setExpandedEventSeq] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const lastSequenceRef = useRef<number | null>(null);

  useEffect(() => {
    lastSequenceRef.current = state.lastSequence;
  }, [state.lastSequence]);

  // Fetch initial state via REST
  const runQuery = useQuery({
    queryKey: ["run", params.id],
    queryFn: () => getRun(params.id),
    refetchOnWindowFocus: false,
  });

  // Initialize with REST data once loaded
  useEffect(() => {
    if (runQuery.data?.run) {
      dispatch({ type: "INIT", run: runQuery.data.run });
    }
  }, [runQuery.data]);

  // Connect to SSE stream
  useEffect(() => {
    if (!params.id) return;

    let es: EventSource | null = null;
    let isCancelled = false;

    const handleEvent = (e: MessageEvent) => {
      if (isCancelled) return;
      try {
        const data = JSON.parse(e.data) as SimulationEvent;
        lastSequenceRef.current =
          lastSequenceRef.current === null
            ? data.sequence
            : Math.max(lastSequenceRef.current, data.sequence);
        dispatch({ type: "ADD_EVENT", event: data });

        if (["run.completed", "run.failed", "run.cancelled"].includes(e.type)) {
          es?.close();
          dispatch({ type: "SET_SSE_STATUS", status: "closed" });
        }
      } catch (err) {
        console.error("Error parsing SSE event:", err);
      }
    };

    const connectSSE = () => {
      if (isCancelled) return;

      dispatch({ type: "SET_SSE_STATUS", status: "connecting" });
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
      es = new EventSource(buildRunEventsUrl(apiBaseUrl, params.id, lastSequenceRef.current));

      es.onopen = () => {
        if (isCancelled) return;
        dispatch({ type: "SET_SSE_STATUS", status: "connected" });
      };

      es.onerror = () => {
        if (isCancelled) return;
        if (es?.readyState === EventSource.CONNECTING) {
          dispatch({ type: "SET_SSE_STATUS", status: "reconnecting" });
        } else {
          dispatch({ type: "SET_SSE_STATUS", status: "error" });
        }
      };

      eventTypes.forEach((type) => {
        es?.addEventListener(type, handleEvent);
      });
    };

    connectSSE();

    return () => {
      isCancelled = true;
      if (es) {
        eventTypes.forEach((type) => {
          es?.removeEventListener(type, handleEvent);
        });
        es.close();
      }
    };
  }, [params.id]);

  // Elapsed Timer effect
  useEffect(() => {
    const isRunning = state.run?.state === "running" || state.run?.state === "cancelling";
    if (!isRunning) {
      if (state.run?.created_at && state.run?.updated_at) {
        const start = new Date(state.run.created_at).getTime();
        const end = new Date(state.run.updated_at).getTime();
        setElapsedSeconds(Math.max(0, Math.floor((end - start) / 1000)));
      }
      return;
    }

    const interval = setInterval(() => {
      if (state.run?.created_at) {
        const start = new Date(state.run.created_at).getTime();
        setElapsedSeconds(Math.max(0, Math.floor((Date.now() - start) / 1000)));
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [state.run?.state, state.run?.created_at, state.run?.updated_at]);

  const handleStart = async () => {
    try {
      dispatch({ type: "SET_ACTION_ERROR", error: null });
      await startRun(params.id);
    } catch (err: any) {
      dispatch({ type: "SET_ACTION_ERROR", error: err.message || "Failed to start run" });
    }
  };

  const handleCancel = async () => {
    try {
      dispatch({ type: "SET_ACTION_ERROR", error: null });
      await cancelRun(params.id);
    } catch (err: any) {
      dispatch({ type: "SET_ACTION_ERROR", error: err.message || "Failed to cancel run" });
    }
  };

  if (runQuery.isLoading) {
    return <LoadingSkeleton />;
  }

  if (runQuery.isError) {
    return <ErrorState error={runQuery.error} />;
  }

  const run = state.run;
  if (!run) return null;

  const cockpitActions = getCockpitActionState(run);

  // Calculate live metrics on client
  const metrics: DerivedMetrics = computeMetrics(run, state.events);

  // Auto-select first request if none selected
  const requests = run.requests || [];
  const selectedRequest = requests.find((r) => r.id === selectedRequestId) || requests[0] || null;

  // Format elapsed time (mm:ss)
  const formatElapsed = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  // Source Badge mapping
  const renderSourceBadge = (source: "real" | "simulated" | "system" | "mock") => {
    const label = getSourceBadgeLabel(source);
    let badgeColor = "border-zinc-200 bg-zinc-50 text-zinc-700";
    if (label === "REAL") badgeColor = "border-emerald-200 bg-emerald-50 text-emerald-800";
    else if (label === "SIMULATED") badgeColor = "border-sky-200 bg-sky-50 text-sky-800";
    else if (label === "MOCK") badgeColor = "border-amber-200 bg-amber-50 text-amber-800";
    else if (label === "SYSTEM") badgeColor = "border-zinc-200 bg-zinc-50 text-zinc-700";

    return (
      <span className={`inline-flex rounded border px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase ${badgeColor}`}>
        {label}
      </span>
    );
  };

  // Recharts latency data preparation
  const latencyChartData = requests
    .filter((r) => r.state === "completed" || r.state === "failed")
    .map((r) => {
      const mainAttempt = r.attempts?.[0];
      const upstream = mainAttempt?.upstream_latency_ms || 0;
      const injected = mainAttempt?.injected_latency_ms || 0;
      return {
        id: r.id.replace(`req-${run.id}-`, ""),
        latency: upstream + injected,
        upstream,
        injected,
      };
    });

  // Recharts success data preparation
  const successChartData = [
    { name: "Successful", count: metrics.successful_requests, fill: "#10b981" },
    { name: "Failed", count: metrics.failed_requests, fill: "#ef4444" },
    { name: "Abandoned", count: run.metrics?.abandoned_requests || 0, fill: "#71717a" },
  ];

  // Recharts provider/model distribution data preparation
  const providerChartData = Object.entries(metrics.requests_by_actual_model_provider).map(
    ([key, value]) => ({
      name: key,
      value,
    })
  );

  // Recharts cumulative cost data preparation
  let runningCost = 0;
  const costChartData = requests
    .flatMap((r) => r.attempts || [])
    .filter((a) => a.state === "completed" || a.state === "failed")
    .map((a, idx) => {
      if (a.cost_total !== null && a.cost_total !== undefined) {
        runningCost += a.cost_total;
      }
      return {
        attempt: idx + 1,
        cost: runningCost,
      };
    });

  // Find routing status indicators for the selected request
  const routingProfile = run.scenario.routing_profile;
  const isResilientRoute = routingProfile.type === "resilient_route";

  return (
    <div className="space-y-6">
      {/* Flight Cockpit Title and Header */}
      <PageHeader
        eyebrow="Simulation Cockpit"
        title={formatScenarioName(run.scenario.id)}
        description={`Run ID: ${run.id}`}
        action={
          <div className="flex items-center gap-3">
            <SseStatusBadge status={state.sseStatus} />
            <RunStatusBadge state={run.state} />
          </div>
        }
      />

      {/* Action Error Banner */}
      {state.actionError && (
        <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <AlertTriangle className="h-5 w-5 shrink-0 text-red-600" />
          <div>{state.actionError}</div>
        </div>
      )}

      {/* Flight status bar */}
      <section className="panel grid gap-4 p-4 md:grid-cols-3 lg:grid-cols-6 items-center">
        <div>
          <div className="text-xs text-muted-foreground font-medium">Run Status</div>
          <div className="metadata mt-1 text-sm font-semibold truncate" title={run.state}>
            {run.state}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground font-medium">Scenario ID</div>
          <div className="metadata mt-1 text-sm font-semibold truncate" title={run.scenario.id}>
            {run.scenario.id}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground font-medium">Workload</div>
          <div className="metadata mt-1 text-sm font-semibold truncate">
            {run.scenario.workload_name}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground font-medium">Routing Type</div>
          <div className="metadata mt-1 text-sm font-semibold truncate capitalize">
            {run.scenario.routing_profile.type.replace("_", " ")}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground font-medium">Random Seed</div>
          <div className="metadata mt-1 text-sm font-semibold">{run.scenario.seed}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground font-medium">Elapsed Time</div>
          <div className="metadata mt-1 text-sm font-semibold flex items-center gap-1.5 text-primary">
            <Clock className="h-3.5 w-3.5" />
            {formatElapsed(elapsedSeconds)}
          </div>
        </div>
        <div className="flex items-center justify-end gap-2">
          {cockpitActions.canStart && (
            <Button
              onClick={handleStart}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white flex items-center gap-1.5"
            >
              <Play className="h-4 w-4" /> Start Run
            </Button>
          )}
          {cockpitActions.canCancel && (
            <Button
              onClick={handleCancel}
              variant="outline"
              disabled={!cockpitActions.canCancel}
              className="w-full border-red-200 hover:bg-red-50 text-red-600 flex items-center gap-1.5"
            >
              <StopCircle className="h-4 w-4" /> Cancel
            </Button>
          )}
          {run.state !== "created" && run.state !== "running" && (
            <div className="text-xs text-muted-foreground text-right w-full">Run Completed</div>
          )}
        </div>
      </section>

      {/* Active Incident Banner */}
      {state.activeFaults.length > 0 && (
        <div className="space-y-2">
          {state.activeFaults.map((fault) => {
            const rule = run.scenario.fault_rules.find((r) => r.id === fault.ruleId);
            const durationSec = rule ? rule.duration_ms / 1000 : 0;
            const startSec = rule ? rule.start_after_ms / 1000 : 0;
            const remainingSec = rule ? Math.max(0, durationSec - Math.max(0, elapsedSeconds - startSec)) : 0;
            
            return (
              <div
                key={fault.ruleId}
                className="flex flex-col md:flex-row md:items-center justify-between gap-3 border border-sky-300 bg-sky-50 rounded-md p-4 text-sky-900 shadow-sm"
              >
                <div className="flex items-start gap-3">
                  <ShieldAlert className="h-5 w-5 shrink-0 text-sky-600 mt-0.5" />
                  <div>
                    <div className="font-semibold flex items-center gap-2">
                      Active Chaos Fault Injected: {fault.type.replace("_", " ")}
                      {renderSourceBadge("simulated")}
                    </div>
                    <div className="text-xs mt-1 text-sky-800">
                      {fault.message}
                    </div>
                    <div className="text-[11px] font-mono mt-1 text-sky-700">
                      Target: {fault.targetProvider || "Any provider"} / {fault.targetModel || "Any model"} | 
                      Params: {JSON.stringify(fault.parameters)}
                    </div>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-xs text-sky-700">Remaining Duration</div>
                  <div className="font-mono text-sm font-bold">
                    {remainingSec > 0 ? `${remainingSec.toFixed(1)}s` : "clearing..."}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Live Metrics Grid */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <MetricCard
          label="Availability"
          value={metrics.availability_percentage !== null ? `${metrics.availability_percentage.toFixed(1)}%` : "N/A"}
          detail={`${metrics.successful_requests}/${metrics.total_logical_requests} requests`}
        />
        <MetricCard
          label="p95 Latency"
          value={metrics.p95_end_to_end_latency_ms !== null ? `${(metrics.p95_end_to_end_latency_ms / 1000).toFixed(2)}s` : "N/A"}
          detail={
            metrics.p50_end_to_end_latency_ms !== null
              ? `p50: ${(metrics.p50_end_to_end_latency_ms / 1000).toFixed(2)}s`
              : undefined
          }
        />
        <MetricCard
          label="Correctness"
          value={metrics.overall_correctness_rate !== null ? `${metrics.overall_correctness_rate.toFixed(1)}%` : "N/A"}
          detail={
            metrics.schema_valid_response_rate !== null
              ? `Valid JSON: ${metrics.schema_valid_response_rate.toFixed(0)}%`
              : undefined
          }
        />
        <MetricCard
          label="Fallback Recovery"
          value={metrics.fallback_recovery_rate !== null ? `${metrics.fallback_recovery_rate.toFixed(1)}%` : "N/A"}
          detail={`${metrics.successful_fallback_recoveries}/${metrics.fallback_triggered_requests} triggered`}
        />
        <MetricCard
          label="Cumulative Cost"
          value={metrics.total_cost !== null ? `$${metrics.total_cost.toFixed(4)}` : "N/A"}
          detail={
            metrics.cost_per_successful_request !== null
              ? `Avg/req: $${metrics.cost_per_successful_request.toFixed(4)}`
              : "mock mode"
          }
        />
        <MetricCard
          label="Resilience Score"
          value={metrics.resilience_score.score !== null ? `${metrics.resilience_score.score.toFixed(0)}/100` : "N/A"}
          detail={`${metrics.resilience_score.components.filter(c => !c.excluded).length}/5 score factors`}
        />
      </section>

      {/* Main Grid: Cockpit Telemetry */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Side: Route maps, Charts, Requests, Timeline (span 2) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Configured Route Map Widget */}
          <section className="panel p-4">
            <h3 className="font-semibold text-sm border-b pb-2 flex items-center justify-between">
              <span>Routing Topology & Current Path Status</span>
              {renderSourceBadge(isResilientRoute ? "simulated" : "system")}
            </h3>
            {selectedRequest ? (
              <div className="mt-4">
                <div className="text-xs text-muted-foreground mb-3 flex items-center justify-between">
                  <span>
                    Selected Request: <strong className="font-mono text-primary">{selectedRequest.id}</strong>
                  </span>
                  <span>
                    Fixture ID: <strong className="font-mono">{selectedRequest.fixture_id}</strong>
                  </span>
                </div>

                {isResilientRoute ? (
                  <div className="flex flex-col space-y-4">
                    <div className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">
                      Simulator-Managed Fallback Chain
                    </div>
                    <div className="relative flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 py-2">
                      {routingProfile.routes.map((route, idx) => {
                        const attempt = selectedRequest.attempts?.find((a) => a.index === idx);
                        const isAttempted = !!attempt;
                        const isSuccess = attempt?.validation_passed === true;
                        const isRunning = attempt?.state === "started";
                        const isFailed =
                          attempt?.state === "failed" ||
                          attempt?.state === "blocked" ||
                          attempt?.validation_passed === false;

                        let cardStyle = "border-zinc-200 bg-zinc-50 text-zinc-500";
                        let statusText = "Muted / Bypassed";

                        if (isRunning) {
                          cardStyle = "border-sky-300 bg-sky-50 text-sky-800 shadow-sm ring-1 ring-sky-400";
                          statusText = "Active / Evaluating";
                        } else if (isSuccess) {
                          cardStyle = "border-emerald-300 bg-emerald-50 text-emerald-800 shadow-sm";
                          statusText = "Route Completed";
                        } else if (isFailed) {
                          cardStyle = "border-red-300 bg-red-50 text-red-800 shadow-sm";
                          statusText = `Failed / Blocked (${attempt.simulated_status_code || "Score Fail"})`;
                        }

                        return (
                          <div
                            key={idx}
                            className={`flex-1 border rounded-md p-3 text-xs flex flex-col justify-between min-h-20 transition-all ${cardStyle}`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-semibold uppercase tracking-wider text-[9px] text-muted-foreground">
                                Route {idx + 1} {idx === 0 ? "(Primary)" : "(Fallback)"}
                              </span>
                              {isRunning && (
                                <span className="h-2 w-2 rounded-full bg-sky-500 animate-ping" />
                              )}
                            </div>
                            <div className="font-mono text-sm mt-1.5 font-bold truncate">
                              {route.provider}/{route.model}
                            </div>
                            {isAttempted && (
                              <div className="mt-2 text-[10px] flex items-center justify-between font-mono">
                                <span>{statusText}</span>
                                <span>{(attempt.upstream_latency_ms || 0).toFixed(0)}ms</span>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : routingProfile.type === "gateway_auto" ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50/50 p-4 text-xs">
                    <div className="font-semibold text-amber-900 flex items-center gap-1.5">
                      <Server className="h-4 w-4 text-amber-600" />
                      Concentrate Native Auto Routing (Metric: {routingProfile.metric})
                    </div>
                    <p className="mt-1 text-amber-800">
                      Provider and model selection is dynamically negotiated by Concentrate AI.
                    </p>
                    {selectedRequest.attempts?.[0] && (
                      <div className="mt-3 flex items-center justify-between border-t border-amber-200/50 pt-2 font-mono">
                        <div>
                          <span>Actual Selected model: </span>
                          <strong className="text-amber-900">
                            {selectedRequest.attempts[0].actual_model ||
                              selectedRequest.attempts[0].model}
                          </strong>
                        </div>
                        <div>
                          <span>Provider: </span>
                          <strong className="text-amber-900 capitalize">
                            {selectedRequest.attempts[0].actual_provider || "mock"}
                          </strong>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="rounded-md border border-zinc-200 bg-zinc-50 p-4 text-xs font-mono flex items-center justify-between">
                    <div>
                      <span>Brittle Single Route Target: </span>
                      <strong>
                        {routingProfile.routes[0]?.provider}/{routingProfile.routes[0]?.model}
                      </strong>
                    </div>
                    <div>
                      <span>Status: </span>
                      <strong className="capitalize text-primary">
                        {selectedRequest.state}
                      </strong>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-muted-foreground mt-4 text-center">
                No active requests selected. Stored scenario topology requires run telemetry.
              </div>
            )}
          </section>

          {/* Charts section */}
          <section className="panel p-4 space-y-4">
            <h3 className="font-semibold text-sm border-b pb-2">Telemetry Visualization</h3>

            {latencyChartData.length > 0 ? (
              <div className="grid gap-6 md:grid-cols-2">
                {/* Latency Chart */}
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground font-semibold">
                    Request Latency Over Time (ms)
                  </div>
                  <div className="h-48 mt-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={latencyChartData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="id" tick={{ fontSize: 9 }} />
                        <YAxis tick={{ fontSize: 9 }} />
                        <Tooltip contentStyle={{ fontSize: 10 }} />
                        <Area
                          type="monotone"
                          dataKey="latency"
                          name="Total Latency"
                          stroke="#0ea5e9"
                          fill="#e0f2fe"
                          strokeWidth={2}
                        />
                        <Area
                          type="monotone"
                          dataKey="injected"
                          name="Injected Latency"
                          stroke="#f59e0b"
                          fill="#fef3c7"
                          strokeWidth={1}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Status Bar Chart */}
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground font-semibold">
                    Requests Success vs Failure Count
                  </div>
                  <div className="h-48 mt-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={successChartData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                        <YAxis tick={{ fontSize: 9 }} />
                        <Tooltip contentStyle={{ fontSize: 10 }} />
                        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                          {successChartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Provider Distribution Chart */}
                {providerChartData.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground font-semibold">
                      Returned Model & Provider Distribution
                    </div>
                    <div className="h-48 mt-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={providerChartData}
                            cx="50%"
                            cy="50%"
                            innerRadius={40}
                            outerRadius={65}
                            paddingAngle={2}
                            dataKey="value"
                          >
                            {providerChartData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip contentStyle={{ fontSize: 10 }} />
                          <Legend wrapperStyle={{ fontSize: 9 }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {/* Cumulative Cost Chart */}
                {metrics.total_cost !== null && costChartData.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground font-semibold">
                      Cumulative Workload Run Cost ($)
                    </div>
                    <div className="h-48 mt-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={costChartData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="attempt" tick={{ fontSize: 9 }} />
                          <YAxis tick={{ fontSize: 9 }} />
                          <Tooltip contentStyle={{ fontSize: 10 }} />
                          <Area
                            type="monotone"
                            dataKey="cost"
                            name="Cost ($)"
                            stroke="#8b5cf6"
                            fill="#f3e8ff"
                            strokeWidth={2}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-muted-foreground py-8 text-center">
                Waiting for simulation execution telemetry to populate charts.
              </div>
            )}
          </section>

          {/* Stored requests list */}
          <section className="panel overflow-hidden">
            <div className="border-b p-4 font-semibold text-sm flex items-center justify-between">
              <span>Logical Workload Requests</span>
              <span className="metadata text-[10px] text-muted-foreground">
                Total Queue: {requests.length}
              </span>
            </div>
            {requests.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b bg-muted/50 font-medium text-muted-foreground uppercase tracking-wider text-[9px]">
                      <th className="p-3">Request ID</th>
                      <th className="p-3">Fixture</th>
                      <th className="p-3">Attempts</th>
                      <th className="p-3">State</th>
                      <th className="p-3">Validation Outcome</th>
                      <th className="p-3 text-right">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y font-mono">
                    {requests.map((request) => {
                      const isSelected = request.id === selectedRequestId;
                      const hasFailedAttempts = (request.attempts || []).some(
                        (a) => a.state === "failed" || a.state === "blocked"
                      );
                      const isCompleted = request.state === "completed";
                      const isFailed = request.state === "failed";

                      let stateColor = "text-zinc-500";
                      if (isCompleted) stateColor = "text-emerald-600";
                      else if (isFailed) stateColor = "text-red-600";
                      else if (request.state === "running") stateColor = "text-sky-600 font-bold";

                      const score = request.validation_result?.score;

                      return (
                        <tr
                          key={request.id}
                          className={`hover:bg-muted/30 transition-colors ${isSelected ? "bg-muted/40" : ""}`}
                        >
                          <td className="p-3 font-semibold text-primary">{request.id}</td>
                          <td className="p-3">{request.fixture_id}</td>
                          <td className="p-3 flex items-center gap-1.5">
                            <span>{(request.attempts || []).length}</span>
                            {hasFailedAttempts && (
                              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" aria-label="Fallback Triggered" />
                            )}
                          </td>
                          <td className={`p-3 capitalize ${stateColor}`}>{request.state}</td>
                          <td className="p-3">
                            {score ? (
                              <span
                                className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-bold ${score.overall_correct ? "bg-emerald-50 text-emerald-700 border border-emerald-100" : "bg-red-50 text-red-700 border border-red-100"}`}
                              >
                                {score.overall_correct ? "Passed" : "Failed"}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </td>
                          <td className="p-3 text-right">
                            <Button
                              onClick={() => setSelectedRequestId(request.id)}
                              variant="outline"
                              className="h-7 w-7 p-0 hover:bg-muted"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground p-8 text-center">
                Start the run to populate request items.
              </div>
            )}
          </section>

          {/* Event Timeline */}
          <section className="panel overflow-hidden">
            <div className="border-b p-4 font-semibold text-sm flex items-center justify-between">
              <span>Event Stream Timeline Telemetry</span>
              <span className="metadata text-[10px] text-muted-foreground">
                Total Events: {state.events.length}
              </span>
            </div>
            {state.events.length > 0 ? (
              <div className="divide-y max-h-[30rem] overflow-y-auto">
                {[...state.events]
                  .sort((a, b) => b.sequence - a.sequence)
                  .map((event) => {
                    const isExpanded = expandedEventSeq === event.sequence;
                    const eventTime = new Date(event.timestamp).toLocaleTimeString();
                    const reqId = event.payload?.request_id;
                    const model = event.payload?.model;

                    return (
                      <div key={event.sequence} className="p-3 text-xs hover:bg-muted/10">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="metadata font-mono font-bold text-zinc-400 bg-zinc-100 rounded px-1 text-[10px]">
                              #{event.sequence.toString().padStart(3, "0")}
                            </span>
                            <span className="font-mono text-zinc-500 text-[10px]">{eventTime}</span>
                            <span className="font-semibold text-zinc-800">{event.type}</span>
                            {renderSourceBadge(event.source)}
                          </div>
                          <Button
                            onClick={() =>
                              setExpandedEventSeq(isExpanded ? null : event.sequence)
                            }
                            variant="outline"
                            className="h-6 px-1.5 text-[10px] font-medium"
                          >
                            {isExpanded ? "Hide Payload" : "Show Payload"}
                          </Button>
                        </div>

                        <div className="mt-1 text-muted-foreground font-mono text-[11px] flex flex-wrap gap-x-4 gap-y-1">
                          {typeof reqId === "string" && (
                            <div>
                              Req: <strong className="text-zinc-600">{reqId}</strong>
                            </div>
                          )}
                          {typeof model === "string" && (
                            <div>
                              Model: <strong className="text-zinc-600">{model}</strong>
                            </div>
                          )}
                          {typeof event.payload?.message === "string" && (
                            <div className="text-primary italic font-sans text-xs">
                              {event.payload.message}
                            </div>
                          )}
                        </div>

                        {isExpanded && (
                          <pre className="mt-2 overflow-auto rounded bg-muted p-2.5 text-[10px] font-mono text-zinc-700">
                            {JSON.stringify(event.payload, null, 2)}
                          </pre>
                        )}
                      </div>
                    );
                  })}
              </div>
            ) : (
              <div className="text-xs text-muted-foreground p-8 text-center">
                Waiting for events to stream...
              </div>
            )}
          </section>
        </div>

        {/* Right Column: Request Inspector (span 1) */}
        <div className="space-y-6">
          <section className="panel p-4 space-y-4">
            <h3 className="font-semibold text-sm border-b pb-2 flex items-center justify-between">
              <span>Logical Request Inspector</span>
              <Database className="h-4 w-4 text-muted-foreground" />
            </h3>

            {selectedRequest ? (
              <div className="space-y-4 text-xs font-mono">
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase font-bold">Request ID</div>
                  <div className="text-sm font-bold text-primary mt-0.5">{selectedRequest.id}</div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-[10px] text-muted-foreground uppercase font-bold">Fixture ID</div>
                    <div className="font-semibold text-zinc-800 mt-0.5 truncate" title={selectedRequest.fixture_id}>
                      {selectedRequest.fixture_id}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground uppercase font-bold">Current State</div>
                    <div className="font-semibold text-zinc-800 mt-0.5 capitalize">
                      {selectedRequest.state}
                    </div>
                  </div>
                </div>

                {/* Validation Scores */}
                {selectedRequest.validation_result?.score && (
                  <div className="rounded border bg-zinc-50/50 p-3 space-y-2">
                    <div className="text-[10px] text-muted-foreground uppercase font-bold border-b pb-1">
                      Validation Results
                    </div>
                    <div className="grid grid-cols-2 gap-x-2 gap-y-1.5 text-[11px]">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Schema Valid:</span>
                        <strong className={selectedRequest.validation_result.score.schema_valid ? "text-emerald-600" : "text-red-600"}>
                          {selectedRequest.validation_result.score.schema_valid ? "TRUE" : "FALSE"}
                        </strong>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Category Match:</span>
                        <strong className={selectedRequest.validation_result.score.category_correct ? "text-emerald-600" : "text-red-600"}>
                          {selectedRequest.validation_result.score.category_correct ? "TRUE" : "FALSE"}
                        </strong>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Priority Match:</span>
                        <strong className={selectedRequest.validation_result.score.priority_correct ? "text-emerald-600" : "text-red-600"}>
                          {selectedRequest.validation_result.score.priority_correct ? "TRUE" : "FALSE"}
                        </strong>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Keywords:</span>
                        <strong>
                          {(selectedRequest.validation_result.score.summary_keyword_coverage * 100).toFixed(0)}%
                        </strong>
                      </div>
                    </div>
                  </div>
                )}

                {/* Validation Errors */}
                {selectedRequest.validation_result?.errors && selectedRequest.validation_result.errors.length > 0 && (
                  <div className="rounded border border-red-100 bg-red-50/50 p-3 space-y-1 text-red-900">
                    <div className="text-[10px] uppercase font-bold text-red-700">Validation Failures</div>
                    <ul className="list-disc pl-4 text-[10px] space-y-1">
                      {selectedRequest.validation_result.errors.map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Attempts list */}
                <div className="space-y-3">
                  <div className="text-[10px] text-muted-foreground uppercase font-bold">
                    Route Attempt History
                  </div>

                  {selectedRequest.attempts && selectedRequest.attempts.length > 0 ? (
                    <div className="space-y-4">
                      {selectedRequest.attempts.map((attempt) => {
                        const isSuccess = attempt.validation_passed === true;
                        const isBlocked = attempt.state === "blocked";
                        const isFailed = attempt.state === "failed";
                        const isAbandoned = attempt.state === "abandoned";
                        const isRunning = attempt.state === "started";

                        let attemptBorder = "border-zinc-200 bg-white";
                        let headerBg = "bg-zinc-50 border-b";
                        if (isSuccess) {
                          attemptBorder = "border-emerald-200 bg-emerald-50/10";
                          headerBg = "bg-emerald-50 border-b border-emerald-200";
                        } else if (isFailed || isBlocked) {
                          attemptBorder = "border-red-200 bg-red-50/10";
                          headerBg = "bg-red-50 border-b border-red-200";
                        } else if (isRunning) {
                          attemptBorder = "border-sky-300 bg-sky-50/10 ring-1 ring-sky-300";
                          headerBg = "bg-sky-50 border-b border-sky-300";
                        }

                        // Determine badges to display
                        const runMode = attempt.actual_provider === "mock" || attempt.provider === "mock" ? "MOCK" : "REAL";
                        const isSimulated = attempt.fault_provenance && attempt.fault_provenance.length > 0;

                        return (
                          <div key={attempt.id} className={`rounded border overflow-hidden transition-all ${attemptBorder}`}>
                            {/* Attempt Title Header */}
                            <div className={`p-2.5 flex items-center justify-between text-xs font-semibold ${headerBg}`}>
                              <span className="text-zinc-700">
                                Attempt #{attempt.index + 1}
                              </span>
                              <div className="flex gap-1.5 items-center">
                                {isSimulated && renderSourceBadge("simulated")}
                                {renderSourceBadge(runMode === "MOCK" ? "mock" : "real")}
                                <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] capitalize font-bold ${isSuccess ? "bg-emerald-100 text-emerald-800" : isFailed || isBlocked ? "bg-red-100 text-red-800" : isRunning ? "bg-sky-100 text-sky-800" : "bg-zinc-100 text-zinc-800"}`}>
                                  {attempt.state}
                                </span>
                              </div>
                            </div>

                            {/* Attempt parameters list */}
                            <div className="p-3 space-y-2 text-[11px] divide-y divide-zinc-100">
                              <div className="flex justify-between py-1">
                                <span className="text-muted-foreground">Requested:</span>
                                <strong className="text-zinc-700 font-bold truncate max-w-[12rem]" title={attempt.model}>
                                  {attempt.provider ? `${attempt.provider}/` : ""}{attempt.model}
                                </strong>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-muted-foreground">Actual Result:</span>
                                <strong className="text-zinc-700 font-bold truncate max-w-[12rem]">
                                  {attempt.actual_provider ? `${attempt.actual_provider}/` : ""}
                                  {attempt.actual_model || "N/A"}
                                </strong>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-muted-foreground">Fallback Index:</span>
                                <span>{attempt.simulator_managed_fallback ? "TRUE (Simulator Fallback)" : "FALSE"}</span>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-muted-foreground">HTTP Status:</span>
                                <strong>{attempt.simulated_status_code || attempt.upstream_response_id ? 200 : "Error"}</strong>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-muted-foreground">Latency:</span>
                                <span>
                                  Upstream: <strong>{attempt.upstream_latency_ms != null ? `${attempt.upstream_latency_ms.toFixed(0)}ms` : "N/A"}</strong> | 
                                  Injected: <strong>{attempt.injected_latency_ms}ms</strong>
                                </span>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-muted-foreground">Tokens Budget:</span>
                                <span>
                                  In: <strong>{attempt.input_tokens ?? "N/A"}</strong> | 
                                  Out: <strong>{attempt.output_tokens ?? "N/A"}</strong>
                                </span>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-muted-foreground">Cost:</span>
                                <strong>
                                  {attempt.cost_total !== null && attempt.cost_total !== undefined
                                    ? `$${attempt.cost_total.toFixed(5)}`
                                    : "N/A"}
                                </strong>
                              </div>

                              {/* Errors if any */}
                              {attempt.errors && attempt.errors.length > 0 && (
                                <div className="text-[10px] text-red-700 pt-2 space-y-1 font-mono">
                                  <div className="font-semibold uppercase text-red-800">Errors encountered:</div>
                                  {attempt.errors.map((err, i) => (
                                    <div key={i} className="pl-2 border-l border-red-300">{err}</div>
                                  ))}
                                </div>
                              )}

                              {/* Injected Fault Details */}
                              {attempt.fault_provenance && attempt.fault_provenance.length > 0 && (
                                <div className="text-[10px] pt-2 space-y-2 font-mono">
                                  <div className="font-semibold uppercase text-sky-800 flex items-center gap-1">
                                    <ShieldAlert className="h-3.5 w-3.5" />
                                    Simulated Fault Provenance
                                  </div>
                                  {attempt.fault_provenance.map((prov, i) => (
                                    <div key={i} className="rounded border border-sky-100 bg-sky-50/50 p-2 text-sky-900">
                                      <div className="font-semibold capitalize text-sky-800">
                                        Type: {prov.type.replace("_", " ")}
                                      </div>
                                      <div>Rule ID: {prov.rule_id}</div>
                                      {prov.injected_delay_ms > 0 && (
                                        <div>Injected Delay: {prov.injected_delay_ms}ms</div>
                                      )}
                                      {prov.simulated_status_code && (
                                        <div>Simulated Status: {prov.simulated_status_code}</div>
                                      )}
                                      {prov.corrupted_response && (
                                        <div className="text-amber-700 font-semibold">Response payload corrupted (malformed JSON)</div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground py-2 italic">
                      No attempts registered.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-xs text-muted-foreground py-8 text-center italic">
                Select a request from the list to inspect its attempts, validation logs, and fault injections.
              </div>
            )}
          </section>

          <Link href={`/runs/${params.id}/report`} className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline">
            <FileText className="h-4 w-4" /> Open Full Post-Flight Report
          </Link>
        </div>
      </div>
    </div>
  );
}

function SseStatusBadge({ status }: { status: SseStatus }) {
  const config = {
    connecting: { color: "bg-amber-50 text-amber-800 border-amber-200", text: "Connecting" },
    connected: { color: "bg-emerald-50 text-emerald-800 border-emerald-200", text: "Live Stream" },
    reconnecting: { color: "bg-indigo-50 text-indigo-800 border-indigo-200", text: "Reconnecting" },
    closed: { color: "bg-zinc-50 text-zinc-800 border-zinc-200", text: "Closed" },
    error: { color: "bg-red-50 text-red-800 border-red-200", text: "Stream Error" },
  }[status] || { color: "bg-zinc-50 text-zinc-800 border-zinc-200", text: "Unknown" };

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-bold uppercase tracking-wider ${config.color}`}>
      <span
        className={`h-1.5 w-1.5 rounded-full ${status === "connected" ? "bg-emerald-500 animate-pulse" : status === "connecting" || status === "reconnecting" ? "bg-amber-500 animate-pulse" : "bg-zinc-400"}`}
      />
      {config.text}
    </span>
  );
}
