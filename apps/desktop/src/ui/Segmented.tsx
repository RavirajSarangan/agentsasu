import { motion } from "motion/react";
import { useId } from "react";
import { play } from "../sound/player";
import { cx } from "./cx";

type Option<T extends string> = { value: T; label: React.ReactNode };

/** macOS segmented control with a sliding thumb. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  className,
  size = "md",
}: {
  value: T;
  options: readonly Option<T>[];
  onChange: (v: T) => void;
  className?: string;
  size?: "sm" | "md";
}) {
  const id = useId();
  return (
    <div role="radiogroup" className={cx("inline-flex rounded-[9px] bg-[var(--sunken)] p-[2px]", className)}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="radio"
            aria-checked={active}
            onClick={() => {
              if (active) return;
              play("click");
              onChange(o.value);
            }}
            className={cx(
              "relative flex-1 whitespace-nowrap rounded-[7px] font-medium capitalize transition-colors",
              size === "sm" ? "h-6 px-2.5 text-[11.5px]" : "h-7 px-3 text-[12.5px]",
              active ? "text-[var(--text)]" : "text-[var(--muted)] hover:text-[var(--text)]",
            )}
          >
            {active && (
              <motion.span
                layoutId={`seg-${id}`}
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
                className="absolute inset-0 rounded-[7px] bg-[var(--surface)] shadow-[var(--shadow-sm)]"
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
