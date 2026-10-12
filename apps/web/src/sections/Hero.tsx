import { Languages, Lock, ShieldCheck, Undo2 } from "lucide-react";
import { DownloadButton, StarButton } from "../Layout";
import { Desk } from "./Desk";

const TRUST = [
  { Icon: Languages, text: "English · தமிழ் · Tanglish" },
  { Icon: Lock, text: "Voice stays on your Mac" },
  { Icon: ShieldCheck, text: "Only your voice" },
  { Icon: Undo2, text: "Undo anything" },
];

export function Hero() {
  return (
    <section id="top" className="relative overflow-x-clip px-4 pb-12 pt-28 sm:px-6 sm:pb-24 sm:pt-36">
      <div aria-hidden className="dots pointer-events-none absolute inset-x-0 top-0 h-[560px] [mask-image:linear-gradient(to_bottom,black,transparent)]" />
      {/* soft aurora behind the headline */}
      <div aria-hidden className="aurora pointer-events-none absolute left-1/2 top-0 h-[520px] w-[min(1100px,140vw)] -translate-x-1/2" />
      <div className="relative mx-auto max-w-[1180px]">
        <div className="grid items-end gap-10 lg:grid-cols-[1.25fr_1fr]">
          <h1 className="rise display text-[clamp(3rem,8.4vw,6.6rem)]"
          >
            Talk to your Mac.
            <span lang="ta" className="mt-4 block text-[0.42em] font-semibold leading-[1.25] tracking-normal text-[var(--muted)]">
              உங்க Mac-கிட்ட பேசுங்க.
            </span>
          </h1>
          <div className="rise flex flex-col gap-6 pb-2" style={{ animationDelay: "0.12s" }}>
            <p className="lede">
              Sasu is a little robot that lives in the corner of your screen. Say “Hey Sasu” in English, Tamil or a mix of both, and it opens apps, sorts files and
              changes settings. It only works for your voice, and anything it does can be undone.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <DownloadButton />
              <StarButton size="lg" />
            </div>
            <ul className="flex flex-wrap gap-2" aria-label="Highlights">
              {TRUST.map(({ Icon, text }) => (
                <li key={text} className="chip">
                  <Icon size={14} className="text-[var(--accent)]" /> {text}
                </li>
              ))}
            </ul>
            <p className="text-sm text-[var(--faint)]">A free, open-source voice assistant for Mac, in English and தமிழ். Apple Silicon, macOS 13 or later.</p>
          </div>
        </div>
        <div className="rise mt-12 sm:mt-16" style={{ animationDelay: "0.25s" }}>
          <Desk />
        </div>
      </div>
    </section>
  );
}
