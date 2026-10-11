// Which sound an agent event deserves. Pure, so it's tested without audio.
import type { CoreEvent } from "../agent/protocol";
import type { LocalEvent, RobotView } from "../robot/stateMachine";

import type { Cue } from "@sasu/brand";

export { CUES, type Cue } from "@sasu/brand";

export function cueFor(prev: RobotView, event: CoreEvent | LocalEvent): Cue | null {
  switch (event.type) {
    case "wake":
      return "wake";
    case "listening":
      return prev.state === "listening" ? null : "listen";
    case "transcript":
      return "think";
    case "tool_start":
      return "tool";
    case "confirm_request":
      return "confirm";
    case "turn_done":
      if (event.ok) return "success";
      return prev.state === "error" ? null : "error"; // the error event already played
    case "error":
    case "speaker_rejected":
      return "error";
    case "auth_required":
      return "confirm";
    case "locked":
      return prev.locks.length ? null : "sleep";
    case "unlocked":
      return "wake";
    case "undone":
      return "toggle";
    case "alarm":
      return "error";
    case "sleep":
    case "idle_timeout":
      return prev.state === "sleeping" ? null : "sleep";
    default:
      return null;
  }
}
