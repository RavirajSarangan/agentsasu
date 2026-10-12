import { Brain, Ear, MessageCircle, Music } from "lucide-react";
import { useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Robot } from "../Robot";

/** Live versions of the app's overlay states: the real robot plus the same chip and bubble.
 * Everything moves with transform/opacity only and stops when the card is off screen. */

const AMMA = "அம்மா, BP மாத்திரை நேரம். சாப்பிட்டீங்களா?".split(" ");

function Chip({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className="state-chip" style={{ color }}>
      {children}
    </span>
  );
}

function Bars({ color, n = 5 }: { color: string; n?: number }) {
  return (
    <span aria-hidden className="eq" style={{ color }}>
      {Array.from({ length: n }, (_, i) => (
        <i key={i} style={{ animationDelay: `${(i * 0.13) % 0.5}s` }} />
      ))}
    </span>
  );
}

function Card({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <li className="flex w-[78%] max-w-[300px] shrink-0 snap-center flex-col items-center gap-2 overflow-hidden rounded-[18px] bg-[var(--panel)] px-2 pb-4 pt-3 shadow-[var(--shadow-sm)] sm:w-auto sm:max-w-none">
      <div className="relative flex h-[230px] w-full flex-col items-center justify-end gap-2 sm:h-[250px]">{children}</div>
      <span className="text-sm font-semibold text-[var(--muted)]">{label}</span>
    </li>
  );
}

export function Listening({ size = 104 }: { size?: number }) {
  return (
    <>
      <span className="flex items-center gap-2">
        <Chip color="var(--signal)">
          <Ear size={13} /> Listening
        </Chip>
        <Bars color="var(--signal)" />
      </span>
      <Robot state="listening" size={size} interactive={false} />
    </>
  );
}

export function Thinking({ size = 104 }: { size?: number }) {
  return (
    <>
      <span className="bubble">Hey Sasu, play some Ilaiyaraaja</span>
      <Chip color="var(--amber)">
        <Brain size={13} className="spin-slow" /> Thinking
      </Chip>
      <Robot state="thinking" size={size} interactive={false} />
    </>
  );
}

export function Dancing({ size = 104 }: { size?: number }) {
  return (
    <>
      <Chip color="#e0569b">
        <Music size={13} /> Ilaiyaraaja hits <Bars color="#e0569b" n={3} />
      </Chip>
      <div className="relative">
        {["♪", "♫", "♪"].map((n, i) => (
          <span key={i} aria-hidden className="note" style={{ left: `${18 + i * 30}%`, animationDelay: `${i * 0.7}s` }}>
            {n}
          </span>
        ))}
        <div className="dance">
          <Robot state="happy" size={size} interactive={false} />
        </div>
      </div>
    </>
  );
}

export function AmmaSpeaking({ size = 104, big = false }: { size?: number; big?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref);
  const [reduced, setReduced] = useState(false);
  const [n, setN] = useState(1);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setReduced(true);
      setN(AMMA.length);
    }
  }, []);
  useEffect(() => {
    if (!inView || reduced) return;
    // words appear one by one, hold, then start again
    const t = setTimeout(() => setN((k) => (k >= AMMA.length + 4 ? 1 : k + 1)), n === 1 ? 500 : 380);
    return () => clearTimeout(t);
  }, [inView, n, reduced]);
  return (
    <div ref={ref} className="contents">
      <span lang="ta" className={`bubble ${big ? "text-[1.35rem]" : "text-[1.05rem]"} font-medium leading-snug`} aria-label={AMMA.join(" ")}>
        {AMMA.map((w, i) => (
          <span key={i} aria-hidden className="word" style={{ opacity: i < n ? 1 : 0.12 }}>
            {w}{" "}
          </span>
        ))}
      </span>
      <Chip color="#8b5cf6">
        <MessageCircle size={13} /> <span lang="ta">பேசுகிறேன்</span>
      </Chip>
      <Robot state="speaking" size={size} lang="ta" interactive={false} />
    </div>
  );
}

export function RobotStates() {
  return (
    // phones: a swipeable row with room for the bubbles; bigger screens: a grid
    <ul
      className="-mx-4 mt-10 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 [scrollbar-width:none] sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 sm:pb-0 lg:grid-cols-4"
      aria-label="Sasu's robot in four moods"
    >
      <Card label="Listening">
        <Listening />
      </Card>
      <Card label="Thinking">
        <Thinking />
      </Card>
      <Card label="Music on">
        <Dancing />
      </Card>
      <Card label="Amma mode">
        <AmmaSpeaking />
      </Card>
    </ul>
  );
}
