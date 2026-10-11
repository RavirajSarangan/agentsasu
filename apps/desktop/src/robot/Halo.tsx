import type { RobotHeadState } from "robot-heads";
import { STATE_STYLE } from "./stateStyle";

/** Soft state-coloured light behind the robot. Purely decorative, never clips it. */
export function Halo({ state, size }: { state: RobotHeadState; size: number }) {
  const color = STATE_STYLE[state].color;
  const quiet = state === "idle" || state === "sleeping";
  return (
    <div
      aria-hidden
      className={quiet ? "" : "breathe"}
      style={{
        position: "absolute",
        left: "50%",
        top: "50%",
        width: size * 1.7,
        height: size * 1.7,
        marginLeft: -size * 0.85,
        marginTop: -size * 0.85,
        borderRadius: "50%",
        background: `radial-gradient(closest-side, color-mix(in srgb, ${color} 42%, transparent), transparent)`,
        opacity: quiet ? 0.35 : 1,
        transition: "background 400ms ease, opacity 400ms ease",
        pointerEvents: "none",
        filter: "blur(6px)",
      }}
    />
  );
}
