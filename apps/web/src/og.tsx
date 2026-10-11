// 1200×630 social card (captured by scripts/render-assets.py).
import { themes } from "@sasu/brand";
import { createRoot } from "react-dom/client";
import { RobotHead } from "robot-heads";
import "./styles.css";

function Og() {
  const t = themes.midnight;
  return (
    <div
      style={{
        width: 1200,
        height: 630,
        position: "relative",
        overflow: "hidden",
        background: "radial-gradient(70% 90% at 78% 55%, rgba(111,140,255,0.35), transparent 60%), #07080d",
        color: "#f3f4f8",
        fontFamily: "-apple-system, 'Inter Variable', sans-serif",
      }}
    >
      <div style={{ position: "absolute", left: 80, top: 90 }}>
        <p style={{ margin: 0, fontSize: 26, color: "#9da3b4", fontWeight: 500 }}>Sasu · open-source voice agent for macOS</p>
        <h1 style={{ margin: "26px 0 0", fontSize: 92, lineHeight: 1.0, letterSpacing: "-0.04em", fontWeight: 650 }}>
          Your Mac,
          <br />
          by voice.
        </h1>
        <p className="gradient-text" style={{ margin: "18px 0 0", fontSize: 64, fontWeight: 650, letterSpacing: "-0.03em", ["--accent" as string]: "#6f8cff", ["--accent-2" as string]: "#a78bfa" }}>
          English & <span lang="ta">தமிழ்</span>
        </p>
        <p style={{ margin: "34px 0 0", fontSize: 24, color: "#9da3b4" }}>Owner-only voice · Touch ID · Local-first</p>
      </div>
      <div style={{ position: "absolute", right: 120, top: 150 }}>
        <RobotHead size={300} state="happy" color={t.color} trimColor={t.trimColor} screenColor={t.screen.en} interactive={false} paused />
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<Og />);
