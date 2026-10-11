import { motion, useMotionValueEvent, useScroll } from "motion/react";
import type { RobotHeadState } from "robot-heads";
import { useRef, useState } from "react";
import { Robot, STATE_COLOR } from "../Robot";
import { cue } from "../sound";
import type { Cue } from "@sasu/brand";

const STEPS: { state: RobotHeadState; title: string; body: string; cue: Cue }[] = [
  { state: "listening", title: "Say “Hey Sasu”", body: "Sasu wakes instantly — on-device, no cloud. It checks that it's really your voice.", cue: "wake" },
  { state: "thinking", title: "It understands", body: "English, Tamil or Tanglish. Speech is turned into text locally on your Mac.", cue: "think" },
  { state: "working", title: "It does the work", body: "Opens apps, finds files, changes settings. Risky steps ask you first.", cue: "tool" },
  { state: "speaking", title: "It tells you", body: "A spoken answer in the language you used — and you can interrupt anytime.", cue: "success" },
];

export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start center", "end center"] });
  useMotionValueEvent(scrollYProgress, "change", (v) => {
    const next = Math.min(STEPS.length - 1, Math.max(0, Math.floor(v * STEPS.length)));
    if (next !== active) {
      setActive(next);
      cue(STEPS[next]!.cue);
    }
  });
  const step = STEPS[active]!;

  return (
    <section id="how" className="px-4 py-28 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold text-[var(--accent)]">How it works</p>
        <h2 className="mt-2 max-w-xl text-4xl font-semibold tracking-tight sm:text-5xl">Talk. Sasu handles the rest.</h2>
        <div ref={ref} className="mt-16 grid gap-10 md:grid-cols-2">
          <div className="md:sticky md:top-28 md:h-[420px]">
            <div className="glass relative flex h-[300px] items-center justify-center rounded-3xl md:h-full">
              <Robot state={step.state} size={170} />
              <motion.span
                key={step.state}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute bottom-5 rounded-full px-3 py-1 text-xs font-semibold"
                style={{ color: STATE_COLOR[step.state], background: `color-mix(in srgb, ${STATE_COLOR[step.state]} 14%, transparent)` }}
              >
                {step.state}
              </motion.span>
            </div>
          </div>
          <ol className="flex flex-col">
            {STEPS.map((s, i) => (
              <li key={s.title} className="flex min-h-[200px] items-center md:min-h-[300px]">
                <motion.div animate={{ opacity: i === active ? 1 : 0.35, x: i === active ? 0 : -6 }} transition={{ duration: 0.3 }}>
                  <span className="text-sm font-semibold tabular-nums" style={{ color: STATE_COLOR[s.state] }}>
                    0{i + 1}
                  </span>
                  <h3 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{s.title}</h3>
                  <p className="mt-3 max-w-md text-lg leading-relaxed text-[var(--muted)]">{s.body}</p>
                </motion.div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
