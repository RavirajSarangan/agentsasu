import { Languages, Timer } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { send } from "../agent/connection";

function fmt(s: number) {
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

/** Small status chips under the robot: focus countdown, translator mode. */
export function ModeChips({
  focus,
  translating,
  meeting,
}: {
  focus: { remaining: number; total: number } | null;
  translating: boolean;
  meeting: { seconds: number; lines: number; caption: string } | null;
}) {
  return (
    <AnimatePresence>
      {meeting && (
        <motion.div key="meet" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }} className="flex max-w-[240px] flex-col items-center gap-1">
          <button
            onClick={() => send({ type: "text_command", text: "stop meeting" })}
            title="Click to stop and save notes"
            className="glass flex items-center gap-1.5 rounded-full py-1 pl-2 pr-3 text-[11.5px] font-semibold tabular-nums"
          >
            <span className="blink h-2 w-2 rounded-full bg-[#ef4444]" /> REC {fmt(meeting.seconds)} · {meeting.lines} lines
          </button>
          {meeting.caption && (
            <motion.p key={meeting.caption} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass line-clamp-2 rounded-[12px] px-2.5 py-1 text-center text-[11px] leading-snug">
              {meeting.caption}
            </motion.p>
          )}
        </motion.div>
      )}
      {focus && (
        <motion.button
          key="focus"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 6 }}
          onClick={() => send({ type: "text_command", text: "stop focus" })}
          title="Click to stop focus"
          className="glass relative flex items-center gap-1.5 overflow-hidden rounded-full py-1 pl-2 pr-3 text-[11.5px] font-semibold tabular-nums"
        >
          <span className="absolute inset-y-0 left-0 bg-[var(--accent-glow)]" style={{ width: `${(1 - focus.remaining / Math.max(1, focus.total)) * 100}%` }} />
          <Timer size={12} className="relative text-[var(--accent)]" />
          <span className="relative">Focus {fmt(focus.remaining)}</span>
        </motion.button>
      )}
      {translating && (
        <motion.button
          key="tr"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 6 }}
          onClick={() => send({ type: "text_command", text: "stop translating" })}
          title="Click to stop translating"
          className="glass flex items-center gap-1.5 rounded-full py-1 pl-2 pr-3 text-[11.5px] font-semibold"
        >
          <Languages size={12} className="text-[#8b5cf6]" /> TA ⇄ EN
        </motion.button>
      )}
    </AnimatePresence>
  );
}
