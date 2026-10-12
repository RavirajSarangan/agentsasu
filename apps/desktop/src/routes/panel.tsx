import { createFileRoute, Link, Outlet, redirect, useRouterState } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { BookHeart, CalendarClock, FlaskConical, House, Settings, ShieldCheck, type LucideIcon, Wand2 } from "lucide-react";
import { motion } from "motion/react";
import { agentStore } from "../agent/store";
import { SasuRobot } from "../robot/SasuRobot";
import { settingsStore } from "../robot/settings";
import { STATE_STYLE } from "../robot/stateStyle";
import { inTauri } from "../tauri";

export const Route = createFileRoute("/panel")({
  beforeLoad: () => {
    if (!settingsStore.get().onboarded) throw redirect({ to: "/onboarding" });
  },
  component: PanelLayout,
});

const NAV: { to: string; label: string; Icon: LucideIcon }[] = [
  { to: "/panel", label: "Home", Icon: House },
  { to: "/panel/skills", label: "Skills", Icon: Wand2 },
  { to: "/panel/tasks", label: "Tasks", Icon: CalendarClock },
  { to: "/panel/memory", label: "Memory", Icon: BookHeart },
  { to: "/panel/settings", label: "Settings", Icon: Settings },
  { to: "/panel/security", label: "Security", Icon: ShieldCheck },
  { to: "/panel/robot-lab", label: "Robot Lab", Icon: FlaskConical },
];

function PanelLayout() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const connection = useSelector(agentStore, (s) => s.connection);
  const demo = useSelector(agentStore, (s) => s.demo);
  const state = useSelector(agentStore, (s) => s.view.state);

  const status =
    connection === "open"
      ? { color: "var(--ok)", text: demo ? "Demo mode" : "Connected" }
      : connection === "connecting"
        ? { color: "var(--warn)", text: "Connecting…" }
        : { color: "var(--danger)", text: "Core offline" };

  return (
    <div className="flex h-full">
      <aside
        className="flex w-[216px] shrink-0 flex-col px-3 pb-3"
        style={{ background: inTauri ? "transparent" : "var(--sidebar)" }}
        data-tauri-drag-region
      >
        <div className="h-[52px] shrink-0" data-tauri-drag-region />
        <div className="mb-5 flex items-center gap-2.5 px-2">
          <SasuRobot size={36} antenna={false} floorShadow={false} interactive={false} />
          <div className="min-w-0">
            <p className="text-[14px] font-semibold tracking-tight">Sasu</p>
            <p className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: status.color }} />
              {status.text}
            </p>
          </div>
        </div>

        <nav className="flex flex-col gap-0.5">
          {NAV.map(({ to, label, Icon }) => {
            const active = path === to || (to !== "/panel" && path.startsWith(to));
            return (
              <Link key={to} to={to} className="relative flex h-8 items-center gap-2.5 rounded-[8px] px-2.5 text-[13px]">
                {active && (
                  <motion.span
                    layoutId="nav-pill"
                    transition={{ type: "spring", stiffness: 500, damping: 40 }}
                    className="absolute inset-0 rounded-[8px] bg-[var(--hairline)]"
                  />
                )}
                <Icon size={15} className="relative" style={{ color: active ? "var(--accent)" : "var(--muted)" }} />
                <span className={`relative ${active ? "font-medium" : ""}`}>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto flex items-center gap-2 rounded-[10px] px-2.5 py-2 text-[11.5px] text-[var(--muted)]">
          {(() => {
            const s = STATE_STYLE[state];
            return (
              <>
                <s.Icon size={13} style={{ color: s.color }} />
                {s.label}
              </>
            );
          })()}
        </div>
      </aside>

      <section className="relative min-w-0 flex-1 overflow-y-auto bg-[var(--bg)] shadow-[-0.5px_0_0_var(--hairline-strong)]">
        <div className="sticky top-0 z-10 h-[38px]" data-tauri-drag-region />
        <motion.div
          key={path}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-[760px] px-8 pb-12"
        >
          <Outlet />
        </motion.div>
      </section>
    </div>
  );
}
