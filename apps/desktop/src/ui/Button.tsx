import { motion, type HTMLMotionProps } from "motion/react";
import { forwardRef } from "react";
import { play } from "../sound/player";
import { cx } from "./cx";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANT: Record<Variant, string> = {
  primary: "bg-[var(--accent)] text-[var(--accent-contrast)] shadow-[0_1px_2px_rgba(0,0,0,.15),inset_0_1px_0_rgba(255,255,255,.18)] hover:brightness-110",
  secondary: "bg-[var(--surface)] text-[var(--text)] shadow-[var(--shadow-sm)] hover:bg-[var(--surface-2)]",
  ghost: "text-[var(--text)] hover:bg-[var(--hairline)]",
  danger: "bg-[var(--danger)] text-white shadow-[0_1px_2px_rgba(0,0,0,.15)] hover:brightness-110",
};

const SIZE: Record<Size, string> = {
  sm: "h-7 px-2.5 text-[12px] gap-1.5 rounded-[7px]",
  md: "h-8 px-3.5 text-[13px] gap-2 rounded-[8px]",
  lg: "h-11 px-5 text-[14px] gap-2 rounded-[11px]",
};

export type ButtonProps = HTMLMotionProps<"button"> & { variant?: Variant; size?: Size; quiet?: boolean };

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", quiet, className, onClick, ...rest },
  ref,
) {
  return (
    <motion.button
      ref={ref}
      whileTap={{ scale: 0.96 }}
      transition={{ type: "spring", stiffness: 600, damping: 30 }}
      className={cx(
        "inline-flex select-none items-center justify-center font-medium transition-[background,filter,box-shadow] duration-150 disabled:pointer-events-none disabled:opacity-40",
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      onClick={(e) => {
        if (!quiet) play("click", { force: false });
        onClick?.(e);
      }}
      {...rest}
    />
  );
});

export function IconButton({ label, className, ...rest }: ButtonProps & { label: string }) {
  return <Button variant="ghost" size="sm" aria-label={label} title={label} className={cx("!px-0 w-7", className)} {...rest} />;
}
