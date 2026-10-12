import type { Cue } from "@sasu/brand";
import { Check, FileText, Folder, ListChecks, Pause, Play, Undo2, Volume2 } from "lucide-react";
import { AnimatePresence, motion, useInView } from "motion/react";
import type { RobotHeadState } from "robot-heads";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Robot, STATE_COLOR } from "../Robot";
import { cue } from "../sound";

type Win = "none" | "safari" | "finder" | "volume";
type Bubble = { kind: "heard" | "say" | "plan" | "tool"; text: string; lang?: "en" | "ta"; steps?: string[] };
type Beat = {
  said?: string;
  saidLang?: "en" | "ta";
  state: RobotHeadState;
  at: "home" | "safari" | "finder";
  win: Win;
  sorted?: boolean;
  results?: boolean;
  bubble?: Bubble;
  undo?: boolean;
  ms: number;
  cue?: Cue;
};

const POS = { home: { x: 87, y: 72 }, safari: { x: 64, y: 22 }, finder: { x: 58, y: 24 } } as const;
/** Phones: a portrait Mac screen; windows fill the top, the robot sits below them. */
const POS_NARROW = { home: { x: 76, y: 80 }, safari: { x: 70, y: 76 }, finder: { x: 70, y: 76 } } as const;
const NARROW = 760;

const SCRIPT: Beat[] = [
  { state: "idle", at: "home", win: "none", ms: 1600 },
  { said: "Hey Sasu", state: "listening", at: "home", win: "none", bubble: { kind: "heard", text: "Hey Sasu" }, ms: 1100, cue: "wake" },
  { said: "Open Safari and look up flights to Chennai", state: "thinking", at: "home", win: "none", bubble: { kind: "heard", text: "Open Safari and look up flights to Chennai" }, ms: 1500, cue: "think" },
  { said: "Open Safari and look up flights to Chennai", state: "working", at: "safari", win: "safari", bubble: { kind: "tool", text: "Opening Safari" }, ms: 1600, cue: "tool" },
  { said: "Open Safari and look up flights to Chennai", state: "searching", at: "safari", win: "safari", results: true, bubble: { kind: "tool", text: "Searching flights" }, ms: 1500, cue: "tool" },
  { said: "Open Safari and look up flights to Chennai", state: "speaking", at: "safari", win: "safari", results: true, bubble: { kind: "say", text: "Here are tomorrow's flights to Chennai." }, ms: 2300 },
  { state: "happy", at: "home", win: "safari", results: true, ms: 1300, cue: "success" },
  { said: "Downloads la irukura PDF ellam oru folder-la podu", state: "thinking", at: "home", win: "finder", bubble: { kind: "heard", text: "Downloads la irukura PDF ellam oru folder-la podu" }, ms: 1700, cue: "think" },
  {
    said: "Downloads la irukura PDF ellam oru folder-la podu",
    state: "listening",
    at: "finder",
    win: "finder",
    bubble: { kind: "plan", text: "Here's my plan", steps: ["Find 4 PDFs in Downloads", "Make a folder called PDFs", "Move them in"] },
    ms: 2300,
    cue: "confirm",
  },
  { said: "Downloads la irukura PDF ellam oru folder-la podu", state: "working", at: "finder", win: "finder", sorted: true, bubble: { kind: "tool", text: "Moving 4 files" }, ms: 1500, cue: "tool" },
  {
    said: "Downloads la irukura PDF ellam oru folder-la podu",
    state: "speaking",
    at: "finder",
    win: "finder",
    sorted: true,
    undo: true,
    bubble: { kind: "say", text: "முடிஞ்சது! 4 PDF-உம் PDFs folder-ல இருக்கு.", lang: "ta" },
    ms: 2500,
  },
  { said: "Sasu, undo", state: "happy", at: "finder", win: "finder", bubble: { kind: "say", text: "Undone. Your files are back where they were." }, ms: 2200, cue: "toggle" },
  { said: "Volume 30", state: "working", at: "home", win: "volume", bubble: { kind: "heard", text: "Volume 30" }, ms: 1300, cue: "tool" },
  { said: "Volume 30", state: "happy", at: "home", win: "volume", ms: 1500, cue: "success" },
];

const FILES = [
  { name: "Boarding pass.pdf", pdf: true },
  { name: "Beach.jpg", pdf: false },
  { name: "Invoice September.pdf", pdf: true },
  { name: "Thesis draft.pdf", pdf: true },
  { name: "Notes.txt", pdf: false },
  { name: "Lease.pdf", pdf: true },
];

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(960);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(e!.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export function Desk() {
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(true);
  useEffect(() => {
    // reduced motion: show one finished scene instead of the story (read after mount so the
    // pre-rendered page and the first client render agree)
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setI(10);
      setPlaying(false);
    }
  }, []);
  const [ref, w] = useWidth<HTMLDivElement>();
  const box = useRef<HTMLDivElement>(null);
  const inView = useInView(box, { margin: "80px" }); // the story only plays while you can see it
  const beat = SCRIPT[i]!;
  const narrow = w < NARROW;
  const robot = narrow ? Math.max(58, w * 0.17) : Math.max(54, Math.min(120, w * 0.095));
  const pos = (narrow ? POS_NARROW : POS)[beat.at];
  const font = narrow ? Math.min(15, w * 0.035) : Math.max(9, w * 0.0125);
  const bubbleW = narrow ? Math.min(w * 0.62, 290) : Math.max(220, w * 0.24);
  // keep the bubble inside the screen: shift it sideways, the tail stays on the robot
  const cx = (pos.x / 100) * w;
  const shift = Math.min(0, w - 10 - (cx + bubbleW / 2)) + Math.max(0, 10 - (cx - bubbleW / 2));

  useEffect(() => {
    if (!playing || !inView) return;
    if (beat.cue) cue(beat.cue);
    const t = setTimeout(() => setI((n) => (n + 1) % SCRIPT.length), beat.ms);
    return () => clearTimeout(t);
  }, [i, beat, playing, inView]);

  return (
    <div ref={box} className="mx-auto w-full max-w-[1120px]">
      {/* the Mac */}
      <div ref={ref} className={`relative w-full aspect-[4/5] min-[792px]:aspect-[16/10] rounded-[clamp(14px,2.2vw,28px)] bg-[#0e1430] p-[clamp(5px,0.7vw,9px)] shadow-[var(--shadow-lg)]`}>
        <div className="relative h-full w-full overflow-hidden rounded-[clamp(10px,1.6vw,20px)]" style={{ fontSize: font }} data-narrow={narrow || undefined}>
          <Wallpaper />
          <MenuBar />
          <AnimatePresence>
            {beat.win === "safari" && <Safari key="safari" results={!!beat.results} />}
            {beat.win === "finder" && <Finder key="finder" sorted={!!beat.sorted} />}
            {beat.win === "volume" && <VolumeHud key="vol" />}
          </AnimatePresence>
          <Dock />
        </div>

        {/* robot layer: not clipped, so hops and glow can spill */}
        <motion.div
          className="pointer-events-none absolute z-20"
          initial={false}
          animate={{ left: `${pos.x}%`, top: `${pos.y}%` }}
          transition={{ type: "spring", stiffness: 70, damping: 16, mass: 1 }}
          style={{ x: "-50%", y: "-50%" }}
        >
          <div className="pointer-events-auto relative flex flex-col items-center">
            <AnimatePresence mode="wait">
              {beat.bubble && (
                <SpeechBubble key={beat.bubble.text + beat.bubble.kind} b={beat.bubble} state={beat.state} undo={!!beat.undo} width={bubbleW} shift={shift} fontSize={narrow ? Math.max(12.5, font) : undefined} />
              )}
            </AnimatePresence>
            <Robot state={beat.state} size={robot} lang={beat.bubble?.lang ?? "en"} halo={false} />
          </div>
        </motion.div>
      </div>

      {/* what you said — the subtitle of the demo */}
      <div className="mt-6 flex items-center gap-4 px-1">
        <button
          onClick={() => setPlaying((p) => !p)}
          className="key flex h-11 w-11 shrink-0 items-center justify-center text-[var(--text)]"
          aria-label={playing ? "Pause the demo" : "Play the demo"}
        >
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <div className="min-w-0 flex-1">
          <AnimatePresence mode="wait">
            <motion.p
              key={beat.said ?? "idle"}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25 }}
              className="title truncate text-[clamp(1.05rem,2.4vw,1.6rem)]"
              lang={beat.said && /la |podu|pannu/.test(beat.said) ? "en" : undefined}
            >
              {beat.said ? (
                <>
                  <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle blink" style={{ background: STATE_COLOR[beat.state] }} />“{beat.said}”
                </>
              ) : (
                <span className="text-[var(--faint)]">Sasu is waiting in the corner.</span>
              )}
            </motion.p>
          </AnimatePresence>
        </div>
        <div className="hidden gap-1.5 sm:flex" aria-hidden>
          {SCRIPT.map((_, n) => (
            <span key={n} className="h-1.5 rounded-full transition-all" style={{ width: n === i ? 18 : 6, background: n <= i ? "var(--accent)" : "var(--line-strong)" }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function SpeechBubble({ b, state, undo, width, shift = 0, fontSize }: { b: Bubble; state: RobotHeadState; undo: boolean; width: number; shift?: number; fontSize?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.92 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -4, scale: 0.96, transition: { duration: 0.15 } }}
      transition={{ type: "spring", stiffness: 420, damping: 30 }}
      lang={b.lang}
      className="relative mb-[0.9em] rounded-[1.1em] bg-white/90 px-[1em] py-[0.7em] text-center text-[1em] leading-snug text-[#141a33] shadow-[0_10px_30px_-10px_rgba(0,0,0,0.45)] md:backdrop-blur-xl"
      style={{ width, marginLeft: shift * 2, fontSize }}
    >
      {b.kind === "heard" && <span className="mb-[0.2em] block text-[0.78em] font-semibold" style={{ color: STATE_COLOR[state] }}>Heard you</span>}
      {b.kind === "tool" && (
        <span className="flex items-center justify-center gap-[0.4em] font-medium">
          <span className="h-[0.55em] w-[0.55em] rounded-full blink" style={{ background: "var(--accent)" }} />
          {b.text}
        </span>
      )}
      {b.kind === "plan" && (
        <div className="text-left">
          <p className="mb-[0.3em] flex items-center gap-[0.35em] text-[0.85em] font-semibold text-[#2b49a3]">
            <ListChecks size="1.1em" /> {b.text}
          </p>
          <ol className="flex flex-col gap-[0.15em] text-[0.92em]">
            {b.steps?.map((s, n) => (
              <motion.li key={s} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + n * 0.12 }}>
                {n + 1}. {s}
              </motion.li>
            ))}
          </ol>
          <div className="mt-[0.5em] flex gap-[0.4em]">
            <span className="rounded-full bg-[#1fa968] px-[0.8em] py-[0.2em] text-[0.82em] font-semibold text-white">Go ahead</span>
            <span className="rounded-full bg-black/8 px-[0.8em] py-[0.2em] text-[0.82em] font-semibold">Not now</span>
          </div>
        </div>
      )}
      {(b.kind === "heard" || b.kind === "say") && <span>{b.text}</span>}
      {undo && (
        <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }} className="mx-auto mt-[0.45em] flex w-fit items-center gap-[0.3em] rounded-full bg-black/8 px-[0.7em] py-[0.15em] text-[0.82em] font-semibold">
          <Undo2 size="1em" /> Undo
        </motion.span>
      )}
      <span aria-hidden className="absolute -bottom-[0.32em] h-[0.7em] w-[0.7em] -translate-x-1/2 rotate-45 bg-white/90" style={{ left: `calc(50% - ${shift}px)` }} />
    </motion.div>
  );
}

function Wallpaper() {
  return (
    <div aria-hidden className="absolute inset-0" style={{ background: "linear-gradient(160deg, #3555c4 0%, #22348a 55%, #161f57 100%)" }}>
      <div className="absolute inset-0" style={{ backgroundImage: "radial-gradient(rgba(255,255,255,0.16) 1.2px, transparent 1.5px)", backgroundSize: "2.2em 2.2em" }} />
      {/* a petal kolam drawn around a dot grid, in LED amber */}
      <svg className="absolute right-[7%] top-[16%] h-[52%] opacity-30" viewBox="-100 -100 200 200" fill="none" stroke="#ffd27a" strokeWidth="2">
        {Array.from({ length: 8 }, (_, k) => (
          <ellipse key={k} cx="0" cy="-48" rx="16" ry="40" transform={`rotate(${k * 45})`} />
        ))}
        <circle r="26" />
        {[-60, -30, 0, 30, 60].flatMap((x) => [-60, -30, 0, 30, 60].map((y) => <circle key={`${x}${y}`} cx={x} cy={y} r="2.4" fill="#ffd27a" stroke="none" />))}
      </svg>
    </div>
  );
}

function MenuBar() {
  return (
    <div className="absolute inset-x-0 top-0 z-10 flex h-[2em] items-center justify-between bg-white/18 px-[1em] text-[0.95em] font-medium text-white md:backdrop-blur-md">
      <div className="flex gap-[1.3em]">
        <span className="font-bold">Finder</span>
        <span className="hidden sm:inline">File</span>
        <span className="hidden sm:inline">Edit</span>
        <span className="hidden sm:inline">View</span>
        <span className="hidden sm:inline">Go</span>
      </div>
      <div className="flex items-center gap-[1em]">
        <span className="flex h-[1.2em] w-[1.5em] items-center justify-center rounded-[0.3em] bg-white/30 text-[0.7em] font-bold">S</span>
        <Clock />
      </div>
    </div>
  );
}

/** The menu bar clock shows the visitor's real day and time, like a real Mac. */
function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const tick = () => setNow(new Date());
    const t = setInterval(tick, 15_000);
    return () => clearInterval(t);
  }, []);
  const day = now.toLocaleDateString(undefined, { weekday: "short" });
  const time = now.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return (
    <time dateTime={now.toISOString()} suppressHydrationWarning>
      {day} {time}
    </time>
  );
}

function Dock() {
  const tiles = ["#5b8def", "#f2b84b", "#57c785", "#ef6a5b", "#9b7bf0", "#4bc0d9", "#f08bb4"];
  return (
    <div aria-hidden className="absolute bottom-[1.5%] left-1/2 z-10 flex -translate-x-1/2 gap-[0.55em] rounded-[1.2em] bg-white/20 p-[0.5em] md:backdrop-blur-md">
      {tiles.map((c) => (
        <span key={c} className="h-[2.6em] w-[2.6em] rounded-[0.7em] shadow-[inset_0_-2px_0_rgba(0,0,0,0.15)]" style={{ background: c }} />
      ))}
    </div>
  );
}

const windowMotion = {
  initial: { opacity: 0, scale: 0.94, y: 12 },
  animate: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.96, transition: { duration: 0.2 } },
  transition: { type: "spring" as const, stiffness: 260, damping: 26 },
};

function Chrome({ title }: { title: string }) {
  return (
    <div className="flex h-[2.4em] items-center gap-[0.45em] border-b border-black/8 px-[0.9em]">
      {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
        <span key={c} className="h-[0.8em] w-[0.8em] rounded-full" style={{ background: c }} />
      ))}
      <span className="ml-[0.6em] truncate text-[0.95em] font-semibold text-black/60">{title}</span>
    </div>
  );
}

function Safari({ results }: { results: boolean }) {
  const rows = [
    ["06:40", "08:55", "Direct", "£412"],
    ["11:15", "14:05", "1 stop", "£368"],
    ["21:30", "23:50", "Direct", "£455"],
  ];
  return (
    <motion.div {...windowMotion} className="absolute left-[6%] top-[11%] z-[5] h-[60%] w-[52%] overflow-hidden in-data-narrow:left-[5%] in-data-narrow:top-[9%] in-data-narrow:h-[52%] in-data-narrow:w-[90%] rounded-[0.9em] bg-white text-[#141a33] shadow-[0_24px_60px_-20px_rgba(0,0,0,0.6)]">
      <Chrome title="Flights to Chennai" />
      <div className="px-[1.2em] py-[0.9em]">
        <div className="mb-[1em] flex h-[2.2em] items-center rounded-[0.7em] bg-black/5 px-[0.9em] text-[0.95em] text-black/55">flights from London to Chennai, tomorrow</div>
        {!results ? (
          <div className="flex flex-col gap-[0.6em]">
            {[80, 64, 72].map((wd, n) => (
              <motion.div key={n} className="h-[2.4em] rounded-[0.6em] bg-black/6" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1.1, repeat: Infinity, delay: n * 0.15 }} style={{ width: `${wd}%` }} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-[0.5em]">
            {rows.map((r, n) => (
              <motion.div
                key={r[0]}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: n * 0.1 }}
                className="flex items-center justify-between rounded-[0.6em] border border-black/8 px-[0.9em] py-[0.55em] text-[0.95em]"
              >
                <span className="font-semibold">
                  {r[0]} → {r[1]}
                </span>
                <span className="text-black/50 in-data-narrow:hidden">LHR to MAA, {r[2]}</span>
                <span className="font-bold text-[#2b49a3]">{r[3]}</span>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function Finder({ sorted }: { sorted: boolean }) {
  const shown = sorted ? FILES.filter((f) => !f.pdf) : FILES;
  return (
    <motion.div {...windowMotion} className="absolute left-[6%] top-[12%] z-[5] h-[58%] w-[50%] overflow-hidden in-data-narrow:left-[5%] in-data-narrow:top-[9%] in-data-narrow:h-[52%] in-data-narrow:w-[90%] rounded-[0.9em] bg-white text-[#141a33] shadow-[0_24px_60px_-20px_rgba(0,0,0,0.6)]">
      <Chrome title="Downloads" />
      <div className="flex h-full">
        <div className="hidden w-[24%] flex-col gap-[0.35em] border-r border-black/8 bg-black/[0.03] p-[0.8em] text-[0.9em] text-black/55 sm:flex">
          <span>Desktop</span>
          <span className="rounded-[0.4em] bg-[#2b49a3]/12 px-[0.4em] font-semibold text-[#2b49a3]">Downloads</span>
          <span>Documents</span>
        </div>
        <div className="grid flex-1 grid-cols-3 content-start gap-[0.9em] p-[1em]">
          <AnimatePresence>
            {sorted && (
              <motion.div key="folder" layout initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }} className="flex flex-col items-center gap-[0.3em] text-center">
                <Folder className="h-[2.6em] w-[2.6em] text-[#5b8def]" fill="#a8c4ff" strokeWidth={1.2} />
                <span className="text-[0.85em] font-semibold">PDFs</span>
                <span className="text-[0.75em] text-black/45">4 items</span>
              </motion.div>
            )}
            {shown.map((f) => (
              <motion.div
                key={f.name}
                layout
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.4, x: -30, transition: { duration: 0.35 } }}
                className="flex flex-col items-center gap-[0.3em] text-center"
              >
                <FileText className="h-[2.6em] w-[2.6em]" style={{ color: f.pdf ? "#e5484d" : "#8a93ad" }} strokeWidth={1.2} />
                <span className="line-clamp-2 text-[0.8em] leading-tight">{f.name}</span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

function VolumeHud() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className="absolute left-1/2 top-[38%] z-[5] flex h-[11em] w-[11em] -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center gap-[1em] rounded-[1.6em] bg-white/75 text-[#141a33] md:backdrop-blur-xl"
    >
      <Volume2 className="h-[3.4em] w-[3.4em]" strokeWidth={1.6} />
      <div className="h-[0.5em] w-[70%] overflow-hidden rounded-full bg-black/12">
        <motion.div className="h-full rounded-full bg-[#141a33]" initial={{ width: "70%" }} animate={{ width: "30%" }} transition={{ duration: 0.6, ease: "easeOut" }} />
      </div>
      <span className="flex items-center gap-[0.3em] text-[0.9em] font-semibold">
        <Check size="1em" /> 30
      </span>
    </motion.div>
  );
}
