import { createRoot } from "react-dom/client";
import { Robot } from "./Robot";
import "./styles.css";

// 660×400 DMG window background. Finder draws the Sasu icon at (180, 220) and the
// Applications folder at (480, 220) on top of the two pads below.
document.documentElement.dataset.theme = "light";

function Pad({ x }: { x: number }) {
  return (
    <div
      className="absolute rounded-[28px] bg-white shadow-[0_1px_2px_rgba(20,26,51,0.06),0_18px_40px_-18px_rgba(20,26,51,0.35),inset_0_0_0_1px_rgba(20,26,51,0.06)]"
      style={{ left: x - 66, top: 220 - 66, width: 132, height: 132 }}
    />
  );
}

createRoot(document.getElementById("root")!).render(
  <div className="dots relative h-[400px] w-[660px] overflow-hidden bg-[var(--bg)]">
    <div className="absolute left-[28px] top-[24px] flex items-center gap-2.5">
      <Robot state="happy" size={30} halo={false} interactive={false} />
      <span className="text-[19px] font-bold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
        Sasu
      </span>
    </div>
    <p className="absolute inset-x-0 top-[60px] text-center text-[22px] font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
      Drag Sasu into Applications
    </p>
    <p className="absolute inset-x-0 top-[94px] text-center text-[13px] text-[var(--muted)]">
      Then open it and say “Hey Sasu”. <span lang="ta">வணக்கம்!</span>
    </p>

    <Pad x={180} />
    <Pad x={480} />

    {/* dotted path between the pads, like a kolam line, ending in an arrow */}
    <svg className="absolute" style={{ left: 252, top: 182, width: 156, height: 60 }} viewBox="0 0 156 60" fill="none">
      <path d="M4 40 C 40 4, 112 4, 146 34" stroke="#2b49a3" strokeOpacity="0.55" strokeWidth="3.5" strokeLinecap="round" strokeDasharray="0.1 10" />
      <path d="M134 22 L148 36 L130 42" stroke="#2b49a3" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>

    <p className="absolute inset-x-0 bottom-[22px] text-center text-[11.5px] text-[var(--faint)]">
      First launch: System Settings → Privacy & Security → Open Anyway
    </p>
  </div>,
);
