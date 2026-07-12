import { Run, SimulationEvent as ApiSimulationEvent } from "@/lib/api";

export type SseStatus = "connecting" | "connected" | "reconnecting" | "closed" | "error";
export type EventSource = "real" | "simulated" | "system" | "mock";

export interface ActiveFault {
  ruleId: string;
  type: string;
  message: string;
  activatedAtMs: number;
  targetProvider?: string;
  targetModel?: string;
  durationMs: number;
  parameters: any;
}

export interface SimulationEvent extends ApiSimulationEvent {
  source: EventSource;
  payload: Record<string, unknown>;
}

export interface CockpitState {
  run: Run | null;
  events: SimulationEvent[];
  eventsBySeq: Record<number, SimulationEvent>;
  lastSequence: number | null;
  activeFaults: ActiveFault[];
  sseStatus: SseStatus;
  actionError: string | null;
}

export interface CockpitActionState {
  canStart: boolean;
  canCancel: boolean;
}

export type CockpitAction =
  | { type: "INIT"; run: Run }
  | { type: "ADD_EVENT"; event: SimulationEvent }
  | { type: "ADD_EVENTS"; events: SimulationEvent[] }
  | { type: "SET_SSE_STATUS"; status: SseStatus }
  | { type: "SET_ACTION_ERROR"; error: string | null };

export function formatScenarioName(id: string): string {
  return id
    .split(/[-_]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function getCockpitActionState(run: Run | null): CockpitActionState {
  if (!run) {
    return { canStart: false, canCancel: false };
  }

  return {
    canStart: run.state === "created",
    canCancel: run.state === "running",
  };
}

export function getSourceBadgeLabel(source: EventSource, event?: SimulationEvent): string {
  if (source === "mock" || event?.payload?.is_mock === true) {
    return "MOCK";
  }
  return source.toUpperCase();
}

export function reconstructRun(initialRun: Run, events: SimulationEvent[]): { run: Run; activeFaults: ActiveFault[] } {
  if (!initialRun) return { run: initialRun, activeFaults: [] };

  const run: Run = {
    ...initialRun,
    state: "created",
    requests: [],
    metrics: {
      total_requests: initialRun.scenario.request_count,
      completed_requests: 0,
      failed_requests: 0,
      abandoned_requests: 0,
      passed_validations: 0,
      failed_validations: 0,
    },
    error: null,
  };

  const activeFaults: ActiveFault[] = [];
  const sortedEvents = [...events].sort((a, b) => a.sequence - b.sequence);

  for (const event of sortedEvents) {
    const { type, payload } = event;
    switch (type) {
      case "run.created":
        run.state = "created";
        break;
      case "run.started":
        run.state = "running";
        break;
      case "run.completed":
        run.state = "completed";
        if (payload.metrics) run.metrics = { ...run.metrics, ...(payload.metrics as Record<string, unknown>) };
        break;
      case "run.failed":
        run.state = "failed";
        if (payload.metrics) run.metrics = { ...run.metrics, ...(payload.metrics as Record<string, unknown>) };
        if (typeof payload.error === "string") run.error = payload.error;
        break;
      case "run.cancelled":
        run.state = "cancelled";
        if (payload.metrics) run.metrics = { ...run.metrics, ...payload.metrics };
        break;

      case "request.queued": {
        const reqId = typeof payload.request_id === "string" ? payload.request_id : null;
        if (!reqId) break;
        if (!run.requests) run.requests = [];
        if (!run.requests.some((r) => r.id === reqId)) {
          run.requests.push({
            id: reqId,
            fixture_id: typeof payload.fixture_id === "string" ? payload.fixture_id : "unknown",
            state: "queued",
            attempts: [],
            validation_result: null,
          });
        }
        break;
      }

      case "attempt.started": {
        const reqId = typeof payload.request_id === "string" ? payload.request_id : undefined;
        const attemptId = typeof payload.attempt_id === "string" ? payload.attempt_id : undefined;
        const req = reqId ? run.requests?.find((r) => r.id === reqId) : undefined;
        if (req && attemptId && reqId) {
          req.state = "running";
          if (!req.attempts) req.attempts = [];
          if (!req.attempts.some((a) => a.id === attemptId)) {
            req.attempts.push({
              id: attemptId,
              request_id: reqId,
              index: typeof payload.route_index === "number" ? payload.route_index : 0,
              model: typeof payload.model === "string" ? payload.model : "unknown",
              provider: typeof payload.provider === "string" ? payload.provider : undefined,
              state: "started",
              simulator_managed_fallback: typeof payload.simulator_managed_fallback === "boolean" ? payload.simulator_managed_fallback : false,
              fault_provenance: [],
              errors: [],
              injected_latency_ms: 0,
            });
          }
        }
        break;
      }

      case "fault.injected": {
        const reqId = typeof payload.request_id === "string" ? payload.request_id : null;
        const attemptId = typeof payload.attempt_id === "string" ? payload.attempt_id : null;
        const req = reqId ? run.requests?.find((r) => r.id === reqId) : undefined;
        const att = req && attemptId ? req.attempts?.find((a) => a.id === attemptId) : undefined;
        const provenance = payload.provenance && typeof payload.provenance === "object"
          ? (payload.provenance as Record<string, unknown>)
          : null;
        if (att && provenance && typeof provenance.rule_id === "string") {
          if (!att.fault_provenance) att.fault_provenance = [];
          if (!att.fault_provenance.some((p) => p.rule_id === provenance.rule_id)) {
            att.fault_provenance.push(provenance as never);
            if (typeof provenance.injected_delay_ms === "number") {
              att.injected_latency_ms = (att.injected_latency_ms ?? 0) + provenance.injected_delay_ms;
            }
            if (typeof provenance.simulated_status_code === "number") {
              att.simulated_status_code = provenance.simulated_status_code;
            }
          }
        }
        break;
      }

      case "gateway.response_received": {
        const reqId = typeof payload.request_id === "string" ? payload.request_id : null;
        const attemptId = typeof payload.attempt_id === "string" ? payload.attempt_id : null;
        const req = reqId ? run.requests?.find((r) => r.id === reqId) : undefined;
        const att = req && attemptId ? req.attempts?.find((a) => a.id === attemptId) : undefined;
        if (att) {
          att.actual_model = typeof payload.model === "string" ? payload.model : undefined;
          att.actual_provider = typeof payload.provider === "string" ? payload.provider : undefined;
          att.upstream_response_id = typeof payload.response_id === "string" ? payload.response_id : undefined;
          att.upstream_latency_ms = typeof payload.upstream_latency_ms === "number" ? payload.upstream_latency_ms : undefined;
          const usage = payload.usage && typeof payload.usage === "object" ? payload.usage as Record<string, unknown> : null;
          if (usage) {
            att.input_tokens = typeof usage.input_tokens === "number" ? usage.input_tokens : undefined;
            att.output_tokens = typeof usage.output_tokens === "number" ? usage.output_tokens : undefined;
            att.total_tokens = typeof usage.total_tokens === "number" ? usage.total_tokens : undefined;
          }
          const cost = payload.cost && typeof payload.cost === "object" ? payload.cost as Record<string, unknown> : null;
          if (cost) {
            att.cost_total = typeof cost.total === "number" ? cost.total : typeof cost.cost_total === "number" ? cost.cost_total : null;
          }
        }
        break;
      }

      case "validation.passed":
      case "validation.failed": {
        const reqId = typeof payload.request_id === "string" ? payload.request_id : null;
        const req = reqId ? run.requests?.find((r) => r.id === reqId) : undefined;
        if (req) {
          req.validation_result = {
            score: (payload.score as Record<string, unknown>) as {
              schema_valid: boolean;
              category_correct: boolean;
              priority_correct: boolean;
              summary_keyword_coverage: number;
              overall_correct: boolean;
            },
            errors: Array.isArray(payload.errors) ? payload.errors.filter((item): item is string => typeof item === "string") : undefined,
          };
        }
        const attemptId = typeof payload.attempt_id === "string" ? payload.attempt_id : null;
        const att = req && attemptId ? req.attempts?.find((a) => a.id === attemptId) : undefined;
        if (att) {
          att.validation_passed = (type === "validation.passed");
        }
        break;
      }

      case "attempt.completed": {
        const reqId = typeof payload.request_id === "string" ? payload.request_id : null;
        const attemptId = typeof payload.attempt_id === "string" ? payload.attempt_id : null;
        const req = reqId ? run.requests?.find((r) => r.id === reqId) : undefined;
        const att = req && attemptId ? req.attempts?.find((a) => a.id === attemptId) : undefined;
        if (att) {
          att.state = (payload.state as "completed" | "failed" | "abandoned" | "started" | "blocked") ?? "failed";
          if (typeof payload.simulated_status_code === "number") {
            att.simulated_status_code = payload.simulated_status_code;
          }
          if (Array.isArray(payload.errors)) {
            att.errors = payload.errors.filter((item): item is string => typeof item === "string");
          }
        }
        break;
      }

      case "request.completed": {
        const reqId = typeof payload.request_id === "string" ? payload.request_id : null;
        const req = reqId ? run.requests?.find((r) => r.id === reqId) : undefined;
        if (req && typeof payload.state === "string") {
          req.state = payload.state as "queued" | "running" | "completed" | "failed" | "abandoned";
        }
        break;
      }

      case "metrics.updated":
        if (payload.metrics) {
          run.metrics = { ...run.metrics, ...(payload.metrics as Record<string, unknown>) };
        }
        break;

      case "fault.activated": {
        const ruleId = typeof payload.rule_id === "string" ? payload.rule_id : null;
        if (ruleId && !activeFaults.some((f) => f.ruleId === ruleId)) {
          const ruleConfig = run.scenario.fault_rules?.find(
            (rule) => rule.id === ruleId
          );
          activeFaults.push({
            ruleId,
            type: typeof ruleConfig?.type === "string" ? ruleConfig.type : "unknown",
            message: typeof payload.message === "string" ? payload.message : `Fault ${ruleId} activated`,
            activatedAtMs: typeof payload.at_ms === "number" ? payload.at_ms : 0,
            targetProvider:
              typeof ruleConfig?.target_provider === "string"
                ? ruleConfig.target_provider
                : undefined,
            targetModel:
              typeof ruleConfig?.target_model === "string"
                ? ruleConfig.target_model
                : undefined,
            durationMs:
              typeof ruleConfig?.duration_ms === "number" ? ruleConfig.duration_ms : 0,
            parameters:
              typeof ruleConfig?.parameters === "object" && ruleConfig.parameters !== null
                ? ruleConfig.parameters
                : {},
          });
        }
        break;
      }

      case "fault.cleared": {
        const ruleId = typeof payload.rule_id === "string" ? payload.rule_id : null;
        const idx = typeof ruleId === "string" ? activeFaults.findIndex((f) => f.ruleId === ruleId) : -1;
        if (idx !== -1) {
          activeFaults.splice(idx, 1);
        }
        break;
      }

      default:
        break;
    }
  }

  return { run, activeFaults };
}

export function cockpitReducer(state: CockpitState, action: CockpitAction): CockpitState {
  switch (action.type) {
    case "INIT": {
      const { run, activeFaults } = reconstructRun(action.run, state.events);
      return {
        ...state,
        run: run,
        activeFaults,
        actionError: null,
      };
    }
    case "ADD_EVENT": {
      const { event } = action;
      if (state.eventsBySeq[event.sequence]) {
        return state;
      }
      const newEvents = [...state.events, event];
      const newEventsBySeq = { ...state.eventsBySeq, [event.sequence]: event };

      if (!state.run) {
        return {
          ...state,
          events: newEvents,
          eventsBySeq: newEventsBySeq,
          lastSequence: Math.max(state.lastSequence ?? 0, event.sequence),
        };
      }

      const { run, activeFaults } = reconstructRun(state.run, newEvents);
      return {
        ...state,
        run,
        events: newEvents,
        eventsBySeq: newEventsBySeq,
        lastSequence: Math.max(state.lastSequence ?? 0, event.sequence),
        activeFaults,
      };
    }
    case "ADD_EVENTS": {
      const newEvents = [...state.events];
      const newEventsBySeq = { ...state.eventsBySeq };
      let changed = false;
      for (const event of action.events) {
        if (!newEventsBySeq[event.sequence]) {
          newEvents.push(event);
          newEventsBySeq[event.sequence] = event;
          changed = true;
        }
      }
      if (!changed) return state;

      if (!state.run) {
        return {
          ...state,
          events: newEvents,
          eventsBySeq: newEventsBySeq,
          lastSequence: newEvents.reduce(
            (max, item) => Math.max(max, item.sequence),
            state.lastSequence ?? 0,
          ),
        };
      }

      const { run, activeFaults } = reconstructRun(state.run, newEvents);
      return {
        ...state,
        run,
        events: newEvents,
        eventsBySeq: newEventsBySeq,
        lastSequence: newEvents.reduce(
          (max, item) => Math.max(max, item.sequence),
          state.lastSequence ?? 0,
        ),
        activeFaults,
      };
    }
    case "SET_SSE_STATUS":
      return {
        ...state,
        sseStatus: action.status,
      };
    case "SET_ACTION_ERROR":
      return {
        ...state,
        actionError: action.error,
      };
    default:
      return state;
  }
}

export function buildRunEventsUrl(
  apiBaseUrl: string,
  runId: string,
  lastSequence: number | null,
): string {
  const url = new URL(`/api/runs/${runId}/events`, apiBaseUrl);
  if (lastSequence !== null) {
    url.searchParams.set("last_event_id", String(lastSequence));
  }
  return url.toString();
}
