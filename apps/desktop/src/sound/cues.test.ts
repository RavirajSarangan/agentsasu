import { describe, expect, it } from "vitest";
import { initialView, type RobotView } from "../robot/stateMachine";
import { cueFor } from "./cues";

const view = (state: RobotView["state"]): RobotView => ({ ...initialView, state });

describe("sound cues", () => {
  it("chimes on wake and success", () => {
    expect(cueFor(view("idle"), { type: "wake", source: "hotkey" })).toBe("wake");
    expect(cueFor(view("speaking"), { type: "turn_done", ok: true })).toBe("success");
  });

  it("does not double up", () => {
    expect(cueFor(view("listening"), { type: "listening" })).toBeNull();
    expect(cueFor(view("error"), { type: "turn_done", ok: false })).toBeNull();
    expect(cueFor(view("sleeping"), { type: "idle_timeout" })).toBeNull();
  });

  it("plays tool, confirm, error and sleep cues", () => {
    expect(cueFor(view("thinking"), { type: "tool_start", id: "1", name: "x", args: {}, risk: "safe" })).toBe("tool");
    expect(cueFor(view("thinking"), { type: "confirm_request", id: "c", prompt: "?", lang: "en", risk: "confirm" })).toBe("confirm");
    expect(cueFor(view("working"), { type: "error", code: "x", message: "y" })).toBe("error");
    expect(cueFor(view("idle"), { type: "sleep" })).toBe("sleep");
  });

  it("stays quiet for streaming and connection noise", () => {
    expect(cueFor(view("speaking"), { type: "say_chunk", text: " hi" })).toBeNull();
    expect(cueFor(view("idle"), { type: "disconnected" })).toBeNull();
  });
});
