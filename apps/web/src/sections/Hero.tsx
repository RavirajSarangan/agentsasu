import { Check, LoaderCircle } from "lucide-react";
import { DownloadButton, GithubButton } from "../Layout";
import { AnimatePresence, motion } from "motion/react";
import type { RobotHeadState } from "robot-heads";
import { useEffect, useState } from "react";
import { VERSION } from "../config";
import { Robot, STATE_COLOR } from "../Robot";
import { cue } from "../sound";
import type { Cue } from "@sasu/brand";

type Beat = { state: RobotHeadState; chip: string; text?: string; tool?: string; done?: string; lang?: "en" | "ta"; ms: number; cue?: Cue };

const SCRIPT: Beat[] = [
  { state: "idle", chip: "Ready", ms: 1600 },
  { state: "listening", chip: "Listening", text: "Hey Sasu…", ms: 1300, cue: "wake" },
  { state: "thinking", chip: "Thinking", text: "Downloads la irukura PDF ellam list pannu", ms: 1500, cue: "think" },
  { state: "searching", chip: "Searching", text: "Downloads la irukura PDF ellam list pannu", tool: "files.find", ms: 1500, cue: "tool" },
  { state: "speaking", chip: "Speaking", text: "Downloads-ல 7 PDF இருக்கு. Open பண்ணவா?", lang: "ta", done: "7 files", ms: 2600 },
  { state: "happy", chip: "Done", ms: 1400, cue: "success" },
  { state: "listening", chip: "Listening", text: "Set volume to 30 and open Spotify", ms: 1500, cue: "wake" },
  { state: "working", chip: "Working", text: "Set volume to 30 and open Spotify", tool: "apps.open", ms: 1500, cue: "tool" },
  { state: "speaking", chip: "Speaking", text: "Volume is 30 and Spotify is playing.", done: "Spotify opened", ms: 2400 },
  { state: "happy", chip: "Done", ms: 1500, cue: "success" },
];

export function Hero() {
  const [i, setI] = useState(0);
  const beat = SCRIPT[i]!;

  useEffect(() => {
    if (beat.cue) cue(beat.cue);
    const t = setTimeout(() => setI((n) => (n + 1) % SCRIPT.length), beat.ms);
    return () => clearTimeout(t);
  }, [i, beat]);

  return (
    <section id="top" className="relative overflow-x-clip px-4 pb-24 pt-32 sm:px-6 sm:pt-40">
      <div aria-hidden className="grid-bg pointer-events-none absolute inset-0 -z-10" />
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-24 -z-10 h-[520px] w-[820px] max-w-[140vw] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
        style={{ background: "radial-gradient(closest-side, var(--glow), transparent)" }}
      />
      <div className="mx-auto grid max-w-6xl items-center gap-16 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <motion.span
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass mb-6 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium text-[var(--muted)]"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#30c35a]" /> v{VERSION} · open source · macOS
          </motion.span>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="text-[44px] font-semibold leading-[1.02] tracking-[-0.035em] sm:text-6xl lg:text-7xl"
          >
            Your Mac,
            <br />
            by voice.
            <br />
            <span className="gradient-text">
              In English & <span lang="ta">தமிழ்</span>.
            </span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.6 }}
            className="mt-6 max-w-lg text-lg leading-relaxed text-[var(--muted)]"
          >
            Sasu is a little robot that lives on your desktop. Say <b className="text-[var(--text)]">“Hey Sasu”</b> and it opens apps, finds files and
            changes settings — it only listens to <i>you</i>, and anything it does can be undone.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }} className="mt-9 flex flex-wrap gap-3">
            <DownloadButton size="lg" />
            <GithubButton />
          </motion.div>
          <p className="mt-4 text-xs text-[var(--faint)]">Apple Silicon · macOS 13+ · Free forever</p>
        </div>

        {/* live demo */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2, type: "spring", stiffness: 120, damping: 16 }}
          className="relative mx-auto flex h-[420px] w-full max-w-[440px] flex-col items-center justify-end pb-6"
        >
          <AnimatePresence mode="wait">
            {beat.text && (
              <motion.div
                key={beat.text + beat.state}
                initial={{ opacity: 0, y: 12, scale: 0.94 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.97 }}
                transition={{ type: "spring", stiffness: 380, damping: 30 }}
                lang={beat.lang}
                className="glass relative mb-4 w-[300px] max-w-full rounded-2xl px-4 py-3 text-center text-[15px] leading-snug"
              >
                {beat.text}
                {beat.tool && (
                  <p className="mt-1.5 flex items-center justify-center gap-1.5 font-mono text-xs text-[var(--muted)]">
                    <LoaderCircle size={12} className="animate-spin" /> {beat.tool}
                  </p>
                )}
                {beat.done && (
                  <p className="mt-1.5 flex items-center justify-center gap-1 text-xs font-medium text-[#30c35a]">
                    <Check size={13} strokeWidth={3} /> {beat.done}
                  </p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
          <motion.div
            layout
            className="glass mb-6 flex h-7 items-center gap-1.5 rounded-full px-3 text-xs font-semibold"
            style={{ color: STATE_COLOR[beat.state] }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: STATE_COLOR[beat.state] }} />
            {beat.chip}
          </motion.div>
          <Robot state={beat.state} size={190} lang={beat.lang ?? "en"} />
        </motion.div>
      </div>
    </section>
  );
}
