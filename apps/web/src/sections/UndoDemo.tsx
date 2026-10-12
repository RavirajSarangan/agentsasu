import { Check, FolderPlus, MoveRight, RotateCcw, Undo2, Volume2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { Robot } from "../Robot";
import { cue } from "../sound";

const ACTIONS = [
  { Icon: FolderPlus, text: "Made a folder called PDFs in Downloads" },
  { Icon: MoveRight, text: "Moved Invoice September.pdf into PDFs" },
  { Icon: MoveRight, text: "Moved Boarding pass.pdf into PDFs" },
  { Icon: Volume2, text: "Turned the volume from 70 to 30" },
];

export function UndoDemo() {
  const [undone, setUndone] = useState(false);
  const toggle = () => {
    setUndone((u) => !u);
    cue(undone ? "success" : "toggle", true);
  };
  return (
    <section id="undo" className="cv bg-[var(--bg-2)] px-4 py-16 sm:px-6 sm:py-28">
      <div className="mx-auto grid max-w-[1180px] grid-cols-[minmax(0,1fr)] items-center gap-14 lg:grid-cols-2">
        <div>
          <h2 className="title text-[clamp(2.2rem,4.6vw,3.6rem)]">Changed your mind? Say “undo”.</h2>
          <p className="lede mt-5">
            Every change Sasu makes is written down together with how to reverse it. Files go back to where they were, settings return to what they were, apps it opened
            close again. Thrown-away files wait in Sasu's own bin, so even those come back.
          </p>
          <p className="mt-4 text-[var(--muted)]">Works by voice, with ⌘⌥Z, or with the Undo button next to every request.</p>
        </div>
        <div className="rounded-[28px] bg-[var(--panel)] p-6 shadow-[var(--shadow-lg)] sm:p-8">
          <div className="mb-5 flex items-center gap-3">
            <Robot state={undone ? "happy" : "working"} size={44} halo={false} interactive={false} />
            <div>
              <p className="font-semibold">Sorting my Downloads</p>
              <p className="text-sm text-[var(--muted)]">{undone ? "Everything put back" : "4 changes, all undoable"}</p>
            </div>
          </div>
          <ol className="flex flex-col gap-2">
            {ACTIONS.map(({ Icon, text }, i) => (
              <motion.li
                key={text}
                animate={{ opacity: undone ? 0.45 : 1, x: undone ? -4 : 0 }}
                transition={{ delay: undone ? (ACTIONS.length - i) * 0.08 : i * 0.06 }}
                className="flex items-center gap-3 rounded-2xl bg-[var(--bg)] px-4 py-3"
              >
                <Icon size={17} className="shrink-0 text-[var(--accent)]" />
                <span className={`flex-1 text-[0.97rem] ${undone ? "line-through decoration-[var(--faint)]" : ""}`}>{text}</span>
                <AnimatePresence mode="wait">
                  {undone ? (
                    <motion.span key="r" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: (ACTIONS.length - i) * 0.08 }}>
                      <RotateCcw size={15} className="text-[var(--amber)]" />
                    </motion.span>
                  ) : (
                    <motion.span key="c" initial={{ scale: 0 }} animate={{ scale: 1 }}>
                      <Check size={15} strokeWidth={3} className="text-[var(--signal)]" />
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.li>
            ))}
          </ol>
          <button onClick={toggle} className="key mt-6 flex w-full items-center justify-center gap-2 py-3.5 font-semibold" data-pressed={false}>
            <Undo2 size={17} /> {undone ? "Do it again" : "“Sasu, undo”"}
          </button>
        </div>
      </div>
    </section>
  );
}
