import { Check, Minus, X } from "lucide-react";
import { motion, MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Footer, Nav } from "./Layout";
import { Robot } from "./Robot";
import "./styles.css";
import { applyStoredTheme } from "./theme";

applyStoredTheme();

type Cell = "yes" | "partial" | "no" | "nd";
type RowDef = { feature: string; note?: string; cells: [Cell, Cell, Cell, Cell, Cell, Cell]; refs?: number[]; detail?: Partial<Record<number, string>> };

const COLS = ["Sasu", "Siri (macOS)", "ChatGPT desktop", "Claude desktop", "Raycast AI", "Open Interpreter"];

const ROWS: RowDef[] = [
  {
    feature: "Tamil & Tanglish voice — in and out",
    cells: ["yes", "partial", "nd", "nd", "nd", "nd"],
    refs: [1],
    detail: { 1: "Tamil mixed into English (India) requests; replies in English or Hindi" },
  },
  { feature: "Only obeys the owner's voice", note: "voiceprint checked on every command", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
  { feature: "Guest mode for other voices", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
  { feature: "Undo what the assistant did", note: "by voice or one click", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
  {
    feature: "Shows the plan / asks before acting",
    cells: ["yes", "nd", "nd", "partial", "nd", "partial"],
    refs: [3, 4],
    detail: { 3: "Asks permission before actions (research preview)", 5: "Asks you to approve code before it runs" },
  },
  { feature: "Touch ID before risky actions", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
  {
    feature: "Controls apps & files on the Mac",
    cells: ["yes", "partial", "partial", "yes", "partial", "yes"],
    refs: [2, 3, 4],
    detail: { 1: "System actions and Shortcuts", 2: "Computer-use skills; can see the active window", 3: "Research preview / beta", 4: "Commands and extensions", 5: "OS mode (keyboard, mouse, vision)" },
  },
  { feature: "Hands-free wake word", cells: ["yes", "yes", "nd", "nd", "nd", "partial"], refs: [4], detail: { 5: "Example voice interface" } },
  {
    feature: "Works offline / local AI option",
    cells: ["yes", "partial", "no", "no", "nd", "yes"],
    refs: [4],
    detail: { 1: "Some requests on-device", 5: "Ollama, LM Studio" },
  },
  {
    feature: "Free",
    cells: ["yes", "yes", "partial", "no", "partial", "yes"],
    refs: [2, 3, 5],
    detail: { 2: "Desktop voice on paid plans", 3: "Pro / Max subscribers", 4: "Free plan with limited AI messages" },
  },
  { feature: "Open source", cells: ["yes", "no", "no", "no", "no", "yes"], refs: [4] },
  { feature: "Privacy meter — shows what left your Mac", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
  { feature: "Tamper-evident action log", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
  { feature: "Tamil Panchangam (Rahu kaalam, thithi)", note: "worked out on the Mac", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
  { feature: "Scam checker for messages", note: "OTP tricks, fake bank links, “digital arrest”", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
  { feature: "Care mode for elders", note: "slow Tamil, big text, medicine check-ins, missed-dose texts", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
  { feature: "Robot that flies to the app it's using", cells: ["yes", "nd", "nd", "nd", "nd", "nd"] },
];

const SOURCES = [
  { n: 1, label: "Apple Support — Use multiple languages to speak to Siri in India", url: "https://support.apple.com/en-in/HT212537" },
  { n: 2, label: "Android Authority — ChatGPT Voice comes to the desktop app (Jul 2026)", url: "https://www.androidauthority.com/openai-chatgpt-voice-desktop-rollout-3691031/" },
  { n: 3, label: "Storyboard18 — How to use Claude's computer control on macOS", url: "https://www.storyboard18.com/digital/how-to-use-claudes-new-computer-control-feature-on-macos-tasks-permissions-limits-93068.htm" },
  { n: 4, label: "Open Interpreter on PyPI", url: "https://pypi.org/project/open-interpreter/0.2.3" },
  { n: 5, label: "Aitoolsatlas — Raycast pricing", url: "https://aitoolsatlas.ai/tools/raycast/pricing" },
];

function Mark({ cell, title }: { cell: Cell; title?: string }) {
  const map = {
    yes: { Icon: Check, color: "#30c35a", label: "Yes" },
    partial: { Icon: Minus, color: "#f0a020", label: "Partly" },
    no: { Icon: X, color: "var(--faint)", label: "No" },
    nd: { Icon: null, color: "var(--faint)", label: "Not documented" },
  }[cell];
  return (
    <span className="flex flex-col items-center gap-0.5" title={title ?? map.label}>
      {map.Icon ? (
        <span className="flex h-7 w-7 items-center justify-center rounded-full" style={{ color: map.color, background: `color-mix(in srgb, ${map.color} 14%, transparent)` }}>
          <map.Icon size={15} strokeWidth={3} />
        </span>
      ) : (
        <span className="text-[11px] leading-tight text-[var(--faint)]">not documented</span>
      )}
      {title && <span className="max-w-[120px] text-center text-[10.5px] leading-tight text-[var(--muted)]">{title}</span>}
    </span>
  );
}

function Compare() {
  return (
    <>
      <Nav home="" />
      <main className="px-4 pb-24 pt-32 sm:px-6">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col items-center text-center">
            <Robot state="happy" size={110} />
            <h1 className="mt-10 text-4xl font-semibold tracking-tight sm:text-6xl">
              Sasu <span className="text-[var(--muted)]">vs</span> the rest
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-[var(--muted)]">
              An honest look at what each Mac assistant offers. “Not documented” means we couldn't find it in public information — not that it's impossible.
            </p>
          </div>

          <div className="mt-14 overflow-x-auto rounded-3xl border border-[var(--line)]">
            <table className="w-full min-w-[860px] border-collapse text-sm">
              <thead>
                <tr className="bg-[var(--bg-2)]">
                  <th className="sticky left-0 z-10 bg-[var(--bg-2)] px-5 py-4 text-left font-semibold">Feature</th>
                  {COLS.map((c, i) => (
                    <th key={c} className={`px-3 py-4 text-center font-semibold ${i === 0 ? "text-[var(--accent)]" : ""}`}>
                      {i === 0 ? (
                        <span className="inline-flex items-center gap-1.5">
                          <Robot state="idle" size={20} halo={false} interactive={false} /> {c}
                        </span>
                      ) : (
                        c
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROWS.map((r, ri) => (
                  <motion.tr
                    key={r.feature}
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: ri * 0.02 }}
                    className="border-t border-[var(--line)]"
                  >
                    <td className="sticky left-0 z-10 bg-[var(--bg)] px-5 py-3.5">
                      <span className="font-medium">{r.feature}</span>
                      {r.note && <span className="block text-xs text-[var(--muted)]">{r.note}</span>}
                      {r.refs && <sup className="ml-1 text-[10px] text-[var(--faint)]">{r.refs.map((n) => `[${n}]`).join("")}</sup>}
                    </td>
                    {r.cells.map((cell, ci) => (
                      <td key={ci} className={`px-3 py-3.5 ${ci === 0 ? "bg-[color-mix(in_srgb,var(--accent)_6%,transparent)]" : ""}`}>
                        <Mark cell={cell} title={r.detail?.[ci]} />
                      </td>
                    ))}
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-10 grid gap-6 text-sm text-[var(--muted)] sm:grid-cols-[1fr_1fr]">
            <div>
              <h2 className="font-semibold text-[var(--text)]">Sources</h2>
              <ol className="mt-2 flex flex-col gap-1">
                {SOURCES.map((s) => (
                  <li key={s.n}>
                    [{s.n}]{" "}
                    <a href={s.url} className="underline-offset-4 hover:underline" rel="noopener">
                      {s.label}
                    </a>
                  </li>
                ))}
              </ol>
            </div>
            <div>
              <h2 className="font-semibold text-[var(--text)]">About this comparison</h2>
              <p className="mt-2 leading-relaxed">
                Compiled from public information as of October 2026. Products change quickly — if something here is wrong or out of date, tell us and we'll fix it. All
                product names belong to their owners; Sasu is not affiliated with Apple, OpenAI, Anthropic, Raycast or Open Interpreter.
              </p>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <Compare />
    </MotionConfig>
  </StrictMode>,
);
