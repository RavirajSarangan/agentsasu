import { type Cue, packs, setVolume, unlock } from "@sasu/brand";
import { useSyncExternalStore } from "react";

// Sound on the website is off until the visitor turns it on.
let on = false;
const subs = new Set<() => void>();

export function setSound(v: boolean) {
  on = v;
  if (v) {
    unlock();
    setVolume(0.5);
    packs.soft.success();
  }
  subs.forEach((f) => f());
}

export function cue(c: Cue, force = false) {
  if (!on && !force) return;
  unlock();
  setVolume(0.5);
  packs.soft[c]();
}

export function useSound() {
  return useSyncExternalStore(
    (f) => (subs.add(f), () => subs.delete(f)),
    () => on,
    () => false, // pre-rendered page: sound starts off
  );
}
