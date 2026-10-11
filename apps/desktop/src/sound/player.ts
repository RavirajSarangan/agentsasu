// Turns agent transitions into sounds. Only one window plays agent cues (the overlay
// in the app; whichever page is open in a plain browser), so sounds never double up.
import { packs, panFromScreenX, setPan, setVolume, unlock, type CueOpts } from "@sasu/brand";
import { onAgentEvent } from "../agent/store";
import { settingsStore } from "../robot/settings";
import { inTauri, onHotkey, windowLabel } from "../tauri";
import { cueFor, type Cue } from "./cues";

const MIN_GAP_MS: Partial<Record<Cue, number>> = { tool: 250, think: 400, click: 40 };
const lastPlayed = new Map<Cue, number>();
/** Tool calls so far in this turn: each one plays a step higher. */
let toolStep = 0;

/** Play a cue now. `force` ignores the sound switch and DND (settings previews). */
export function play(cue: Cue, { force = false, ...opts }: { force?: boolean } & CueOpts = {}) {
  const s = settingsStore.get();
  if (!force && (!s.sound || s.dnd || s.volume === 0)) return;
  const now = performance.now();
  if (now - (lastPlayed.get(cue) ?? -Infinity) < (MIN_GAP_MS[cue] ?? 0)) return;
  lastPlayed.set(cue, now);
  unlock();
  packs[s.soundPack][cue](opts);
}

let started = false;

export function startSoundPlayer() {
  if (started) return;
  started = true;

  setVolume(settingsStore.get().volume);
  settingsStore.subscribe((s) => setVolume(s.volume));

  for (const type of ["pointerdown", "keydown"] as const) {
    window.addEventListener(type, unlock, { capture: true, passive: true });
  }
  onHotkey("hotkey-talk", unlock);

  const playsAgentCues = inTauri ? windowLabel === "overlay" : true;
  if (!playsAgentCues) return;

  // Spatial: sounds come from wherever the robot sits on screen.
  const updatePan = () => setPan(panFromScreenX((window.screenX + window.outerWidth / 2) / window.screen.availWidth));
  updatePan();
  setInterval(updatePan, 1000);

  onAgentEvent((event, prev) => {
    if (event.type === "wake") toolStep = 0;
    const cue = cueFor(prev, event);
    if (!cue) return;
    if (cue === "tool") play(cue, { step: toolStep++ });
    else play(cue);
  });
}
