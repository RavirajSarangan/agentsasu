import { MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";
import { applyStoredTheme } from "./theme";

applyStoredTheme();

const root = document.getElementById("root")!;
const app = (
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </StrictMode>
);
// The built page arrives pre-rendered (scripts/prerender.mjs): take it over instead of redrawing.
if (root.hasChildNodes()) hydrateRoot(root, app);
else createRoot(root).render(app);
