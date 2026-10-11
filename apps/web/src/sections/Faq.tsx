import * as Accordion from "@radix-ui/react-accordion";
import { Plus } from "lucide-react";

const QA = [
  ["Is it really free?", "Yes. Sasu is open source under the MIT license. It works with a free Google Gemini or Groq key, or fully offline with Ollama."],
  ["Does my voice go to the cloud?", "No. Wake word, speech recognition and your voiceprint all run on your Mac. With a cloud AI, only the text of your request is sent, and the privacy meter shows exactly how much."],
  ["Do I need to download anything big?", "Voice is a one-time download of about 700 MB that stays on your Mac. Spoken replies use the voices already built into macOS."],
  ["Can someone else use it on my Mac?", "Only as a guest. Other voices can ask the time or play music. Everything else needs your voice, and risky steps need Touch ID."],
  ["What if it does something wrong?", "Say “Sasu, undo” or press ⌘⌥Z and it reverses what it just did. ⌘⌥Esc stops everything instantly."],
  ["Which Macs?", "Apple Silicon Macs with macOS 13 Ventura or newer."],
  [
    "macOS says Sasu “can't be opened”?",
    "Sasu isn't notarized by Apple yet. Open System Settings → Privacy & Security, scroll down and click “Open Anyway” next to Sasu. You only need to do this once.",
  ],
];

export function Faq() {
  return (
    <section id="faq" className="px-4 py-28 sm:px-6">
      <div className="mx-auto grid max-w-[1180px] gap-12 lg:grid-cols-[0.8fr_1.2fr]">
        <h2 className="title text-[clamp(2.2rem,4.6vw,3.6rem)]">Questions people ask</h2>
        <Accordion.Root type="single" collapsible defaultValue="0" className="border-t border-[var(--line)]">
          {QA.map(([q, a], i) => (
            <Accordion.Item key={q} value={String(i)} className="border-b border-[var(--line)]">
              <Accordion.Header>
                <Accordion.Trigger className="group flex w-full items-center justify-between gap-6 py-6 text-left text-[1.15rem] font-semibold">
                  {q}
                  <Plus size={20} className="shrink-0 text-[var(--muted)] transition-transform duration-300 group-data-[state=open]:rotate-45" />
                </Accordion.Trigger>
              </Accordion.Header>
              <Accordion.Content className="overflow-hidden data-[state=closed]:animate-[collapse_200ms_ease] data-[state=open]:animate-[expand_250ms_ease]">
                <p className="max-w-[60ch] pb-6 leading-relaxed text-[var(--muted)]">{a}</p>
              </Accordion.Content>
            </Accordion.Item>
          ))}
        </Accordion.Root>
      </div>
    </section>
  );
}
