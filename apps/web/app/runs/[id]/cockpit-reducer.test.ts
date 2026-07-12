import { describe, it, expect } from "vitest";
import {
  cockpitReducer,
  reconstructRun,
  formatScenarioName,
  CockpitState,
  SimulationEvent,
  getCockpitActionState,
  getSourceBadgeLabel,
  getTerminalRunLabel,
  buildRunEventsUrl,
} from "./cockpit-reducer";
import { computeMetrics } from "./cockpit-metrics";
import { Run } from "@/lib/api";

const mockScenario = {
  id: "support-triage-resilient",
  mode: "deterministic_chaos" as const,
  workload_name: "support_ticket_triage",
  request_count: 3,
  seed: 42,
  rate_per_second: 1,
  max_concurrency: 2,
  model: "mock-fast",
  max_output_tokens: 128,
  recovery_time_slo_ms: 2000,
  latency_slo_ms: 1000,
  routing_profile: {
    id: "resilient-profile",
    type: "resilient_route" as const,
    routes: [
      { model: "mock-fast", provider: "mock" },
      { model: "mock-slow", provider: "mock" },
    ],
  },
  fault_rules: [
    {
      id: "fault-outage",
      type: "provider_outage" as const,
      start_after_ms: 100,
      duration_ms: 500,
      probability: 1.0,
      enabled: true,
      parameters: {},
    },
  ],
};

const initialRun: Run = {
  id: "run-123",
  scenario: mockScenario,
  state: "created",
  created_at: "2026-07-12T06:00:00Z",
  updated_at: "2026-07-12T06:00:00Z",
  requests: [],
  metrics: {
    total_requests: 3,
    completed_requests: 0,
    failed_requests: 0,
    abandoned_requests: 0,
    passed_validations: 0,
    failed_validations: 0,
  },
  error: null,
};

describe("cockpit-reducer & helpers", () => {
  it("formats scenario name correctly", () => {
    expect(formatScenarioName("support-triage-smoke")).toBe("Support Triage Smoke");
    expect(formatScenarioName("resilient_route_demo")).toBe("Resilient Route Demo");
  });

  it("reconstructs run state from events in sequence", () => {
    const events: SimulationEvent[] = [
      {
        sequence: 1,
        type: "run.created",
        source: "system",
        timestamp: "2026-07-12T06:00:01Z",
        run_id: "run-123",
        payload: { scenario_id: "support-triage-resilient" },
      },
      {
        sequence: 2,
        type: "run.started",
        source: "system",
        timestamp: "2026-07-12T06:00:02Z",
        run_id: "run-123",
        payload: { scenario_id: "support-triage-resilient" },
      },
      {
        sequence: 3,
        type: "request.queued",
        source: "system",
        timestamp: "2026-07-12T06:00:03Z",
        run_id: "run-123",
        payload: { request_id: "req-1", fixture_id: "fix-1" },
      },
    ];

    const { run } = reconstructRun(initialRun, events);
    expect(run.state).toBe("running");
    expect(run.requests).toHaveLength(1);
    expect(run.requests![0].id).toBe("req-1");
    expect(run.requests![0].state).toBe("queued");
  });

  it("handles out-of-order events correctly during reconstruction", () => {
    const events: SimulationEvent[] = [
      {
        sequence: 3,
        type: "request.queued",
        source: "system",
        timestamp: "2026-07-12T06:00:03Z",
        run_id: "run-123",
        payload: { request_id: "req-1", fixture_id: "fix-1" },
      },
      {
        sequence: 1,
        type: "run.created",
        source: "system",
        timestamp: "2026-07-12T06:00:01Z",
        run_id: "run-123",
        payload: { scenario_id: "support-triage-resilient" },
      },
      {
        sequence: 2,
        type: "run.started",
        source: "system",
        timestamp: "2026-07-12T06:00:02Z",
        run_id: "run-123",
        payload: { scenario_id: "support-triage-resilient" },
      },
    ];

    const { run } = reconstructRun(initialRun, events);
    expect(run.state).toBe("running");
    expect(run.requests).toHaveLength(1);
    expect(run.requests![0].id).toBe("req-1");
  });

  it("deduplicates events in the reducer state", () => {
    const initialState: CockpitState = {
      run: initialRun,
      events: [],
      eventsBySeq: {},
      lastSequence: null,
      activeFaults: [],
      sseStatus: "connecting",
      actionError: null,
    };

    const event: SimulationEvent = {
      sequence: 1,
      type: "run.created",
      source: "system",
      timestamp: "2026-07-12T06:00:01Z",
      run_id: "run-123",
      payload: { scenario_id: "support-triage-resilient" },
    };

    let state = cockpitReducer(initialState, { type: "ADD_EVENT", event });
    expect(state.events).toHaveLength(1);
    expect(state.eventsBySeq[1]).toBeDefined();
    expect(state.lastSequence).toBe(1);

    // Re-dispatch duplicate event
    state = cockpitReducer(state, { type: "ADD_EVENT", event });
    expect(state.events).toHaveLength(1); // Length remains 1
    expect(state.lastSequence).toBe(1);
  });

  it("handles active fault tracking via events", () => {
    const events: SimulationEvent[] = [
      {
        sequence: 1,
        type: "fault.activated",
        source: "simulated",
        timestamp: "2026-07-12T06:00:01Z",
        run_id: "run-123",
        payload: { rule_id: "fault-outage", message: "Injected outage" },
      },
    ];

    const { activeFaults } = reconstructRun(initialRun, events);
    expect(activeFaults).toHaveLength(1);
    expect(activeFaults[0].ruleId).toBe("fault-outage");
    expect(activeFaults[0].type).toBe("provider_outage");

    // Add clearing event
    events.push({
      sequence: 2,
      type: "fault.cleared",
      source: "simulated",
      timestamp: "2026-07-12T06:00:05Z",
      run_id: "run-123",
      payload: { rule_id: "fault-outage" },
    });

    const { activeFaults: clearedFaults } = reconstructRun(initialRun, events);
    expect(clearedFaults).toHaveLength(0);
  });

  it("correctly preserves null total_cost as null and does not convert to zero", () => {
    const runWithNoCost: Run = {
      ...initialRun,
      requests: [
        {
          id: "req-1",
          fixture_id: "fix-1",
          state: "completed",
          attempts: [
            {
              id: "att-1",
              request_id: "req-1",
              index: 0,
              model: "mock-fast",
              state: "completed",
              simulator_managed_fallback: false,
              cost_total: null, // cost is unknown
              injected_latency_ms: 0,
              errors: [],
              fault_provenance: [],
            },
          ],
        },
      ],
    };

    const metrics = computeMetrics(runWithNoCost, []);
    expect(metrics.total_cost).toBeNull();
    expect(metrics.cost_per_successful_request).toBeNull();
  });

  it("tracks SSE status transitions for reconnecting and terminal streams", () => {
    const initialState: CockpitState = {
      run: initialRun,
      events: [],
      eventsBySeq: {},
      lastSequence: null,
      activeFaults: [],
      sseStatus: "connecting",
      actionError: null,
    };

    let state = cockpitReducer(initialState, { type: "SET_SSE_STATUS", status: "reconnecting" });
    expect(state.sseStatus).toBe("reconnecting");

    state = cockpitReducer(state, { type: "SET_SSE_STATUS", status: "connected" });
    expect(state.sseStatus).toBe("connected");

    state = cockpitReducer(state, {
      type: "ADD_EVENT",
      event: {
        sequence: 1,
        type: "run.completed",
        source: "system",
        timestamp: "2026-07-12T06:00:05Z",
        run_id: "run-123",
        payload: { metrics: { total_requests: 3 } },
      },
    });

    expect(state.run?.state).toBe("completed");
    expect(state.events).toHaveLength(1);
    expect(state.lastSequence).toBe(1);
  });

  it("builds reconnect URLs with the last sequence cursor", () => {
    expect(buildRunEventsUrl("http://localhost:8000", "run-123", null)).toBe(
      "http://localhost:8000/api/runs/run-123/events",
    );
    expect(buildRunEventsUrl("http://localhost:8000", "run-123", 42)).toBe(
      "http://localhost:8000/api/runs/run-123/events?last_event_id=42",
    );
  });

  it("labels mock gateway responses as mock source badges", () => {
    const event: SimulationEvent = {
      sequence: 2,
      type: "gateway.response_received",
      source: "simulated",
      timestamp: "2026-07-12T06:00:02Z",
      run_id: "run-123",
      payload: { is_mock: true },
    };

    expect(getSourceBadgeLabel(event.source, event)).toBe("MOCK");
  });

  it("disables invalid start and cancel actions for non-eligible run states", () => {
    const createdActions = getCockpitActionState(initialRun);
    expect(createdActions.canStart).toBe(true);
    expect(createdActions.canCancel).toBe(false);

    const runningRun = { ...initialRun, state: "running" as const };
    const runningActions = getCockpitActionState(runningRun);
    expect(runningActions.canStart).toBe(false);
    expect(runningActions.canCancel).toBe(true);

    const completedRun = { ...initialRun, state: "completed" as const };
    const completedActions = getCockpitActionState(completedRun);
    expect(completedActions.canStart).toBe(false);
    expect(completedActions.canCancel).toBe(false);
  });

  it("labels terminal run states accurately", () => {
    expect(getTerminalRunLabel("completed")).toBe("Run completed");
    expect(getTerminalRunLabel("failed")).toBe("Run failed");
    expect(getTerminalRunLabel("cancelled")).toBe("Run cancelled");
    expect(getTerminalRunLabel("created")).toBeNull();
    expect(getTerminalRunLabel("running")).toBeNull();
  });
});
