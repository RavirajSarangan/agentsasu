import { motion } from "motion/react";
import { play } from "../sound/player";

/** macOS-style toggle. */
export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => {
        play("toggle");
        onChange(!checked);
      }}
      className="relative h-[22px] w-[38px] shrink-0 rounded-full transition-colors duration-200"
      style={{ background: checked ? "var(--accent)" : "var(--hairline-strong)" }}
    >
      <motion.span
        layout
        transition={{ type: "spring", stiffness: 700, damping: 35 }}
        className="absolute top-[2px] h-[18px] w-[18px] rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,.3)]"
        style={{ left: checked ? 18 : 2 }}
      />
    </button>
  );
}
