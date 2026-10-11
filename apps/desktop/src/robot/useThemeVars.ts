import { useSelector } from "@tanstack/react-store";
import { useEffect } from "react";
import { settingsStore } from "./settings";
import { themes } from "./themes";

/** Mirrors the robot theme into CSS variables so the whole UI shares its accent. */
export function useThemeVars() {
  const name = useSelector(settingsStore, (s) => s.theme);
  useEffect(() => {
    const t = themes[name];
    const root = document.documentElement.style;
    root.setProperty("--accent", t.accent);
    root.setProperty("--accent-glow", t.glow);
  }, [name]);
}
