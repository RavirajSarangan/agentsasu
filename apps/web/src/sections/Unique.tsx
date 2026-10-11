import { Eye, Languages, ListChecks, Navigation, Undo2, UserRound, Wand2 } from "lucide-react";
import { motion } from "motion/react";
import type { RobotHeadState } from "robot-heads";
import { useState } from "react";
import { Robot } from "../Robot";
import { cue } from "../sound";

const ITEMS: { Icon: typeof Undo2; title: string; body: string; say: string; state: RobotHeadState; tone: string }[] = [
  {
    Icon: Undo2,
    title: "“Sasu, undo”",
    body: "Every change Sasu makes is recorded with how to reverse it. Moved the wrong files? Changed a setting? One sentence puts it back.",
    say: "Sasu, undo",
    state: "happy",
    tone: "#30c35a",
  },
  {
    Icon: ListChecks,
    title: "See the plan first",
    body: "For anything with several steps, Sasu shows exactly what it's about to do and waits for your go.",
    say: "Tidy my Downloads",
    state: "thinking",
    tone: "#f0a020",
  },
  {
    Icon: Navigation,
    title: "The robot goes where it works",
    body: "Sasu glides over to the app it's working in, so you always see what it's touching — then flies home.",
    say: "Open Safari",
    state: "working",
    tone: "var(--accent)",
  },
  {
    Icon: Languages,
    title: "Speaks your mix",
    body: "Talk in English, தமிழ் or Tanglish. Sasu answers in the same mix, switching between Tamil and English voices mid-sentence.",
    say: "Spotify-ல next song போடு",
    state: "speaking",
    tone: "#a35cf0",
  },
  {
    Icon: UserRound,
    title: "Guest mode",
    body: "Your voice gets full power. Anyone else can only ask the time or play music — or nothing at all, your choice.",
    say: "(a stranger) Delete my files",
    state: "error",
    tone: "#ef4444",
  },
  {
    Icon: Eye,
    title: "Privacy meter",
    body: "After every request: exactly how many characters left your Mac, to which AI. Audio and voiceprint never leave.",
    say: "⇡ 214 chars · 0 audio · 0 files",
    state: "searching",
    tone: "#1fb6d8",
  },
  {
    Icon: Wand2,
    title: "Teach it a routine",
    body: "Do something once, then “Sasu, save that as morning”. Next time just say “Sasu, morning”.",
    say: "Sasu, save that as morning",
    state: "listening",
    tone: "#30c35a",
  },
];

export function Unique() {
  const [active, setActive] = useState(0);
  const item = ITEMS[active]!;
  return (
    <section id="unique" className="px-4 py-28 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <p className="text-sm font-semibold text-[var(--accent)]">Only on Sasu</p>
        <h2 className="mt-2 max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">Things no other Mac assistant does together.</h2>
        <div className="mt-14 grid gap-8 lg:grid-cols-[1fr_380px]">
          <div className="grid gap-3 sm:grid-cols-2">
            {ITEMS.map(({ Icon, title, body, tone }, i) => (
              <motion.button
                key={title}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ delay: (i % 2) * 0.06 }}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onClick={() => {
                  setActive(i);
                  cue("toggle", true);
                }}
                className={`glass rounded-3xl p-5 text-left transition ${active === i ? "ring-2 ring-[var(--accent)]" : ""}`}
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-2xl" style={{ color: tone, background: `color-mix(in srgb, ${tone} 14%, transparent)` }}>
                  <Icon size={20} />
                </span>
                <h3 className="mt-4 font-semibold tracking-tight">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-[var(--muted)]">{body}</p>
              </motion.button>
            ))}
          </div>
          <div className="lg:sticky lg:top-28 lg:h-[420px]">
            <div className="glass flex h-[360px] flex-col items-center justify-end gap-6 rounded-3xl pb-10 lg:h-full">
              <motion.p
                key={item.say}
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                className="glass max-w-[85%] rounded-2xl px-4 py-2.5 text-center text-[15px]"
              >
                {item.say}
              </motion.p>
              <Robot state={item.state} size={150} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
