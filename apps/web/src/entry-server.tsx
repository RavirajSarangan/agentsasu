// Build-time render of the landing page, so phones see it before any JavaScript runs
// (scripts/prerender.mjs puts this HTML into dist/index.html; main.tsx hydrates it).
import { MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { renderToString } from "react-dom/server";
import { App } from "./App";

export function render(): string {
  return renderToString(
    <StrictMode>
      <MotionConfig reducedMotion="user">
        <App />
      </MotionConfig>
    </StrictMode>,
  );
}
