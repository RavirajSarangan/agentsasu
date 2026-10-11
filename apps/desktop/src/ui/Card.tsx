import { cx } from "./cx";

export function Card({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx("rounded-[var(--radius-lg)] bg-[var(--surface)] shadow-[var(--shadow)]", className)} {...rest} />;
}

/** A titled group of settings rows, like System Settings. */
export function Group({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <header className="px-1">
        <h2 className="text-[13px] font-semibold">{title}</h2>
        {description && <p className="text-[12px] text-[var(--muted)]">{description}</p>}
      </header>
      <Card className="divide-y divide-[var(--hairline)] px-4">{children}</Card>
    </section>
  );
}

export function Row({ label, hint, children }: { label: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex min-h-[46px] items-center justify-between gap-6 py-2.5">
      <div className="min-w-0">
        <div className="text-[13px]">{label}</div>
        {hint && <div className="text-[11.5px] text-[var(--muted)]">{hint}</div>}
      </div>
      <div className="flex shrink-0 items-center gap-2">{children}</div>
    </div>
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded-[5px] bg-[var(--sunken)] px-1.5 font-sans text-[11px] font-medium text-[var(--muted)] shadow-[inset_0_-1px_0_var(--hairline-strong)]">
      {children}
    </kbd>
  );
}

export function Badge({ color = "var(--muted)", children }: { color?: string; children: React.ReactNode }) {
  return (
    <span
      className="inline-flex h-5 items-center gap-1 rounded-full px-2 text-[11px] font-medium"
      style={{ color, background: `color-mix(in srgb, ${color} 14%, transparent)` }}
    >
      {children}
    </span>
  );
}
