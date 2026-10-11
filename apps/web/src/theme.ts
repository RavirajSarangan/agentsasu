import { useEffect, useState } from "react";

export type Theme = "light" | "dark";
const KEY = "sasu.theme";

function read(): Theme {
  try {
    return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

/** Light is the default; dark only when the visitor picks it. */
export function applyStoredTheme() {
  document.documentElement.dataset.theme = read();
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(read);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* private mode: theme still applies for this visit */
    }
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "light" ? "dark" : "light"))];
}
