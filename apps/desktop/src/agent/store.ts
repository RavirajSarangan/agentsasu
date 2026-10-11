import { Store } from "@tanstack/react-store";
import { initialView, reduce, SLEEP_AFTER_MS, type LocalEvent, type RobotView } from "../robot/stateMachine";
import type { CoreEvent } from "./protocol";

export type Connection = "connecting" | "open" | "closed";

export type BrainStatus = Extract<CoreEvent, { type: "brain_status" }>;
export type VoiceStatus = Extract<CoreEvent, { type: "voice_status" }>;
export type EnrollStep = Extract<CoreEvent, { type: "enroll_progress" }>;
export type PrivacyStat = Extract<CoreEvent, { type: "privacy" }>;

export type AgentState = {
  connection: Connection;
  demo: boolean;
  version: string | null;
  view: RobotView;
  brain: BrainStatus | null;
  voice: VoiceStatus | null;
  enroll: EnrollStep | null;
  /** Live mic level 0–1 while listening. */
  level: number;
  /** What left the Mac in the last turn. */
  privacy: PrivacyStat | null;
  log: { at: number; event: CoreEvent }[];
};

const LOG_LIMIT = 200;

export const agentStore = new Store<AgentState>({
  connection: "connecting",
  demo: false,
  version: null,
  view: initialView,
  brain: null,
  voice: null,
  enroll: null,
  level: 0,
  privacy: null,
  log: [],
});

type Listener = (event: CoreEvent | LocalEvent, prev: RobotView, next: RobotView) => void;
const listeners = new Set<Listener>();

/** Subscribe to every agent transition (sounds, analytics). Returns an unsubscribe. */
export function onAgentEvent(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify(event: CoreEvent | LocalEvent, prev: RobotView) {
  const next = agentStore.get().view;
  for (const fn of listeners) fn(event, prev, next);
}

let settleTimer: ReturnType<typeof setTimeout> | undefined;
let idleTimer: ReturnType<typeof setTimeout> | undefined;

function applyLocal(event: LocalEvent) {
  const prev = agentStore.get().view;
  agentStore.setState((s) => ({ ...s, view: reduce(s.view, event) }));
  notify(event, prev);
}

function scheduleTimers(view: RobotView) {
  clearTimeout(settleTimer);
  clearTimeout(idleTimer);
  if (view.settleAfterMs !== null) {
    settleTimer = setTimeout(() => applyLocal({ type: "settle" }), view.settleAfterMs);
  }
  if (view.state !== "sleeping") {
    idleTimer = setTimeout(() => applyLocal({ type: "idle_timeout" }), SLEEP_AFTER_MS);
  }
}

export function applyEvent(event: CoreEvent) {
  if (event.type === "level") {
    // High-rate: update only the meter, skip the log and the state machine.
    agentStore.setState((s) => ({ ...s, level: event.rms }));
    return;
  }
  const prev = agentStore.get().view;
  agentStore.setState((s) => ({
    ...s,
    demo: event.type === "ready" ? event.demo : s.demo,
    version: event.type === "ready" ? event.version : s.version,
    view: reduce(s.view, event),
    brain: event.type === "brain_status" ? event : s.brain,
    voice: event.type === "voice_status" ? event : s.voice,
    enroll: event.type === "enroll_progress" ? event : s.enroll,
    level: event.type === "turn_done" ? 0 : s.level,
    privacy: event.type === "privacy" ? event : s.privacy,
    log: [{ at: Date.now(), event }, ...s.log].slice(0, LOG_LIMIT),
  }));
  scheduleTimers(agentStore.get().view);
  notify(event, prev);
}

export function setConnection(connection: Connection) {
  agentStore.setState((s) => ({ ...s, connection }));
  if (connection === "closed") applyLocal({ type: "disconnected" });
}
