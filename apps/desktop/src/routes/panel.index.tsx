import { createFileRoute, Link } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { ArrowUpRight, Brain, Check, ChevronDown, ListChecks, LoaderCircle, Mic, SendHorizontal, ShieldAlert, Square, TriangleAlert, Undo2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import { send } from "../agent/connection";
import { agentStore } from "../agent/store";
import { buildTimeline, type TimelineItem, type Turn } from "../agent/timeline";
import { Halo } from "../robot/Halo";
import { CareCard } from "../settings/CareSettings";
import { WatchCard } from "../settings/WatchCard";
import { SasuRobot } from "../robot/SasuRobot";
import { STATE_STYLE } from "../robot/stateStyle";
import { play } from "../sound/player";
import { Button } from "../ui/Button";
import { Badge, Card, Kbd } from "../ui/Card";

export const Route = createFileRoute("/panel/")({ component: Home });

const EXAMPLES = [
  { text: "Open Safari", lang: "en" },
  { text: "Downloads la irukura PDF ellam list pannu", lang: "en" },
  { text: "Volume 30 aakku", lang: "en" },
  { text: "Remind me to call Amma", lang: "en" },
  { text: "Spotify-ல next song போடு", lang: "ta" },
  { text: "Sasu, undo", lang: "en" },
] as const;

function Home() {
  return (
    <div className="flex flex-col gap-6">
      <BrainBanner />
      <Hero />
      <CareCard />
      <WatchCard />
      <CommandBar />
      <Timeline />
      <DevLog />
    </div>
  );
}

/** Until an AI brain is connected Sasu can't act, so say so plainly. */
function BrainBanner() {
  const brain = useSelector(agentStore, (s) => s.brain);
  const demo = useSelector(agentStore, (s) => s.demo);
  if (!brain || brain.ready) return null;
  return (
    <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="flex items-center gap-3.5 px-5 py-3.5" style={{ boxShadow: "0 0 0 1px var(--accent-glow), var(--shadow)" }}>
        <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[var(--accent)] text-white">
          <Brain size={18} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-semibold">Connect Sasu's brain — it's free</p>
          <p className="text-[12px] text-[var(--muted)]">
            {demo ? "You're in demo mode. " : ""}Paste a free Google Gemini key and Sasu starts doing real work on your Mac.
          </p>
        </div>
        <Link to="/panel/settings" hash="brain">
          <Button variant="primary" size="sm">
            Set up <ArrowUpRight size={13} />
          </Button>
        </Link>
      </Card>
    </motion.div>
  );
}

function Hero() {
  const view = useSelector(agentStore, (s) => s.view);
  const s = STATE_STYLE[view.state];
  const busy = view.state !== "idle" && view.state !== "sleeping" && view.state !== "happy";

  return (
    <Card className="relative flex items-center gap-8 overflow-visible px-8 py-7">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[var(--radius-lg)] opacity-70"
        style={{ background: `radial-gradient(120% 140% at 0% 0%, color-mix(in srgb, ${s.color} 12%, transparent), transparent 60%)`, transition: "background 500ms" }}
      />
      <div className="relative shrink-0">
        <Halo state={view.state} size={120} />
        <SasuRobot size={120} />
      </div>
      <div className="relative min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-[12px] font-semibold" style={{ color: s.color }}>
          <s.Icon size={14} />
          {s.label}
          {view.activeTool && <span className="font-mono font-normal text-[var(--muted)]">· {view.activeTool}</span>}
        </div>
        <h1 className="text-[24px] font-semibold leading-tight tracking-tight">
          {view.caption ? (
            <span lang={view.lang} className="line-clamp-2">
              {view.caption}
            </span>
          ) : (
            <>
              Hey, I'm Sasu. <span className="text-[var(--muted)]">What should I do?</span>
            </>
          )}
        </h1>
        <div className="mt-5 flex items-center gap-2">
          <Button variant="primary" size="lg" onClick={() => send({ type: "ptt_start" })}>
            <Mic size={16} /> Talk
          </Button>
          <Button size="lg" disabled={!busy} onClick={() => send({ type: "cancel" })}>
            <Square size={13} fill="currentColor" /> Stop
          </Button>
          <span className="ml-2 flex items-center gap-1 text-[11.5px] text-[var(--muted)]">
            <Kbd>⌥</Kbd>
            <Kbd>Space</Kbd> talk · <Kbd>⌘</Kbd>
            <Kbd>⌥</Kbd>
            <Kbd>Esc</Kbd> stop
          </span>
        </div>
      </div>
    </Card>
  );
}

function CommandBar() {
  const [text, setText] = useState("");
  const connected = useSelector(agentStore, (s) => s.connection === "open");

  const submit = (value: string) => {
    const v = value.trim();
    if (v && send({ type: "text_command", text: v })) {
      play("click");
      setText("");
    }
  };

  return (
    <div className="flex flex-col gap-2.5">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(text);
        }}
        className="flex h-11 items-center gap-2 rounded-[12px] bg-[var(--surface)] pl-4 pr-1.5 shadow-[var(--shadow)] transition-shadow focus-within:shadow-[0_0_0_3px_var(--accent-glow),var(--shadow)]"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type a command — English, தமிழ், or Tanglish"
          className="h-full flex-1 bg-transparent text-[14px] outline-none placeholder:text-[var(--faint)]"
          disabled={!connected}
        />
        <Button type="submit" variant="primary" size="sm" quiet disabled={!text.trim() || !connected} aria-label="Send">
          <SendHorizontal size={14} />
        </Button>
      </form>
      <div className="flex flex-wrap gap-1.5">
        {EXAMPLES.map((ex) => (
          <motion.button
            key={ex.text}
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.97 }}
            lang={ex.lang}
            onClick={() => submit(ex.text)}
            className="rounded-full bg-[var(--surface)] px-3 py-1 text-[12px] text-[var(--muted)] shadow-[var(--shadow-sm)] hover:text-[var(--text)]"
          >
            {ex.text}
          </motion.button>
        ))}
      </div>
    </div>
  );
}

function Timeline() {
  const log = useSelector(agentStore, (s) => s.log);
  const turns = useMemo(() => buildTimeline(log), [log]);

  return (
    <section className="flex flex-col gap-3">
      <h2 className="px-1 text-[13px] font-semibold">Conversation</h2>
      {turns.length === 0 ? (
        <Card className="px-6 py-10 text-center text-[13px] text-[var(--muted)]">Nothing yet. Say “Hey Sasu” or try an example above.</Card>
      ) : (
        <div className="flex flex-col gap-3">
          <AnimatePresence initial={false}>
            {turns.slice(0, 12).map((t) => (
              <TurnCard key={t.id} turn={t} />
            ))}
          </AnimatePresence>
        </div>
      )}
    </section>
  );
}

function TurnCard({ turn }: { turn: Turn }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0 }}
      transition={{ type: "spring", stiffness: 400, damping: 34 }}
    >
      <Card className="flex flex-col gap-2.5 px-5 py-4">
        <div className="flex items-center justify-between text-[11px] text-[var(--faint)]">
          <span>{new Date(turn.startedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
          {turn.status === "active" ? (
            <Badge color="var(--accent)">
              <LoaderCircle size={10} className="animate-spin" /> In progress
            </Badge>
          ) : turn.status === "ok" ? (
            <Badge color="var(--ok)">
              <Check size={10} strokeWidth={3} /> Done
            </Badge>
          ) : (
            <Badge color="var(--danger)">
              <X size={10} strokeWidth={3} /> Stopped
            </Badge>
          )}
        </div>
        {turn.items.map((it, i) => (
          <Item key={i} item={it} />
        ))}
        {(turn.undo || turn.privacy) && (
          <div className="mt-1 flex flex-wrap items-center gap-2 border-t border-[var(--hairline)] pt-2.5 text-[11px] text-[var(--muted)]">
            {turn.privacy && (
              <span title="Everything this turn sent off your Mac">
                ⇡ {turn.privacy.chars.toLocaleString()} chars to {turn.privacy.provider} · 0 audio · 0 files
              </span>
            )}
            {turn.undo && (
              <Button
                size="sm"
                className="ml-auto"
                disabled={turn.undo.used}
                onClick={() => send({ type: "undo", turn_id: turn.undo!.turnId })}
                title={turn.undo.actions.join(", ")}
              >
                <Undo2 size={12} /> {turn.undo.used ? "Undone" : `Undo ${turn.undo.actions.length} change${turn.undo.actions.length > 1 ? "s" : ""}`}
              </Button>
            )}
          </div>
        )}
      </Card>
    </motion.div>
  );
}

function Item({ item }: { item: TimelineItem }) {
  switch (item.kind) {
    case "user":
      return (
        <div className="flex justify-end">
          <p lang={item.lang} className="max-w-[80%] rounded-[16px] rounded-br-[5px] bg-[var(--accent)] px-3.5 py-2 text-[13px] text-white">
            {item.text}
          </p>
        </div>
      );
    case "sasu":
      return (
        <div className="flex items-end gap-2">
          <SasuRobot size={22} antenna={false} floorShadow={false} interactive={false} state="speaking" />
          <p lang={item.lang} className="max-w-[80%] rounded-[16px] rounded-bl-[5px] bg-[var(--sunken)] px-3.5 py-2 text-[13px]">
            {item.text}
          </p>
        </div>
      );
    case "tool":
      return (
        <div className="ml-7 flex items-center gap-2 border-l-2 border-[var(--hairline-strong)] pl-3 text-[12px]">
          {item.status === "running" ? (
            <LoaderCircle size={13} className="animate-spin text-[var(--accent)]" />
          ) : item.status === "ok" ? (
            <Check size={13} strokeWidth={3} className="text-[var(--ok)]" />
          ) : (
            <X size={13} strokeWidth={3} className="text-[var(--danger)]" />
          )}
          <code className="font-mono text-[11.5px]">{item.name}</code>
          {item.summary && <span className="text-[var(--muted)]">— {item.summary}</span>}
          {item.risk !== "safe" && <Badge color={item.risk === "dangerous" ? "var(--danger)" : "var(--warn)"}>{item.risk}</Badge>}
        </div>
      );
    case "confirm":
      return (
        <div className="ml-7 flex items-center gap-2 rounded-[10px] px-3 py-2 text-[12.5px]" style={{ background: "color-mix(in srgb, var(--warn) 10%, transparent)" }}>
          <ShieldAlert size={14} style={{ color: item.risk === "dangerous" ? "var(--danger)" : "var(--warn)" }} />
          {item.prompt}
          {!item.answered && <span className="ml-auto text-[11px] text-[var(--muted)]">waiting…</span>}
        </div>
      );
    case "error":
      return (
        <div className="ml-7 flex items-center gap-2 text-[12.5px] text-[var(--danger)]">
          <TriangleAlert size={13} /> {item.message}
        </div>
      );
    case "plan":
      return (
        <div className="ml-7 rounded-[10px] bg-[var(--sunken)] px-3 py-2 text-[12.5px]">
          <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold text-[var(--accent)]">
            <ListChecks size={12} /> Plan
          </p>
          <ol className="list-decimal pl-5 text-[var(--muted)]">
            {item.steps.map((st, i) => (
              <li key={i}>{st}</li>
            ))}
          </ol>
        </div>
      );
    case "undone":
      return (
        <div className="ml-7 flex items-center gap-2 text-[12.5px]" style={{ color: item.ok ? "var(--ok)" : "var(--warn)" }}>
          <Undo2 size={13} /> Undone: {item.summary}
        </div>
      );
  }
}

function DevLog() {
  const [open, setOpen] = useState(false);
  const log = useSelector(agentStore, (s) => s.log);
  return (
    <section>
      <button onClick={() => setOpen((o) => !o)} className="flex items-center gap-1 px-1 text-[12px] text-[var(--muted)] hover:text-[var(--text)]">
        <motion.span animate={{ rotate: open ? 0 : -90 }}>
          <ChevronDown size={13} />
        </motion.span>
        Developer log ({log.length})
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.ol
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-2 max-h-72 overflow-y-auto rounded-[12px] bg-[var(--sunken)] font-mono text-[11px]"
          >
            {log.map(({ at, event }, i) => (
              <li key={`${at}-${i}`} className="border-b border-[var(--hairline)] px-3 py-1">
                <span className="text-[var(--faint)]">{new Date(at).toLocaleTimeString()}</span> {JSON.stringify(event)}
              </li>
            ))}
          </motion.ol>
        )}
      </AnimatePresence>
    </section>
  );
}
