import { createFileRoute } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { Download } from "lucide-react";
import { motion } from "motion/react";
import { useRef } from "react";
import { RobotHead, robotHeadShapes, robotHeadStates, type RobotHeadState } from "robot-heads";
import { settingsStore } from "../robot/settings";
import { STATE_STYLE } from "../robot/stateStyle";
import { themes } from "../robot/themes";
import type { Cue } from "../sound/cues";
import { play } from "../sound/player";
import { Card } from "../ui/Card";

export const Route = createFileRoute("/panel/robot-lab")({ component: RobotLab });

const STATE_CUE: Record<RobotHeadState, Cue> = {
  idle: "click",
  thinking: "think",
  searching: "tool",
  listening: "listen",
  speaking: "confirm",
  working: "tool",
  happy: "success",
  error: "error",
  sleeping: "sleep",
};

/** Every shape × every state in the current theme. Click to hear it, ⤓ to save a PNG. */
function RobotLab() {
  const theme = themes[useSelector(settingsStore, (s) => s.theme)];
  const canvases = useRef(new Map<string, HTMLCanvasElement>());

  const snapshot = (key: string) => {
    const canvas = canvases.current.get(key);
    if (!canvas) return;
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `sasu-${key}.png`;
    a.click();
  };

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-[22px] font-semibold tracking-tight">Robot Lab</h1>
        <p className="text-[13px] text-[var(--muted)]">
          {robotHeadShapes.length} shapes × {robotHeadStates.length} states. Click a robot to hear its sound.
        </p>
      </header>

      {robotHeadStates.map((state, row) => {
        const s = STATE_STYLE[state];
        return (
          <section key={state} className="flex flex-col gap-2">
            <h2 className="flex items-center gap-1.5 px-1 text-[12px] font-semibold" style={{ color: s.color }}>
              <s.Icon size={13} /> {s.label}
              <span className="font-normal text-[var(--faint)]">· {state}</span>
            </h2>
            <div className="grid grid-cols-4 gap-3">
              {robotHeadShapes.map((shape, col) => {
                const key = `${shape}-${state}`;
                return (
                  <motion.div key={key} whileHover={{ y: -3 }} transition={{ type: "spring", stiffness: 400, damping: 25 }} className="group">
                    <Card className="relative flex cursor-default flex-col items-center gap-1 pb-2.5 pt-7" onClick={() => play(STATE_CUE[state], { force: true })}>
                      <RobotHead
                        ref={(el) => {
                          if (el) canvases.current.set(key, el);
                        }}
                        shape={shape}
                        state={state}
                        size={76}
                        color={theme.color}
                        trimColor={theme.trimColor}
                        screenColor={theme.screen.en}
                        seed={(row * robotHeadShapes.length + col) / 40}
                      />
                      <span className="mt-2 text-[11px] capitalize text-[var(--muted)]">{shape}</span>
                      <button
                        aria-label={`Save ${key} as PNG`}
                        onClick={(e) => {
                          e.stopPropagation();
                          snapshot(key);
                        }}
                        className="absolute right-2 top-2 rounded-md p-1 text-[var(--faint)] opacity-0 transition-opacity hover:bg-[var(--hairline)] hover:text-[var(--text)] group-hover:opacity-100"
                      >
                        <Download size={13} />
                      </button>
                    </Card>
                  </motion.div>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
