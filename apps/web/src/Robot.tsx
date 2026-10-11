import { themes, type ThemeName } from "@sasu/brand";
import { RobotHead, type RobotHeadShape, type RobotHeadState } from "robot-heads";

export const STATE_COLOR: Record<RobotHeadState, string> = {
  idle: "var(--accent)",
  listening: "#30c35a",
  thinking: "#f0a020",
  searching: "#1fb6d8",
  working: "var(--accent)",
  speaking: "#a35cf0",
  happy: "#30c35a",
  error: "#ef4444",
  sleeping: "#8e8e93",
};

/** Robot with a breathing, state-coloured halo. Never clipped. */
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
  return (
    <div className="relative" style={{ width: size, height: size }}>
      {halo && (
        <div
          aria-hidden
          className="breathe pointer-events-none absolute rounded-full"
          style={{
            inset: -size * 0.45,
            background: `radial-gradient(closest-side, color-mix(in srgb, ${color} 40%, transparent), transparent)`,
            filter: "blur(10px)",
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
        interactive={interactive}
        aria-label={`Sasu robot, ${state}`}
      />
    </div>
  );
}
