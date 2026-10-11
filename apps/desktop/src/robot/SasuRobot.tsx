import { useSelector } from "@tanstack/react-store";
import { forwardRef, useMemo } from "react";
import { RobotHead, type RobotHeadProps, type RobotHeadState } from "robot-heads";
import { agentStore } from "../agent/store";
import { effectiveShape, settingsStore } from "./settings";
import { themes } from "./themes";

const LABEL: Record<RobotHeadState, string> = {
  idle: "idle",
  thinking: "thinking",
  searching: "searching",
  listening: "listening",
  speaking: "speaking",
  working: "working",
  happy: "happy",
  error: "has a problem",
  sleeping: "sleeping",
};

export function speedFor(state: RobotHeadState, batterySaver: boolean): number {
  const base = state === "working" ? 1.4 : state === "sleeping" ? 0.7 : 1;
  return batterySaver ? base * 0.7 : base;
}

type Props = Omit<RobotHeadProps, "state" | "shape" | "color" | "trimColor" | "screenColor"> & {
  /** Override the live agent state (Robot Lab, avatars). */
  state?: RobotHeadState;
};

/** The live Sasu robot: state from the agent, look from the shared settings. */
export const SasuRobot = forwardRef<HTMLCanvasElement, Props>(function SasuRobot(
  { state: forced, size, speed: speedOverride, ...rest },
  ref,
) {
  const live = useSelector(agentStore, (s) => s.view.state);
  const lang = useSelector(agentStore, (s) => s.view.lang);
  const settings = useSelector(settingsStore);
  const state = forced ?? live;
  const theme = themes[settings.theme];
  const seed = useMemo(() => Math.random(), []);

  return (
    <RobotHead
      ref={ref}
      shape={effectiveShape(settings)}
      state={state}
      size={size ?? settings.size}
      color={theme.color}
      trimColor={theme.trimColor}
      screenColor={theme.screen[lang]}
      speed={speedOverride ?? speedFor(state, settings.batterySaver)}
      paused={settings.dnd}
      seed={seed}
      aria-label={`Sasu, ${LABEL[state]}`}
      {...rest}
    />
  );
});
