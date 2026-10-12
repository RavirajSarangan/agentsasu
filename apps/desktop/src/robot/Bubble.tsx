import { useSelector } from "@tanstack/react-store";
import { Check, FingerprintPattern, ListChecks, LoaderCircle, ShieldAlert, ShieldCheck, Undo2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { send } from "../agent/connection";
import { agentStore, onAgentEvent } from "../agent/store";
import { play } from "../sound/player";

type Flash = { ok: boolean; summary: string };

/** Glass caption under the robot: streaming words, tool progress and yes/no prompts. */
export function Bubble() {
  const { caption, big, scam, confirm, activeTool, lang, auth, plan, undo, state } = useSelector(agentStore, (s) => s.view);
  const [flash, setFlash] = useState<Flash | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const off = onAgentEvent((e) => {
      if (e.type !== "tool_end") return;
      setFlash({ ok: e.ok, summary: e.summary });
      clearTimeout(timer);
      timer = setTimeout(() => setFlash(null), 1100);
    });
    return () => {
      off();
      clearTimeout(timer);
    };
  }, []);

  const text = confirm?.prompt ?? caption;
  const offerUndo = undo && (state === "happy" || state === "idle") && !confirm;
  const show = Boolean(text || activeTool || flash || plan || offerUndo);
  const dangerous = confirm?.risk === "dangerous";

  const answer = (approved: boolean) => {
    if (!confirm) return;
    play(approved ? "toggle" : "click");
    send({ type: "confirm_response", id: confirm.id, approved });
  };

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          key="bubble"
          initial={{ opacity: 0, y: 10, scale: 0.92 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 6, scale: 0.95, transition: { duration: 0.18 } }}
          transition={{ type: "spring", stiffness: 420, damping: 30 }}
          lang={lang}
          className={`glass relative rounded-[16px] px-3.5 py-2.5 text-center ${big ? "w-[256px] text-[17px] font-medium leading-[1.35]" : "w-[224px] text-[12.5px] leading-[1.4]"}`}
          style={dangerous ? { borderColor: "var(--danger)", boxShadow: "0 0 0 1px var(--danger), var(--shadow-lg)" } : undefined}
        >
          {auth && (
            <motion.div
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="mx-auto mb-1.5 flex h-9 w-9 items-center justify-center rounded-full text-[var(--danger)]"
              style={{ background: "color-mix(in srgb, var(--danger) 14%, transparent)" }}
            >
              <FingerprintPattern size={20} className="breathe" />
            </motion.div>
          )}
          {plan && (
            <ol className="mb-1.5 flex flex-col gap-1 text-left text-[11.5px]">
              <li className="flex items-center gap-1 font-semibold text-[var(--accent)]">
                <ListChecks size={12} /> {lang === "ta" ? "இதை செய்யப்போறேன்" : "Here's my plan"}
              </li>
              {plan.map((step, i) => (
                <motion.li key={i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.08 }} className="flex gap-1.5">
                  <span className="tabular-nums text-[var(--muted)]">{i + 1}.</span> {step}
                </motion.li>
              ))}
            </ol>
          )}
          {scam && <ScamChip verdict={scam.verdict} lang={lang} />}
          {text && <Words text={text} lines={big ? 5 : 4} />}
          {offerUndo && (
            <motion.button
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              whileTap={{ scale: 0.94 }}
              onClick={() => send({ type: "undo", turn_id: undo.turnId })}
              className="mx-auto mt-1.5 flex h-6 items-center gap-1 rounded-full bg-[var(--hairline-strong)] px-2.5 text-[11px] font-semibold"
              title={undo.actions.join(", ")}
            >
              <Undo2 size={12} /> {lang === "ta" ? "திருப்பி மாத்து" : "Undo"}
            </motion.button>
          )}
          {auth && <p className="mt-1 text-[11px] text-[var(--muted)]">{lang === "ta" ? "Touch ID தேவை" : "Confirm with Touch ID"}</p>}

          <AnimatePresence mode="wait" initial={false}>
            {activeTool && !confirm ? (
              <motion.div key="tool" {...pill} className="mt-1.5 flex items-center justify-center gap-1.5 text-[11px] text-[var(--muted)]">
                <LoaderCircle size={11} className="animate-spin" />
                <span className="font-mono">{activeTool}</span>
              </motion.div>
            ) : flash && !confirm ? (
              <motion.div
                key="flash"
                {...pill}
                className="mt-1.5 flex items-center justify-center gap-1 text-[11px] font-medium"
                style={{ color: flash.ok ? "var(--ok)" : "var(--danger)" }}
              >
                {flash.ok ? <Check size={12} strokeWidth={3} /> : <X size={12} strokeWidth={3} />}
                {flash.summary}
              </motion.div>
            ) : null}
          </AnimatePresence>

          {confirm && (
            <div className="mt-2.5 flex justify-center gap-2">
              {dangerous && <ShieldAlert size={14} className="self-center text-[var(--danger)]" />}
              <motion.button
                whileTap={{ scale: 0.94 }}
                onClick={() => answer(true)}
                className="flex h-7 items-center gap-1 rounded-full bg-[var(--ok)] px-3 text-[12px] font-semibold text-white shadow-sm"
              >
                <Check size={13} strokeWidth={3} /> {lang === "ta" ? "ஆமா" : "Yes"}
              </motion.button>
              <motion.button
                whileTap={{ scale: 0.94 }}
                onClick={() => answer(false)}
                className="flex h-7 items-center gap-1 rounded-full bg-[var(--hairline-strong)] px-3 text-[12px] font-semibold"
              >
                <X size={13} strokeWidth={3} /> {lang === "ta" ? "வேண்டாம்" : "No"}
              </motion.button>
            </div>
          )}

          {/* tail pointing down at the robot */}
          <span
            aria-hidden
            className="absolute -bottom-[5px] left-1/2 h-2.5 w-2.5 -translate-x-1/2 rotate-45"
            style={{ background: "var(--glass)", borderRight: "0.5px solid var(--glass-border)", borderBottom: "0.5px solid var(--glass-border)" }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

const SCAM = {
  scam: { color: "var(--danger)", en: "Looks like a scam", ta: "Scam மாதிரி இருக்கு", Icon: ShieldAlert },
  suspicious: { color: "var(--warn)", en: "Be careful", ta: "கவனமா இருங்க", Icon: ShieldAlert },
  looks_ok: { color: "var(--ok)", en: "No scam signs", ta: "Scam அடையாளம் இல்ல", Icon: ShieldCheck },
} as const;

function ScamChip({ verdict, lang }: { verdict: keyof typeof SCAM; lang: string }) {
  const s = SCAM[verdict];
  return (
    <motion.p
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="mx-auto mb-1.5 flex w-fit items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold"
      style={{ color: s.color, background: `color-mix(in srgb, ${s.color} 14%, transparent)` }}
    >
      <s.Icon size={12} /> {lang === "ta" ? s.ta : s.en}
    </motion.p>
  );
}

const pill = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
  transition: { duration: 0.18 },
};

/** Each new word fades up as it streams in. */
function Words({ text, lines }: { text: string; lines: number }) {
  const words = text.split(/(\s+)/);
  return (
    <p className={lines === 5 ? "line-clamp-5" : "line-clamp-4"}>
      {words.map((w, i) => (
        <motion.span key={`${i}-${w}`} initial={{ opacity: 0, filter: "blur(3px)" }} animate={{ opacity: 1, filter: "blur(0px)" }} transition={{ duration: 0.25 }}>
          {w}
        </motion.span>
      ))}
    </p>
  );
}
