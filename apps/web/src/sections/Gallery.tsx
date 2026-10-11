import { motion } from "motion/react";
import { useState } from "react";

/** Both theme variants are in the page; CSS shows the one for the current theme and the
 * hidden one is never fetched (display:none + loading="lazy"). */
export function Shot({ name, alt, width, height, className = "" }: { name: string; alt: string; width: number; height: number; className?: string }) {
  return (
    <>
      {(["light", "dark"] as const).map((t) => (
        <img
          key={t}
          src={`/shots/${name}-${t}.webp`}
          srcSet={`/shots/${name}-${t}.webp 1x, /shots/${name}-${t}@2x.webp 2x`}
          alt={alt}
          width={width}
          height={height}
          loading="lazy"
          decoding="async"
          className={`shot-${t} ${className}`}
        />
      ))}
    </>
  );
}

const TABS = [
  { id: "home", label: "Home", alt: "Sasu's home screen on a Mac: the robot, today's medicine reminders and a finished request to open Safari and search flights, with each step ticked." },
  { id: "memory", label: "Memory", alt: "Sasu's Memory page: encrypted facts like “Amma's BP tablet is at 8 in the morning”, searchable and deletable." },
  { id: "security", label: "Security", alt: "Sasu's Security page: voice lock active, tamper-evident log intact, trap files, intruder photo, away lock and panic word settings." },
  { id: "settings", label: "Amma mode", alt: "Sasu's Amma mode settings: medicine reminders for Amma and Appa with times, and which contact “son” means for calling by voice." },
] as const;

const STATES = [
  { id: "listening", label: "Listening", alt: "The Sasu robot listening, with a live voice meter." },
  { id: "thinking", label: "Thinking", alt: "The Sasu robot thinking about “Hey Sasu, play some Ilaiyaraaja”." },
  { id: "dancing", label: "Music on", alt: "The Sasu robot smiling with the song chip “Ilaiyaraaja hits”." },
  { id: "amma", label: "Amma mode", alt: "The Sasu robot asking in large Tamil text: “அம்மா, BP மாத்திரை நேரம். சாப்பிட்டீங்களா?”" },
] as const;

export function Gallery() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("home");
  const current = TABS.find((t) => t.id === tab)!;
  return (
    <section id="screens" className="bg-[var(--bg-2)] px-4 py-24 sm:px-6">
      <div className="mx-auto max-w-[1180px]">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h2 className="title text-[clamp(2rem,4vw,3rem)]">See it on your Mac.</h2>
            <p className="lede mt-3">Real screens from the app, not mock-ups.</p>
          </div>
          <div role="tablist" aria-label="Screens" className="inline-flex flex-wrap rounded-full bg-[var(--bg)] p-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                id={`tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls="screen-panel"
                onClick={() => setTab(t.id)}
                onKeyDown={(e) => {
                  const i = TABS.findIndex((x) => x.id === tab);
                  const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
                  if (!step) return;
                  const next = TABS[(i + step + TABS.length) % TABS.length]!;
                  setTab(next.id);
                  document.getElementById(`tab-${next.id}`)?.focus();
                }}
                tabIndex={tab === t.id ? 0 : -1}
                className="relative rounded-full px-4 py-2 text-sm font-semibold"
              >
                {tab === t.id && <motion.span layoutId="screen-tab" className="absolute inset-0 rounded-full bg-[var(--panel)] shadow-[var(--shadow-sm)]" />}
                <span className="relative">{t.label}</span>
              </button>
            ))}
          </div>
        </div>

        <figure id="screen-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="mt-10 overflow-hidden rounded-[18px] bg-[var(--panel)] shadow-[var(--shadow-lg)] ring-1 ring-[var(--line)]">
          <div aria-hidden className="flex h-9 items-center gap-2 border-b border-[var(--line)] px-4">
            <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
            <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
            <span className="h-3 w-3 rounded-full bg-[#28c840]" />
            <span className="ml-3 text-xs font-medium text-[var(--muted)]">Sasu</span>
          </div>
          <motion.div key={tab} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }}>
            <Shot name={current.id} alt={current.alt} width={1080} height={880} className="block h-auto w-full" />
          </motion.div>
        </figure>

        <ul className="mt-10 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {STATES.map((s) => (
            <li key={s.id} className="flex flex-col items-center gap-2 overflow-hidden rounded-[18px] bg-[var(--panel)] px-2 pt-2 pb-4 shadow-[var(--shadow-sm)]">
              <Shot name={`robot-${s.id}`} alt={s.alt} width={270} height={285} className="h-auto w-full max-w-[220px]" />
              <span className="text-sm font-semibold text-[var(--muted)]">{s.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
