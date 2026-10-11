// Renders the 660×400 DMG window background (captured to assets/ by scripts/render-assets.py).
// Finder draws the app icon at (180, 220) and the Applications link at (480, 220).
import { themes } from "@sasu/brand";
import { createRoot } from "react-dom/client";
import { RobotHead } from "robot-heads";
import "./styles.css";

function Dmg() {
  const t = themes.midnight;
  return (
    <div
      data-theme="light"
      style={{
        width: 660,
        height: 400,
        position: "relative",
        overflow: "hidden",
        background: "radial-gradient(120% 90% at 50% 0%, #ffffff 0%, #eef1fa 55%, #e2e7f5 100%)",
        fontFamily: "-apple-system, 'Inter Variable', sans-serif",
        color: "#0b0d14",
      }}
    >
      <div style={{ position: "absolute", left: 24, top: 22, display: "flex", alignItems: "center", gap: 10 }}>
        <RobotHead size={34} state="happy" color={t.color} trimColor={t.trimColor} screenColor={t.screen.en} interactive={false} antenna={false} floorShadow={false} paused />
        <span style={{ fontWeight: 600, fontSize: 17, letterSpacing: "-0.02em" }}>Sasu</span>
      </div>
      <p style={{ position: "absolute", top: 76, width: "100%", textAlign: "center", fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", margin: 0 }}>
        Drag Sasu into Applications
      </p>
      <p style={{ position: "absolute", top: 108, width: "100%", textAlign: "center", fontSize: 13, color: "#5b6070", margin: 0 }}>
        Then open it and say “Hey Sasu” · <span lang="ta">வணக்கம்!</span>
      </p>
      {/* soft spots under the two Finder icons */}
      {[180, 480].map((x) => (
        <div key={x} style={{ position: "absolute", left: x - 70, top: 220 - 70, width: 140, height: 140, borderRadius: "50%", background: "radial-gradient(closest-side, rgba(58,95,208,0.16), transparent)" }} />
      ))}
      <svg width="660" height="400" style={{ position: "absolute", inset: 0 }} aria-hidden>
        <defs>
          <linearGradient id="g" x1="0" x2="1">
            <stop offset="0" stopColor="#3a5fd0" stopOpacity="0.25" />
            <stop offset="1" stopColor="#7c5cff" />
          </linearGradient>
        </defs>
        <path d="M262 220 C 320 196, 360 196, 404 216" fill="none" stroke="url(#g)" strokeWidth="4" strokeLinecap="round" strokeDasharray="2 10" />
        <path d="M394 204 L 410 218 L 392 230" fill="none" stroke="#7c5cff" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <p style={{ position: "absolute", bottom: 18, width: "100%", textAlign: "center", fontSize: 11, color: "#9aa0ad", margin: 0 }}>
        Open source · MIT · Your voice never leaves this Mac
      </p>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<Dmg />);
