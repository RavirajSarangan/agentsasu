import { AnimatePresence, motion } from "motion/react";
import type { RobotHeadState } from "robot-heads";
import type { Lang } from "../agent/protocol";
import { STATE_STYLE } from "./stateStyle";

/** Small pill naming what Sasu is doing; morphs between states. */
export function StateChip({ state, lang }: { state: RobotHeadState; lang: Lang }) {
  const s = STATE_STYLE[state];
  return (
    <motion.div layout transition={{ type: "spring", stiffness: 500, damping: 34 }} className="glass flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-semibold">
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={state}
          initial={{ opacity: 0, y: 6, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -6, filter: "blur(4px)" }}
          transition={{ duration: 0.22 }}
          className="flex items-center gap-1.5"
          style={{ color: s.color }}
        >
          <s.Icon size={12} strokeWidth={2.4} />
          <span lang={lang}>{lang === "ta" ? s.ta : s.label}</span>
        </motion.span>
      </AnimatePresence>
    </motion.div>
  );
}

/** Equaliser bars shown while listening (driven by mic level in Phase 2). */
export function ListeningBars({ color = "#30c35a", level }: { color?: string; level?: number }) {
  // Real mic level when we have it; a gentle idle animation otherwise.
  if (level !== undefined && level > 0) {
    const shape = [0.55, 0.85, 1, 0.8, 0.5];
    return (
      <div aria-hidden className="flex h-3.5 items-center gap-[3px]">
        {shape.map((k, i) => (
          <motion.span
            key={i}
            animate={{ scaleY: Math.max(0.2, Math.min(1, level * k * 1.6)) }}
            transition={{ type: "spring", stiffness: 600, damping: 22 }}
            className="block h-full w-[3px] origin-center rounded-full"
            style={{ background: color }}
          />
        ))}
      </div>
    );
  }
  return (
    <div aria-hidden className="flex h-3.5 items-center gap-[3px]">
      {[0, 1, 2, 3, 4].map((i) => (
        <span key={i} className="eq-bar block h-full w-[3px] rounded-full" style={{ background: color, animationDelay: `${i * 0.12}s` }} />
      ))}
    </div>
  );
}
