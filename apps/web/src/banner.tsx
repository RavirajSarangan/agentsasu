import { createRoot } from "react-dom/client";
import { Robot } from "./Robot";
import "./styles.css";

// 1280×640 social/README banner. Rendered to PNG by scripts, not linked from the site.
document.documentElement.dataset.theme = new URLSearchParams(location.search).get("theme") ?? "light";

createRoot(document.getElementById("root")!).render(
  <div className="dots relative flex h-[640px] w-[1280px] items-center overflow-hidden bg-[var(--bg)] px-[96px]">
    <div className="flex-1">
      <p className="display text-[128px]">Sasu</p>
      <p className="title mt-5 text-[40px]">Talk to your Mac.</p>
      <p lang="ta" className="mt-2 text-[30px] font-semibold text-[var(--muted)]">
        உங்க Mac-கிட்ட பேசுங்க.
      </p>
      <p className="mt-9 text-[21px] text-[var(--muted)]">English · தமிழ் · Tanglish — only your voice — undo anything</p>
    </div>
    <div className="mr-10">
      <Robot state="happy" size={300} />
    </div>
  </div>,
);
