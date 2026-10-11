import { Volume2, VolumeX } from "lucide-react";
import { setSound, useSound } from "../sound";

export function SoundToggle() {
  const on = useSound();
  return (
    <button
      onClick={() => setSound(!on)}
      aria-pressed={on}
      aria-label={on ? "Turn demo sounds off" : "Turn demo sounds on"}
      className="flex h-9 w-9 items-center justify-center rounded-full text-[var(--muted)] hover:bg-[var(--panel)] hover:text-[var(--text)]"
    >
      {on ? <Volume2 size={17} /> : <VolumeX size={17} />}
    </button>
  );
}
