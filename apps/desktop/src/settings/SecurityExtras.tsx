import { useQuery } from "@tanstack/react-query";
import { useSelector } from "@tanstack/react-store";
import { Bug, Ghost, KeyRound, Lock, Siren, Timer } from "lucide-react";
import { useState } from "react";
import { apiGet, send } from "../agent/connection";
import { agentStore } from "../agent/store";
import { settingsStore, updateSettings } from "../robot/settings";
import { play } from "../sound/player";
import { unlockSecure } from "../tauri";
import { Button } from "../ui/Button";
import { Badge, Card, Group, Row } from "../ui/Card";
import { Segmented } from "../ui/Segmented";
import { Switch } from "../ui/Switch";

type AuditEntry = { id: number; at: number; kind: string; data: Record<string, unknown> };

const LOCK_TEXT: Record<string, string> = {
  panic: "Locked by your panic word",
  canary: "Locked: something touched a trap file",
  away: "Locked while you're away",
};

/** Security page extras: active locks, trap files, panic word, away lock, intruder log. */
export function SecurityExtras() {
  const s = useSelector(settingsStore);
  const locks = useSelector(agentStore, (st) => st.view.locks);
  const connected = useSelector(agentStore, (st) => st.connection === "open");
  const logSize = useSelector(agentStore, (st) => st.log.length);
  const [panic, setPanic] = useState("");
  const [panicSaved, setPanicSaved] = useState(false);
  const intruders = useQuery({
    queryKey: ["intruders", logSize],
    queryFn: async () => (await apiGet<AuditEntry[]>("/api/audit?limit=300")).filter((e) => e.kind === "intruder" || e.kind === "alarm"),
    enabled: connected,
  });

  const secureLocks = locks.filter((l) => l in LOCK_TEXT);

  return (
    <>
      {secureLocks.length > 0 && (
        <Card className="flex items-center gap-3 px-5 py-4" style={{ boxShadow: "0 0 0 1.5px var(--danger), var(--shadow)" }}>
          <Siren size={20} className="text-[var(--danger)]" />
          <div className="flex-1">
            {secureLocks.map((l) => (
              <p key={l} className="text-[13.5px] font-semibold">
                {LOCK_TEXT[l]}
              </p>
            ))}
            <p className="text-[12px] text-[var(--muted)]">Unlocking needs Touch ID or your Mac password.</p>
          </div>
          {secureLocks.map((l) => (
            <Button key={l} variant="primary" size="sm" onClick={() => void unlockSecure(l).then((ok) => play(ok ? "success" : "error", { force: true }))}>
              <Lock size={13} /> Unlock
            </Button>
          ))}
        </Card>
      )}

      <Group title="Traps and alarms" description="Extra protection against tricks, intruders and leaks.">
        <Row
          label={
            <span className="flex items-center gap-2">
              <Bug size={14} className="text-[var(--accent)]" /> Trap files
            </span>
          }
          hint="Decoy “password” files in Documents and Desktop. If anything — even a tricked AI — touches them, Sasu locks itself."
        >
          <Switch label="Trap files" checked={s.canaries} onChange={(canaries) => updateSettings({ canaries })} />
        </Row>
        <Row
          label={
            <span className="flex items-center gap-2">
              <Timer size={14} className="text-[var(--accent)]" /> Away lock
            </span>
          }
          hint="Stop listening when your Mac has been idle for a while."
        >
          <Segmented
            size="sm"
            value={String(s.awayMinutes)}
            onChange={(v) => updateSettings({ awayMinutes: Number(v) })}
            options={[
              { value: "0", label: "Off" },
              { value: "5", label: "5 min" },
              { value: "15", label: "15 min" },
            ]}
          />
        </Row>
        <div className="flex flex-col gap-2 py-3.5">
          <p className="flex items-center gap-2 text-[13px]">
            <KeyRound size={14} className="text-[var(--accent)]" /> Panic word
          </p>
          <p className="text-[11.5px] text-[var(--muted)]">Say or type it and Sasu locks instantly until Touch ID. Only a salted hash is kept.</p>
          <div className="flex gap-2">
            <input
              type="password"
              value={panic}
              onChange={(e) => setPanic(e.target.value)}
              placeholder="e.g. mango lassi"
              className="h-8 flex-1 rounded-[8px] bg-[var(--sunken)] px-3 text-[12.5px] outline-none focus:shadow-[0_0_0_3px_var(--accent-glow)]"
            />
            <Button
              size="sm"
              variant="primary"
              disabled={panic.trim().length < 3}
              onClick={() => {
                send({ type: "set_settings", settings: { panic_word: panic } });
                setPanic("");
                setPanicSaved(true);
                play("success", { force: true });
              }}
            >
              {panicSaved ? "Saved" : "Set"}
            </Button>
          </div>
        </div>
      </Group>

      <section className="flex flex-col gap-2">
        <h2 className="flex items-center gap-1.5 px-1 text-[13px] font-semibold">
          <Ghost size={14} /> Intruders and alarms
        </h2>
        <Card className="max-h-[260px] overflow-y-auto">
          {!intruders.data?.length ? (
            <p className="px-5 py-6 text-center text-[13px] text-[var(--muted)]">Nobody has tried anything. 👍</p>
          ) : (
            <ol className="divide-y divide-[var(--hairline)]">
              {intruders.data.map((e) => (
                <li key={e.id} className="flex items-center gap-3 px-4 py-2.5 text-[12.5px]">
                  <span className="w-[120px] shrink-0 text-[var(--faint)]">{new Date(e.at * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                  <Badge color={e.kind === "alarm" ? "var(--danger)" : "var(--warn)"}>{e.kind === "alarm" ? String(e.data.alarm) : "stranger"}</Badge>
                  <span className="min-w-0 flex-1 truncate">{String(e.data.text ?? e.data.detail ?? "")}</span>
                  {typeof e.data.score === "number" && <span className="text-[11px] text-[var(--faint)]">voice {Math.round(Number(e.data.score) * 100)}%</span>}
                </li>
              ))}
            </ol>
          )}
        </Card>
      </section>
    </>
  );
}
