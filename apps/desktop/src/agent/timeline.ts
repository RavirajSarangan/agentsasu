// Turns the raw event log into conversation turns for the Home timeline. Pure.
import type { CoreEvent, Lang, Risk } from "./protocol";

export type TimelineItem =
  | { kind: "user"; text: string; lang: Lang }
  | { kind: "tool"; id: string; name: string; risk: Risk; status: "running" | "ok" | "fail"; summary: string }
  | { kind: "sasu"; text: string; lang: Lang }
  | { kind: "confirm"; id: string; prompt: string; risk: Risk; answered: boolean }
  | { kind: "error"; message: string }
  | { kind: "plan"; steps: string[] }
  | { kind: "undone"; ok: boolean; summary: string };

export type Turn = {
  id: number;
  startedAt: number;
  status: "active" | "ok" | "fail";
  items: TimelineItem[];
  /** Set when the turn changed something that "Sasu undo" can reverse. */
  undo?: { turnId: string; actions: string[]; used: boolean };
  /** What left the Mac during the turn. */
  privacy?: { provider: string; chars: number };
};

/** `log` is newest-first, as kept by the agent store. */
export function buildTimeline(log: readonly { at: number; event: CoreEvent }[]): Turn[] {
  const turns: Turn[] = [];
  // Held in an object so TypeScript doesn't narrow it away across the closure.
  const open: { turn: Turn | null } = { turn: null };

  const current = (at: number): Turn => {
    if (!open.turn) {
      open.turn = { id: at * 1000 + turns.length, startedAt: at, status: "active", items: [] };
      turns.push(open.turn);
    }
    return open.turn;
  };

  for (let i = log.length - 1; i >= 0; i--) {
    const { at, event } = log[i]!;
    switch (event.type) {
      case "wake":
        if (open.turn?.status === "active" && open.turn.items.length) open.turn.status = "fail";
        open.turn = null;
        current(at);
        break;
      case "transcript":
        current(at).items.push({ kind: "user", text: event.text, lang: event.lang });
        break;
      case "tool_start":
        current(at).items.push({ kind: "tool", id: event.id, name: event.name, risk: event.risk, status: "running", summary: "" });
        break;
      case "tool_end": {
        const tool = current(at).items.find((it) => it.kind === "tool" && it.id === event.id);
        if (tool?.kind === "tool") {
          tool.status = event.ok ? "ok" : "fail";
          tool.summary = event.summary;
        }
        break;
      }
      case "confirm_request":
        current(at).items.push({ kind: "confirm", id: event.id, prompt: event.prompt, risk: event.risk, answered: false });
        break;
      case "say_start":
        current(at).items.push({ kind: "sasu", text: event.text, lang: event.lang });
        break;
      case "say_chunk": {
        const last = current(at).items.at(-1);
        if (last?.kind === "sasu") last.text += event.text;
        break;
      }
      case "error":
        current(at).items.push({ kind: "error", message: event.message });
        break;
      case "plan_preview":
        current(at).items.push({ kind: "plan", steps: event.steps });
        break;
      case "undo_available":
        current(at).undo = { turnId: event.turn_id, actions: event.actions, used: false };
        break;
      case "undone": {
        current(at).items.push({ kind: "undone", ok: event.ok, summary: event.summary });
        const target = turns.find((t) => t.undo?.turnId === event.turn_id);
        if (target?.undo) target.undo.used = true;
        break;
      }
      case "privacy":
        current(at).privacy = { provider: event.provider, chars: event.chars };
        break;
      case "turn_done":
        if (open.turn) {
          open.turn.status = event.ok ? "ok" : "fail";
          for (const it of open.turn.items) if (it.kind === "confirm") it.answered = true;
        }
        open.turn = null;
        break;
      default:
        break;
    }
  }
  return turns.filter((t) => t.items.length > 0).reverse();
}
