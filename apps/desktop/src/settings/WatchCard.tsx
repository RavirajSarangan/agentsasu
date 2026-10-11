import { useSelector } from "@tanstack/react-store";
import { BatteryCharging, Download, Eye, FileClock, Globe, SquareTerminal, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect } from "react";
import { apiFetch, apiGet } from "../agent/connection";
import { agentStore } from "../agent/store";
import { Card } from "../ui/Card";

const ICON = { download: Download, battery: BatteryCharging, page: Globe, file: FileClock, command: SquareTerminal } as const;
type Row = { id: string; kind: keyof typeof ICON; label: string };

/** Home: what Sasu is keeping an eye on ("download mudinja sollu"), each one cancellable. */
export function WatchCard() {
  const watches = useSelector(agentStore, (s) => s.watches);
  const connected = useSelector(agentStore, (s) => s.connection === "open");

  // after a reconnect, pick up watches the core already had
  useEffect(() => {
    if (!connected) return;
    void apiGet<Row[]>("/api/watch").then((rows) =>
      agentStore.setState((s) => ({ ...s, watches: Object.fromEntries(rows.map((r) => [r.id, { kind: r.kind, label: r.label }])) })),
    );
  }, [connected]);

  const rows = Object.entries(watches);
  if (!rows.length) return null;
  return (
    <Card className="flex flex-col gap-2.5 px-5 py-4">
      <p className="flex items-center gap-2 text-[13px] font-semibold">
        <Eye size={15} className="text-[var(--accent)]" /> Watching
      </p>
      <ul className="flex flex-col gap-1">
        <AnimatePresence initial={false}>
          {rows.map(([id, w]) => {
            const Icon = ICON[w.kind as keyof typeof ICON] ?? Eye;
            return (
              <motion.li
                key={id}
                layout
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 12 }}
                className="flex items-center gap-2.5 rounded-[8px] bg-[var(--sunken)] px-3 py-1.5 text-[12.5px]"
              >
                <Icon size={13} className="text-[var(--accent)]" />
                <span className="flex-1 truncate">{w.label}</span>
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--ok)]" aria-hidden />
                <button aria-label={`Stop watching ${w.label}`} onClick={() => void apiFetch(`/api/watch/${id}`, { method: "DELETE" })} className="text-[var(--muted)] hover:text-[var(--danger)]">
                  <X size={13} />
                </button>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ul>
    </Card>
  );
}
