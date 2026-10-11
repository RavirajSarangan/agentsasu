import { describe, expect, it } from "vitest";
import type { CoreEvent } from "../agent/protocol";
import { initialView, reduce, toolState, type LocalEvent } from "./stateMachine";

const run = (...events: (CoreEvent | LocalEvent)[]) => events.reduce(reduce, initialView);

describe("robot state machine", () => {
  it("walks a full successful turn", () => {
    const states = [
      { type: "wake", source: "hotkey" },
      { type: "transcript", text: "open Safari", lang: "en" },
      { type: "tool_start", id: "1", name: "web_search", args: {}, risk: "safe" },
      { type: "tool_start", id: "2", name: "apps.open", args: {}, risk: "safe" },
      { type: "say_start", text: "Done", lang: "en" },
      { type: "turn_done", ok: true },
      { type: "settle" },
    ] satisfies (CoreEvent | LocalEvent)[];
    const seen = states.map((_, i) => run(...states.slice(0, i + 1)).state);
    expect(seen).toEqual(["listening", "thinking", "searching", "working", "speaking", "happy", "idle"]);
  });

  it("asks for confirmation while listening", () => {
    const v = run({ type: "confirm_request", id: "c1", prompt: "Delete?", lang: "ta", risk: "confirm" });
    expect(v).toMatchObject({ state: "listening", lang: "ta", confirm: { id: "c1" } });
  });

  it("settles after happy and error", () => {
    expect(run({ type: "turn_done", ok: true }).settleAfterMs).toBeGreaterThan(0);
    expect(run({ type: "error", code: "x", message: "boom" })).toMatchObject({ state: "error", caption: "boom" });
  });

  it("sleeps on idle timeout and wakes on wake", () => {
    expect(run({ type: "idle_timeout" }).state).toBe("sleeping");
    expect(run({ type: "idle_timeout" }, { type: "wake", source: "wakeword" }).state).toBe("listening");
  });

  it("classifies tools", () => {
    expect(toolState("files.find")).toBe("searching");
    expect(toolState("shell.run")).toBe("working");
  });
});

describe("security states", () => {
  it("sleeps while locked and ignores activity until unlocked", () => {
    const locked = run({ type: "locked", reasons: ["screen"] });
    expect(locked).toMatchObject({ state: "sleeping", locks: ["screen"] });
    expect(reduce(locked, { type: "wake", source: "wakeword" }).state).toBe("sleeping");
    expect(reduce(locked, { type: "unlocked" })).toMatchObject({ state: "idle", locks: [] });
  });

  it("shows a rejected stranger as an error", () => {
    expect(run({ type: "speaker_rejected", score: 0.2 })).toMatchObject({ state: "error", caption: "Sorry, I only listen to my owner." });
  });

  it("waits for Touch ID and clears it when work starts", () => {
    const v = run({ type: "auth_required", id: "a1", reason: "Empty Trash", risk: "dangerous" });
    expect(v.auth).toEqual({ id: "a1", reason: "Empty Trash" });
    expect(reduce(v, { type: "tool_start", id: "t", name: "files.trash", args: {}, risk: "dangerous" }).auth).toBeNull();
  });
});
