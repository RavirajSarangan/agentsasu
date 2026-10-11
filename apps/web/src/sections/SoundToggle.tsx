import { Volume2, VolumeX } from "lucide-react";
import { setSound, useSound } from "../sound";

export function SoundToggle() {
  const on = useSound();
  return (
    <button
      onClick={() => setSound(!on)}
      aria-pressed={on}
      aria-label={on ? "Turn sound off" : "Turn sound on"}
      className="flex h-9 items-center gap-1.5 rounded-full px-3 text-sm text-[var(--muted)] hover:text-[var(--text)]"
    >
      {on ? <Volume2 size={17} /> : <VolumeX size={17} />}
      <span className="hidden lg:inline">{on ? "Sound on" : "Sound off"}</span>
    </button>
  );
}
