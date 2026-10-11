import { CUES, type Cue, type PackName, packs, setVolume, unlock } from "@sasu/brand";
import { motion } from "motion/react";
import type { RobotHeadState } from "robot-heads";
import { useState } from "react";
import { Robot } from "../Robot";

const PACKS: { id: PackName; name: string; blurb: string }[] = [
  { id: "soft", name: "Soft", blurb: "Glassy chimes that sit right on a Mac." },
  { id: "robo", name: "Robo", blurb: "Bleeps and bloops." },
  { id: "kovil", name: "Kovil", blurb: "Temple bells tuned to raga Mayamalavagowla." },
  { id: "toon", name: "Toon", blurb: "Slide whistle, kazoo, sad trombone, snore." },
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

const CUE_LABEL: Record<Cue, string> = {
  wake: "Wake",
  listen: "Listen",
  think: "Think",
  tool: "Step",
  confirm: "Ask",
  success: "Done",
  error: "Oops",
  sleep: "Sleep",
  click: "Click",
  toggle: "Toggle",
};

export function Sounds() {
  const [pack, setPack] = useState<PackName>("kovil");
  const [state, setState] = useState<RobotHeadState>("idle");
  const [step, setStep] = useState(0);
  const [pressed, setPressed] = useState<string | null>(null);

  const hit = (c: Cue) => {
    unlock();
    setVolume(0.55);
    packs[pack][c]({ step });
    if (c === "tool") setStep((s) => (s + 1) % 8);
    setState(CUE_STATE[c]);
    setPressed(c);
    setTimeout(() => setPressed(null), 120);
  };

  return (
    <section id="sounds" className="bg-[var(--bg-2)] px-4 py-16 sm:px-6 sm:py-28">
      <div className="mx-auto max-w-[1180px]">
        <div className="max-w-2xl">
          <h2 className="title text-[clamp(2.2rem,4.6vw,3.6rem)]">You can hear what it's doing.</h2>
          <p className="lede mt-5">
            Every sound is synthesized live. It comes from wherever the robot sits on your screen, and each step of a task plays one note higher, so you hear progress
            without looking.
          </p>
        </div>
        <div className="mt-14 grid gap-10 lg:grid-cols-[1fr_320px]">
          <div>
            <div role="radiogroup" aria-label="Sound pack" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {PACKS.map((p) => (
                <button
                  key={p.id}
                  role="radio"
                  aria-checked={pack === p.id}
                  onClick={() => {
                    setPack(p.id);
                    unlock();
                    setVolume(0.55);
                    packs[p.id].success();
                    setState("happy");
                  }}
                  className={`rounded-2xl p-4 text-left transition ${pack === p.id ? "bg-[var(--panel)] shadow-[0_0_0_2px_var(--accent),var(--shadow)]" : "bg-transparent shadow-[inset_0_0_0_1.5px_var(--line)] hover:bg-[var(--panel)]"}`}
                >
                  <span className="block font-semibold" style={{ fontFamily: "var(--font-display)" }}>
                    {p.name}
                  </span>
                  <span className="mt-1 block text-sm leading-snug text-[var(--muted)]">{p.blurb}</span>
                </button>
              ))}
            </div>
            <div className="mt-6 grid grid-cols-5 gap-2.5">
              {CUES.map((c) => (
                <button key={c} onClick={() => hit(c)} data-pressed={pressed === c} className="key flex h-16 flex-col items-center justify-center text-sm font-semibold">
                  {CUE_LABEL[c]}
                  {c === "tool" && <span className="text-[11px] font-normal text-[var(--muted)]">note {step + 1}</span>}
                </button>
              ))}
            </div>
          </div>
          <div className="dots flex h-[320px] items-center justify-center rounded-[28px] bg-[var(--panel)] shadow-[var(--shadow)]">
            <motion.div key={state} initial={{ scale: 0.96 }} animate={{ scale: 1 }}>
              <Robot state={state} size={150} />
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
