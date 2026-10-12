import { packs, setVolume, unlock } from "@sasu/brand";
import { Hand, Laugh, Moon, Music, Sparkles, Vibrate } from "lucide-react";
import { AnimatePresence, motion, useAnimationControls } from "motion/react";
import type { RobotHeadState } from "robot-heads";
import { useEffect, useRef, useState } from "react";
import { Robot } from "../Robot";

const JOKES = [
  { text: "Why did the robot go to the beach? To recharge its batteries. Seri, seri, naane sirikkiren.", lang: "en" as const },
  { text: "என் Wi-Fi password என்ன தெரியுமா? 'தெரியாது'. அதான் password!", lang: "ta" as const },
  { text: "I tried to delete your Downloads folder once. Then I remembered undo exists. Bayam illa.", lang: "en" as const },
];

type Mode = "idle" | "pet" | "dizzy" | "dance" | "night" | "joke" | "break";

const MODE_STATE: Record<Mode, RobotHeadState> = {
  idle: "idle",
  pet: "happy",
  dizzy: "error",
  dance: "happy",
  night: "sleeping",
  joke: "speaking",
  break: "listening",
};

function play(fn: () => void) {
  unlock();
  setVolume(0.55);
  fn();
}

export function Fun() {
  const [mode, setMode] = useState<Mode>("idle");
  const [joke, setJoke] = useState(0);
  const controls = useAnimationControls();
  const holdTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (mode !== "dance") return;
    void controls.start({ y: [0, -14, 0], rotate: [0, -6, 6, 0], transition: { duration: 0.55, repeat: Infinity } });
    const beat = setInterval(() => play(() => packs.toon.tool({ step: Math.floor(Math.random() * 6) })), 550);
    return () => {
      clearInterval(beat);
      controls.stop();
      void controls.start({ y: 0, rotate: 0 });
    };
  }, [mode, controls]);

  const set = (m: Mode) => {
    setMode(m);
    if (m === "dizzy") {
      play(() => packs.toon.error());
      void controls.start({ x: [0, -18, 16, -12, 10, -6, 0], rotate: [0, -12, 10, -8, 6, 0], transition: { duration: 0.7 } });
    }
    if (m === "night") play(() => packs.toon.sleep());
    if (m === "joke") {
      setJoke((j) => (j + 1) % JOKES.length);
      play(() => packs.toon.listen());
    }
    if (m === "break") play(() => packs.kovil.confirm());
  };

  const bubble: Record<Mode, { text: string; lang?: "ta" | "en" } | null> = {
    idle: null,
    pet: { text: "Hehe. That tickles. 💙" },
    dizzy: { text: "Ayyo! Ellaam suthudhu…", lang: "en" },
    dance: { text: "♪ Spotify is on. Can't stop, won't stop." },
    night: { text: "It's late. Thoongunga… I'll keep it quiet. 😴" },
    joke: JOKES[joke]!,
    break: { text: "You've been at it for an hour. Konjam thanni kudinga, stretch pannunga." },
  };

  const ITEMS: { m: Mode; Icon: typeof Hand; label: string; hint: string }[] = [
    { m: "pet", Icon: Hand, label: "Pet it", hint: "Click and hold the robot" },
    { m: "dizzy", Icon: Vibrate, label: "Shake it", hint: "Drag it around fast" },
    { m: "dance", Icon: Music, label: "Play music", hint: "It dances to Spotify and Music" },
    { m: "joke", Icon: Laugh, label: "“Joke sollu”", hint: "English or Tamil jokes" },
    { m: "night", Icon: Moon, label: "Late night", hint: "Yawns and talks quieter after 11 pm" },
    { m: "break", Icon: Sparkles, label: "Break buddy", hint: "Water and stretch reminders" },
  ];

  const b = bubble[mode];
  return (
    <section id="fun" className="cv px-4 py-16 sm:px-6 sm:py-28">
      <div className="mx-auto grid max-w-[1180px] grid-cols-[minmax(0,1fr)] items-center gap-14 lg:grid-cols-[1fr_1fr]">
        <div>
          <h2 className="title text-[clamp(2.2rem,4.6vw,3.6rem)]">Serious about security. Not serious about everything.</h2>
          <p className="lede mt-5">Sasu is a little coworker, not a search box. Poke it and see.</p>
          <div className="mt-9 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {ITEMS.map(({ m, Icon, label, hint }) => (
              <button
                key={m}
                onClick={() => set(mode === m && m === "dance" ? "idle" : m)}
                className={`rounded-2xl p-4 text-left transition ${mode === m ? "bg-[var(--panel)] shadow-[0_0_0_2px_var(--accent),var(--shadow)]" : "shadow-[inset_0_0_0_1.5px_var(--line)] hover:bg-[var(--panel)]"}`}
              >
                <Icon size={19} className="text-[var(--accent)]" />
                <span className="mt-2.5 block font-semibold">{label}</span>
                <span className="mt-0.5 block text-[0.85rem] leading-snug text-[var(--muted)]">{hint}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="dots relative flex h-[440px] flex-col items-center justify-end rounded-[32px] bg-[var(--panel)] pb-14 shadow-[var(--shadow-lg)]">
          <AnimatePresence mode="wait">
            {b && (
              <motion.p
                key={mode + joke}
                lang={b.lang}
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6 }}
                className="mb-6 max-w-[80%] rounded-[22px] bg-[var(--bg)] px-5 py-3.5 text-center text-[1.05rem] leading-snug shadow-[var(--shadow-sm)]"
              >
                {b.text}
              </motion.p>
            )}
          </AnimatePresence>
          <motion.div
            animate={controls}
            onPointerDown={() => {
              holdTimer.current = setTimeout(() => {
                set("pet");
                play(() => packs.soft.success());
              }, 350);
            }}
            onPointerUp={() => clearTimeout(holdTimer.current)}
            onPointerLeave={() => clearTimeout(holdTimer.current)}
            className="cursor-grab touch-none select-none active:cursor-grabbing"
            title="Click and hold to pet"
          >
            <Robot state={MODE_STATE[mode]} size={170} lang={b?.lang === "ta" ? "ta" : "en"} />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
