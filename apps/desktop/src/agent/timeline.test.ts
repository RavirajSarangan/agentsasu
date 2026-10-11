import { describe, expect, it } from "vitest";
import type { CoreEvent } from "./protocol";
import { buildTimeline } from "./timeline";

const log = (...events: CoreEvent[]) => events.map((event, i) => ({ at: i, event })).reverse();

describe("buildTimeline", () => {
  it("groups a turn with tools and a streamed reply", () => {
    const turns = buildTimeline(
      log(
        { type: "wake", source: "demo" },
        { type: "transcript", text: "open Safari", lang: "en" },
        { type: "tool_start", id: "t1", name: "apps.open", args: {}, risk: "safe" },
        { type: "tool_end", id: "t1", ok: true, summary: "opened" },
        { type: "say_start", text: "Done", lang: "en", big: false },
        { type: "say_chunk", text: " now" },
        { type: "turn_done", ok: true },
      ),
    );
    expect(turns).toHaveLength(1);
    expect(turns[0]!.status).toBe("ok");
    expect(turns[0]!.items.map((i) => i.kind)).toEqual(["user", "tool", "sasu"]);
    expect(turns[0]!.items[1]).toMatchObject({ status: "ok", summary: "opened" });
    expect(turns[0]!.items[2]).toMatchObject({ text: "Done now" });
  });

  it("puts the newest turn first and marks failures", () => {
    const turns = buildTimeline(
      log(
        { type: "wake", source: "demo" },
        { type: "transcript", text: "first", lang: "en" },
        { type: "turn_done", ok: true },
        { type: "wake", source: "demo" },
        { type: "transcript", text: "delete", lang: "en" },
        { type: "confirm_request", id: "c", prompt: "Sure?", lang: "en", risk: "dangerous" },
        { type: "error", code: "denied", message: "Cancelled" },
        { type: "turn_done", ok: false },
      ),
    );
    expect(turns.map((t) => t.status)).toEqual(["fail", "ok"]);
    expect(turns[0]!.items.map((i) => i.kind)).toEqual(["user", "confirm", "error"]);
  });

  it("tracks plans, privacy and undo", () => {
    const turns = buildTimeline(
      log(
        { type: "transcript", text: "tidy pdfs", lang: "en" },
        { type: "plan_preview", id: "p", steps: ["Create the folder PDFs", "Move 3 item(s) to PDFs"] },
        { type: "privacy", provider: "Google Gemini", chars: 1200, images: 0, audio: 0 },
        { type: "undo_available", turn_id: "T1", actions: ["moved a.pdf"] },
        { type: "turn_done", ok: true },
        { type: "undone", turn_id: "T1", ok: true, summary: "moved a.pdf" },
        { type: "turn_done", ok: true },
      ),
    );
    const first = turns[1]!;
    expect(first.items[1]).toEqual({ kind: "plan", steps: ["Create the folder PDFs", "Move 3 item(s) to PDFs"] });
    expect(first.privacy).toEqual({ provider: "Google Gemini", chars: 1200 });
    expect(first.undo?.used).toBe(true);
    expect(turns[0]!.items[0]).toMatchObject({ kind: "undone", ok: true });
  });

  it("ignores lone status events", () => {
    expect(buildTimeline(log({ type: "ready", version: "1", demo: true }, { type: "sleep" }))).toEqual([]);
  });
});
