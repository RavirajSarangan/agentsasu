// Robot look-and-feel settings, shared by every window: persisted in localStorage and
// broadcast with a Tauri event (each window has its own JS context).
import { Store } from "@tanstack/react-store";
import { isTauri } from "@tauri-apps/api/core";
import { emit, listen } from "@tauri-apps/api/event";
import type { RobotHeadShape } from "robot-heads";
import type { PackName } from "@sasu/brand";
import { themes, type ThemeName } from "./themes";

export type Mode = "normal" | "offline" | "safe" | "full";

export type RobotSettings = {
  shape: RobotHeadShape;
  /** When on, the shape follows the agent mode instead of `shape`. */
  modeShapes: boolean;
  mode: Mode;
  theme: ThemeName;
  size: number;
  dnd: boolean;
  batterySaver: boolean;
  sound: boolean;
  /** 0–1 */
  volume: number;
  soundPack: PackName;
  /** Trackpad taps on confirm, Touch ID and success. */
  haptics: boolean;
  /** The robot flies to the app it's working in. */
  flyToApps: boolean;
  /** AI provider the core should use. */
  provider: "gemini" | "groq" | "anthropic" | "ollama";
  /** Speak replies out loud with the Mac's voices. */
  tts: boolean;
  /** Unknown voices: limited "guest" tools, or ignored completely. */
  guestMode: "guest" | "reject";
  /** Sasu's speaking voice: girl (Tara + Vani) or boy (Rishi + Vani). */
  voiceStyle: "girl" | "boy";
  /** Robot dances while music plays. */
  dance: boolean;
  /** Playful Tamil touches in replies. */
  funReplies: boolean;
  /** Lock when the Mac has been idle this many minutes (0 = off). */
  awayMinutes: number;
  /** Plant trap files that catch misuse. */
  canaries: boolean;
  /** Stretch / water reminder every N minutes (0 = off). */
  breakMinutes: number;
  /** What you call the robot (comma-separated extra names, e.g. "Chitti, சிட்டி"). */
  robotName: string;
  /** City for the morning briefing weather. */
  city: string;
  /** Spoken heads-ups: low battery, meeting in 5 minutes. */
  nudges: boolean;
  /** Festive greetings on Pongal, Deepavali, Tamil New Year, Christmas. */
  festivals: boolean;
  /** Take a camera photo when a stranger or a trap file triggers (opt-in). */
  intruderPhoto: boolean;
  /** Emergency contact (phone or email) for the SOS phrase. */
  sosContact: string;
  /** Amma mode: who "magan" / "magal" (son / daughter) means when an elder asks to call. */
  sonName: string;
  daughterName: string;
  /** Loud siren + lock when a trap file is touched or strangers keep trying. */
  lostAlarm: boolean;
  /** Remember the last 50 copied texts (encrypted) so you can ask for them back. */
  clipboardMemory: boolean;
  /** First-run setup finished. */
  onboarded: boolean;
  uiLang: "en" | "ta";
};

export const SIZES = { S: 96, M: 140, L: 180 } as const;

export const MODE_SHAPE: Record<Mode, RobotHeadShape> = {
  normal: "rectangle",
  offline: "circle",
  safe: "square",
  full: "hexagon",
};

const KEY = "sasu.robot-settings";
const EVENT = "robot-settings";

const defaults: RobotSettings = {
  shape: "rectangle",
  modeShapes: false,
  mode: "normal",
  theme: "midnight",
  size: SIZES.M,
  dnd: false,
  batterySaver: false,
  sound: true,
  volume: 0.6,
  soundPack: "soft",
  haptics: true,
  flyToApps: true,
  provider: "gemini",
  tts: true,
  guestMode: "guest",
  voiceStyle: "girl",
  dance: true,
  funReplies: true,
  awayMinutes: 0,
  canaries: true,
  breakMinutes: 0,
  robotName: "",
  city: "",
  nudges: false,
  festivals: true,
  intruderPhoto: false,
  sosContact: "",
  sonName: "",
  daughterName: "",
  lostAlarm: false,
  clipboardMemory: false,
  onboarded: false,
  uiLang: "en",
};

function load(): RobotSettings {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<RobotSettings>;
    const merged = { ...defaults, ...saved };
    return merged.theme in themes ? merged : { ...merged, theme: defaults.theme };
  } catch {
    return defaults;
  }
}

export const settingsStore = new Store<RobotSettings>(load());

export function updateSettings(patch: Partial<RobotSettings>) {
  settingsStore.setState((s) => ({ ...s, ...patch }));
  const next = settingsStore.get();
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable: settings still apply for this session */
  }
  if (isTauri()) void emit(EVENT, next);
}

export function effectiveShape(s: RobotSettings): RobotHeadShape {
  return s.modeShapes ? MODE_SHAPE[s.mode] : s.shape;
}

if (isTauri()) {
  void listen<RobotSettings>(EVENT, (e) => settingsStore.setState(() => e.payload));
} else {
  window.addEventListener("storage", (e) => {
    if (e.key === KEY) settingsStore.setState(() => load());
  });
}

/** The part of the settings the agent core cares about. */
export function coreSettings(s: RobotSettings) {
  return {
    provider: s.provider,
    tts: s.tts,
    guest_mode: s.guestMode,
    voice_style: s.voiceStyle,
    fun_replies: s.funReplies,
    away_minutes: s.awayMinutes,
    canaries: s.canaries,
    robot_name: s.robotName,
    city: s.city,
    nudges: s.nudges,
    festivals: s.festivals,
    intruder_photo: s.intruderPhoto,
    sos_contact: s.sosContact,
    relations: { son: s.sonName, daughter: s.daughterName },
    lost_alarm: s.lostAlarm,
    clipboard_memory: s.clipboardMemory,
  };
}
