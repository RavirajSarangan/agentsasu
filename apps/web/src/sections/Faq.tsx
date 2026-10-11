import { ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

const QA = [
  ["Is it really free?", "Yes. Sasu is open source under the MIT license. It works with a free Google Gemini or Groq key, or fully offline with Ollama."],
  ["Do I need to download anything big?", "Voice is a one-time ~700 MB download (speech recognition, wake word, voice ID) that stays on your Mac. Spoken replies use the voices already built into macOS."],
  ["Does my voice go to the cloud?", "No. The wake word, speech-to-text and your voiceprint run on your Mac. With a cloud AI model, only the text of your request is sent."],
  ["Can someone else use it on my Mac?", "No. Sasu only obeys your enrolled voice, stops listening when your Mac is locked, and needs Touch ID for anything risky."],
  ["Which languages?", "English and Tamil — including Tanglish. Sasu replies in the language you spoke."],
  ["Which Macs?", "Apple Silicon Macs on macOS 13 Ventura or newer."],
  ["What if it does something wrong?", "Say “Sasu, undo” (or press ⌘⌥Z) and it reverses what it just did. ⌘⌥Esc stops everything instantly, and every action is in a tamper-evident log."],
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" className="border-t border-[var(--line)] px-4 py-28 sm:px-6">
      <div className="mx-auto max-w-3xl">
        <h2 className="text-center text-4xl font-semibold tracking-tight sm:text-5xl">Questions</h2>
        <div className="mt-12 divide-y divide-[var(--line)] border-y border-[var(--line)]">
          {QA.map(([q, a], i) => (
            <div key={q}>
              <button onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i} className="flex w-full items-center justify-between gap-4 py-5 text-left text-lg font-medium">
                {q}
                <motion.span animate={{ rotate: open === i ? 180 : 0 }} className="shrink-0 text-[var(--muted)]">
                  <ChevronDown size={20} />
                </motion.span>
              </button>
              <AnimatePresence initial={false}>
                {open === i && (
                  <motion.p
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25 }}
                    className="overflow-hidden pb-5 leading-relaxed text-[var(--muted)]"
                  >
                    {a}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
