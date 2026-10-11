export type Lang = "en" | "ta";

export type Theme = {
  label: string;
  color: string;
  trimColor: string;
  /** LED colour per heard language, so you can see which language Sasu understood. */
  screen: Record<Lang, string>;
  /** UI accent that matches the shell. */
  accent: string;
  glow: string;
};

export const themes = {
  midnight: {
    label: "Midnight",
    color: "#2b49a3",
    trimColor: "#93a6c8",
    screen: { en: "#e8f2ff", ta: "#ffd27a" },
    accent: "#3a5fd0",
    glow: "rgba(58, 95, 208, 0.35)",
  },
  kumkum: {
    label: "Kumkum",
    color: "#a3242b",
    trimColor: "#e0b860",
    screen: { en: "#fff3e0", ta: "#ffd27a" },
    accent: "#c4323a",
    glow: "rgba(196, 50, 58, 0.32)",
  },
  mint: {
    label: "Mint",
    color: "#1f8a70",
    trimColor: "#b9d9cf",
    screen: { en: "#eafff6", ta: "#ffe08a" },
    accent: "#1d9a7c",
    glow: "rgba(29, 154, 124, 0.32)",
  },
  mono: {
    label: "Graphite",
    color: "#2d3038",
    trimColor: "#a7acb8",
    screen: { en: "#f2f4f8", ta: "#ffcf70" },
    accent: "#5b6170",
    glow: "rgba(91, 97, 112, 0.32)",
  },
} satisfies Record<string, Theme>;

export type ThemeName = keyof typeof themes;
