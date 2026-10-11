// Pure mapping from agent events to what the robot shows. No timers or I/O here:
// the store schedules `settle` (after happy/error) and `idle_timeout` (→ sleeping).
import type { RobotHeadState } from "robot-heads";
import type { CoreEvent, Lang, LockReason, Risk } from "../agent/protocol";

export const HAPPY_MS = 1200;
export const ERROR_MS = 2000;
export const SLEEP_AFTER_MS = 5 * 60 * 1000;

/** Tools that look for things show `searching`; everything else shows `working`. */
const SEARCH_TOOLS = /^(web_search|web\.|files[._](find|search|list|read)|screen[._]|browser[._]|clipboard_get|apps_list|media_now_playing)/;

export type ConfirmPrompt = { id: string; prompt: string; risk: Risk };
export type AuthPrompt = { id: string; reason: string };
export type UndoOffer = { turnId: string; actions: string[] };

export type RobotView = {
  state: RobotHeadState;
  caption: string;
  lang: Lang;
  activeTool: string | null;
  confirm: ConfirmPrompt | null;
  /** Waiting for Touch ID / password (handled by the desktop shell). */
  auth: AuthPrompt | null;
  /** Steps Sasu is about to take (plan preview), until the turn moves on. */
  plan: string[] | null;
  /** The last turn can be undone. */
  undo: UndoOffer | null;
  /** Non-empty while Sasu is locked (screen locked, disabled, or locked by the user). */
  locks: LockReason[];
  /** When set, the store returns the robot to idle after this many ms. */
  settleAfterMs: number | null;
};

export type LocalEvent = { type: "settle" } | { type: "idle_timeout" } | { type: "disconnected" };

export const initialView: RobotView = {
  state: "idle",
  caption: "",
  lang: "en",
  activeTool: null,
  confirm: null,
  auth: null,
  plan: null,
  undo: null,
  locks: [],
  settleAfterMs: null,
};

export function toolState(name: string): RobotHeadState {
  return SEARCH_TOOLS.test(name) ? "searching" : "working";
}

export function reduce(view: RobotView, event: CoreEvent | LocalEvent): RobotView {
  const next = { ...view, settleAfterMs: null };
  if (view.locks.length && !["locked", "unlocked", "ready", "alarm"].includes(event.type)) {
    return { ...view, state: "sleeping" }; // nothing moves the robot while locked
  }
  switch (event.type) {
    case "ready":
      return { ...initialView };
    case "locked":
      return { ...next, state: "sleeping", caption: "", activeTool: null, confirm: null, auth: null, locks: event.reasons };
    case "unlocked":
      return { ...next, state: "idle", caption: "", locks: [] };
    case "speaker_rejected":
      return { ...next, state: "error", caption: "Sorry, I only listen to my owner.", activeTool: null, settleAfterMs: ERROR_MS };
    case "auth_required":
      return { ...next, state: "listening", caption: event.reason, confirm: null, auth: { id: event.id, reason: event.reason } };
    case "wake":
    case "listening":
      return { ...next, state: "listening", caption: view.state === "listening" ? view.caption : "", confirm: null, plan: null };
    case "partial_transcript":
      return { ...next, caption: event.text };
    case "transcript":
      return { ...next, state: "thinking", caption: event.text, lang: event.lang, plan: null, undo: null };
    case "plan_preview":
      return { ...next, state: "thinking", plan: event.steps };
    case "undo_available":
      return { ...next, undo: { turnId: event.turn_id, actions: event.actions } };
    case "undone":
      return { ...next, undo: null };
    case "focus_app":
    case "privacy":
    case "level":
    case "enroll_progress":
    case "brain_status":
    case "voice_status":
    case "fun":
    case "focus":
    case "translate_mode":
    case "snap_request":
      return { ...view };
    case "idle":
      return { ...next, state: "idle", caption: "", activeTool: null };
    case "alarm":
      return { ...next, state: "error", caption: `🚨 ${event.detail}`, activeTool: null, confirm: null, auth: null, settleAfterMs: 4000 };
    case "intruder":
      return { ...next, caption: "Not my owner. Guest mode." };
    case "thinking":
      return { ...next, state: "thinking" };
    case "tool_start":
      return { ...next, state: toolState(event.name), activeTool: event.name, auth: null, plan: null };
    case "tool_end":
      return { ...next, state: "thinking", activeTool: null };
    case "confirm_request":
      return {
        ...next,
        state: "listening",
        caption: event.prompt,
        lang: event.lang,
        confirm: { id: event.id, prompt: event.prompt, risk: event.risk },
      };
    case "say_start":
      return { ...next, state: "speaking", caption: event.text, lang: event.lang, confirm: null };
    case "say_chunk":
      return { ...next, caption: view.caption + event.text };
    case "say_end":
      return next;
    case "turn_done":
      return event.ok
        ? { ...next, state: "happy", activeTool: null, confirm: null, auth: null, settleAfterMs: HAPPY_MS }
        : { ...next, state: "error", activeTool: null, confirm: null, auth: null, settleAfterMs: ERROR_MS };
    case "error":
      return { ...next, state: "error", caption: event.message, activeTool: null, confirm: null, auth: null, settleAfterMs: ERROR_MS };
    case "sleep":
    case "idle_timeout":
      return { ...next, state: "sleeping", caption: "", activeTool: null, confirm: null };
    case "settle":
      return { ...next, state: "idle", caption: "" };
    case "disconnected":
      return { ...next, state: "error", caption: "Reconnecting to Sasu core…", activeTool: null, confirm: null };
  }
}
