import { Music2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";

const NOTES = ["♪", "♫", "♬", "♩"];
const HUES = ["#ff5fa2", "#ffb938", "#30c35a", "#3ab8ff", "#9b7bf0"];

/** Party layer behind the robot while music plays: colour-cycling glow and rising notes. */
export function DanceGlow({ size }: { size: number }) {
  return (
    <motion.div
      aria-hidden
      className="pointer-events-none absolute rounded-full"
      style={{ left: "50%", top: "50%", width: size * 1.8, height: size * 1.8, marginLeft: -size * 0.9, marginTop: -size * 0.9, filter: "blur(8px)" }}
      animate={{
        background: HUES.map((c) => `radial-gradient(closest-side, color-mix(in srgb, ${c} 45%, transparent), transparent)`),
        scale: [0.92, 1.08, 0.92],
      }}
      transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
    />
  );
}

export function FloatingNotes({ size }: { size: number }) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      {Array.from({ length: 6 }, (_, i) => (
        <motion.span
          key={i}
          className="absolute select-none font-bold"
          style={{ left: `${15 + ((i * 37) % 70)}%`, bottom: size * 0.2, color: HUES[i % HUES.length], fontSize: 14 + (i % 3) * 5 }}
          initial={{ opacity: 0, y: 0 }}
          animate={{ opacity: [0, 1, 0], y: -size * (0.9 + (i % 3) * 0.25), x: [0, i % 2 ? 10 : -10, 0], rotate: [0, i % 2 ? 20 : -20] }}
          transition={{ duration: 2.4 + (i % 3) * 0.5, repeat: Infinity, delay: i * 0.45, ease: "easeOut" }}
        >
          {NOTES[i % NOTES.length]}
        </motion.span>
      ))}
    </div>
  );
}

export function NowPlaying({ song }: { song: string | null }) {
  return (
    <AnimatePresence>
      {song && (
        <motion.div
          initial={{ opacity: 0, y: 6, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 6 }}
          className="glass flex max-w-[200px] items-center gap-1.5 rounded-full py-1 pl-2 pr-3 text-[11px] font-semibold"
        >
          <motion.span animate={{ rotate: [0, -12, 12, 0] }} transition={{ duration: 0.8, repeat: Infinity }} className="text-[#ff5fa2]">
            <Music2 size={12} />
          </motion.span>
          <span className="truncate">{song}</span>
          <span className="flex h-3 items-end gap-[2px]">
            {[0.6, 1, 0.75].map((h, i) => (
              <motion.span
                key={i}
                className="w-[2.5px] rounded-full bg-[#ff5fa2]"
                animate={{ height: [`${h * 40}%`, "100%", `${h * 30}%`] }}
                transition={{ duration: 0.5 + i * 0.13, repeat: Infinity, repeatType: "mirror" }}
              />
            ))}
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
