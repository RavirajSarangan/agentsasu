import { themes, type ThemeName } from "@sasu/brand";
import { motion } from "motion/react";
import { robotHeadShapes, type RobotHeadState } from "robot-heads";
import { useState } from "react";
import { Robot } from "../Robot";
import { cue } from "../sound";

const REACT: RobotHeadState[] = ["happy", "speaking", "thinking", "searching"];

export function Shapes() {
  const [theme, setTheme] = useState<ThemeName>("midnight");
  const [poked, setPoked] = useState<number | null>(null);
  return (
    <section className="px-4 py-28 sm:px-6">
      <div className="mx-auto max-w-6xl text-center">
        <p className="text-sm font-semibold text-[var(--accent)]">Make it yours</p>
        <h2 className="mt-2 text-4xl font-semibold tracking-tight sm:text-5xl">Four shapes. Many moods.</h2>
        <p className="mt-4 text-lg text-[var(--muted)]">Click one to say hi.</p>
        <div className="mt-8 inline-flex gap-2 rounded-full p-1.5 glass">
          {(Object.keys(themes) as ThemeName[]).map((t) => (
            <button
              key={t}
              onClick={() => {
                setTheme(t);
                cue("toggle");
              }}
              aria-label={`${themes[t].label} theme`}
              aria-pressed={theme === t}
              className="relative h-8 w-8 rounded-full"
              style={{ background: themes[t].color, boxShadow: `inset 0 0 0 3px ${themes[t].trimColor}` }}
            >
              {theme === t && <motion.span layoutId="theme-ring" className="absolute -inset-1 rounded-full border-2 border-[var(--accent)]" />}
            </button>
          ))}
        </div>
        <div className="mt-14 grid grid-cols-2 gap-6 md:grid-cols-4">
          {robotHeadShapes.map((shape, i) => (
            <motion.button
              key={shape}
              whileHover={{ y: -6 }}
              whileTap={{ scale: 0.96 }}
              onClick={() => {
                setPoked(i);
                cue(i % 2 ? "confirm" : "success", true);
                setTimeout(() => setPoked((p) => (p === i ? null : p)), 1600);
              }}
              className="glass flex flex-col items-center gap-5 rounded-3xl pb-6 pt-12"
            >
              <Robot state={poked === i ? REACT[i]! : "idle"} size={110} shape={shape} theme={theme} />
              <span className="text-sm font-medium capitalize text-[var(--muted)]">{shape}</span>
            </motion.button>
          ))}
        </div>
      </div>
    </section>
  );
}
