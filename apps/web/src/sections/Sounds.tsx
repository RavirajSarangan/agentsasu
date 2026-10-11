import { CUES, type Cue, type PackName, packs, setVolume, unlock } from "@sasu/brand";
import { Play } from "lucide-react";
import { motion } from "motion/react";
import type { RobotHeadState } from "robot-heads";
import { useState } from "react";
import { Robot } from "../Robot";

const PACKS: { id: PackName; name: string; blurb: string }[] = [
  { id: "soft", name: "Soft", blurb: "Glassy chimes, Mac-like." },
  { id: "robo", name: "Robo", blurb: "Bleeps and bloops." },
  { id: "kovil", name: "Kovil", blurb: "Temple bells in raga Mayamalavagowla." },
  { id: "toon", name: "Toon 🤪", blurb: "Slide whistle, kazoo, sad trombone." },
];

const CUE_STATE: Record<Cue, RobotHeadState> = {
  wake: "listening",
  listen: "listening",
  think: "thinking",
  tool: "working",
  confirm: "listening",
  success: "happy",
  error: "error",
  sleep: "sleeping",
  click: "idle",
  toggle: "idle",
};

export function Sounds() {
  const [pack, setPack] = useState<PackName>("toon");
  const [state, setState] = useState<RobotHeadState>("idle");
  const [step, setStep] = useState(0);

  const play = (c: Cue) => {
    unlock();
    setVolume(0.55);
    packs[pack][c]({ step });
    if (c === "tool") setStep((s) => (s + 1) % 8);
    setState(CUE_STATE[c]);
  };

  return (
    <section id="sounds" className="border-t border-[var(--line)] px-4 py-28 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold text-[var(--accent)]">Sounds with personality</p>
        <h2 className="mt-2 max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">Hear what Sasu is doing — without looking.</h2>
        <p className="mt-4 max-w-xl text-lg text-[var(--muted)]">
          Every sound is synthesized live. They come from where the robot sits on your screen, and each step of a task plays one note higher, so you can hear progress.
        </p>
        <div className="mt-12 grid items-center gap-10 lg:grid-cols-[1fr_300px]">
          <div>
            <div className="flex flex-wrap gap-2">
              {PACKS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    setPack(p.id);
                    unlock();
                    setVolume(0.55);
                    packs[p.id].success();
                    setState("happy");
                  }}
                  className={`relative rounded-2xl px-4 py-3 text-left transition ${pack === p.id ? "text-[var(--text)]" : "text-[var(--muted)]"}`}
                >
                  {pack === p.id && <motion.span layoutId="pack" className="glass absolute inset-0 rounded-2xl ring-2 ring-[var(--accent)]" />}
                  <span className="relative block font-semibold">{p.name}</span>
                  <span className="relative block text-xs">{p.blurb}</span>
                </button>
              ))}
            </div>
            <div className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-5">
              {CUES.map((c) => (
                <motion.button
                  key={c}
                  whileTap={{ scale: 0.94 }}
                  onClick={() => play(c)}
                  className="glass flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm capitalize"
                >
                  <Play size={12} className="text-[var(--accent)]" fill="currentColor" /> {c === "tool" ? `step ${step + 1}` : c}
                </motion.button>
              ))}
            </div>
          </div>
          <div className="glass flex h-[300px] items-center justify-center rounded-3xl">
            <Robot state={state} size={150} />
          </div>
        </div>
      </div>
    </section>
  );
}
