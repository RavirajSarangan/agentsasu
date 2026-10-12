import { themes, type ThemeName } from "@sasu/brand";
import { useInView } from "motion/react";
import { RobotHead, type RobotHeadShape, type RobotHeadState } from "robot-heads";
import { useRef } from "react";

export const STATE_COLOR: Record<RobotHeadState, string> = {
  idle: "var(--accent)",
  listening: "var(--signal)",
  thinking: "var(--amber)",
  searching: "#1fb6d8",
  working: "var(--accent)",
  speaking: "#8b5cf6",
  happy: "var(--signal)",
  error: "var(--danger)",
  sleeping: "var(--faint)",
};

/** The robot, optionally with a soft state-coloured glow. Never clipped by its parent.
 * Each head draws on its own canvas every frame, so it pauses while off screen: a page full
 * of robots then costs only the ones you can see (this was most of the phone lag). */
export function Robot({
  state,
  size,
  shape = "rectangle",
  theme = "midnight",
  lang = "en",
  halo = true,
  interactive = true,
}: {
  state: RobotHeadState;
  size: number;
  shape?: RobotHeadShape;
  theme?: ThemeName;
  lang?: "en" | "ta";
  halo?: boolean;
  interactive?: boolean;
}) {
  const t = themes[theme];
  const color = STATE_COLOR[state];
  const ref = useRef<HTMLDivElement>(null);
  const visible = useInView(ref, { margin: "120px" });
  return (
    <div ref={ref} className="relative" style={{ width: size, height: size }}>
      {halo && (
        <div
          aria-hidden
          className="breathe pointer-events-none absolute rounded-full"
          style={{
            inset: -size * 0.4,
            background: `radial-gradient(closest-side, color-mix(in srgb, ${color} 30%, transparent), transparent)`,
            transition: "background 500ms ease",
          }}
        />
      )}
      <RobotHead
        size={size}
        shape={shape}
        state={state}
        color={t.color}
        trimColor={t.trimColor}
        screenColor={t.screen[lang]}
        interactive={interactive && visible}
        paused={!visible}
        aria-label={`Sasu robot, ${state}`}
      />
    </div>
  );
}
