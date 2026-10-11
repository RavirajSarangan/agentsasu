import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { FileClock, FingerprintPattern, Link2, Lock, LockOpen, Power, ShieldCheck, ShieldX, UserX } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { apiGet, send } from "../agent/connection";
import { agentStore } from "../agent/store";
import { play } from "../sound/player";
import { onShell, setDisabled, shellSecurity, testTouchId } from "../tauri";
import { Button } from "../ui/Button";
import { Badge, Card, Group, Row } from "../ui/Card";

export const Route = createFileRoute("/panel/security")({ component: SecurityPage });

type CoreSecurity = {
  locked: boolean;
  lockReasons: string[];
  voiceprintEnrolled: boolean;
  audit: { ok: boolean; entries: number; brokenAt: number | null };
  bind: string;
};

type AuditEntry = { id: number; at: number; kind: string; data: Record<string, unknown>; hash: string };

const KIND_STYLE: Record<string, { color: string; label: string }> = {
  command: { color: "var(--accent)", label: "Command" },
  approval: { color: "var(--warn)", label: "Approval" },
  rejected: { color: "var(--danger)", label: "Blocked" },
  speaker_rejected: { color: "var(--danger)", label: "Stranger" },
  lock: { color: "var(--muted)", label: "Locked" },
  unlock: { color: "var(--ok)", label: "Unlocked" },
  cancel: { color: "var(--muted)", label: "Stopped" },
  start: { color: "var(--muted)", label: "Started" },
  stop: { color: "var(--muted)", label: "Stopped core" },
};

function SecurityPage() {
  const connected = useSelector(agentStore, (s) => s.connection === "open");
  const logSize = useSelector(agentStore, (s) => s.log.length);
  const locks = useSelector(agentStore, (s) => s.view.locks);
  const [shell, setShell] = useState<{ locks: string[]; touch_id: boolean }>({ locks: [], touch_id: false });
  const [touchResult, setTouchResult] = useState<boolean | null>(null);

  const sec = useQuery({ queryKey: ["security", logSize], queryFn: () => apiGet<CoreSecurity>("/api/security"), enabled: connected });
  const audit = useQuery({ queryKey: ["audit", logSize], queryFn: () => apiGet<AuditEntry[]>("/api/audit?limit=60"), enabled: connected });

  useEffect(() => {
    const refresh = () => void shellSecurity().then(setShell);
    refresh();
    const offs = [onShell("disabled-changed", refresh), onShell("session-locked", refresh), onShell("request-enable", () => void enable())];
    return () => offs.forEach((off) => off());
  }, []);

  const disabled = locks.includes("disabled") || shell.locks.includes("disabled");
  const enable = async () => {
    const ok = await setDisabled(false);
    if (!ok) play("error", { force: true });
    void shellSecurity().then(setShell);
  };

  const chain = sec.data?.audit;
  const strangers = audit.data?.filter((e) => e.kind === "speaker_rejected").length ?? 0;
  const blocked = audit.data?.filter((e) => e.kind === "rejected").length ?? 0;

  return (
    <div className="flex flex-col gap-7">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Security</h1>
          <p className="text-[13px] text-[var(--muted)]">Only you can command Sasu. Everything it does is recorded.</p>
        </div>
        {disabled ? (
          <Button variant="primary" onClick={() => void enable()}>
            <Power size={14} /> Turn Sasu on
          </Button>
        ) : (
          <Button variant="danger" onClick={() => void setDisabled(true)}>
            <Power size={14} /> Disable Sasu
          </Button>
        )}
      </header>

      <div className="grid grid-cols-3 gap-3">
        <Stat
          icon={locks.length ? Lock : LockOpen}
          color={locks.length ? "var(--warn)" : "var(--ok)"}
          title={locks.length ? "Locked" : "Active"}
          detail={locks.length ? `by ${locks.join(", ")}` : "Listening for you"}
        />
        <Stat
          icon={chain?.ok === false ? ShieldX : ShieldCheck}
          color={chain?.ok === false ? "var(--danger)" : "var(--ok)"}
          title={chain ? (chain.ok ? "Log intact" : "Log tampered!") : "—"}
          detail={chain ? (chain.ok ? `${chain.entries} sealed entries` : `broken at #${chain.brokenAt}`) : "connecting…"}
        />
        <Stat icon={UserX} color={strangers + blocked ? "var(--danger)" : "var(--muted)"} title={`${strangers + blocked} blocked`} detail={`${strangers} strangers · ${blocked} bad requests`} />
      </div>

      <Group title="Who can command Sasu">
        <Row label="Owner voice only" hint={sec.data?.voiceprintEnrolled ? "Your voiceprint is enrolled and encrypted on this Mac." : "Enrol your voice in the setup assistant (arrives with voice input)."}>
          <Badge color={sec.data?.voiceprintEnrolled ? "var(--ok)" : "var(--warn)"}>{sec.data?.voiceprintEnrolled ? "Enrolled" : "Not enrolled"}</Badge>
        </Row>
        <Row label="Touch ID for dangerous actions" hint="Deleting, system changes and anything outside your home folder.">
          {touchResult !== null && <Badge color={touchResult ? "var(--ok)" : "var(--danger)"}>{touchResult ? "Passed" : "Failed"}</Badge>}
          <Button size="sm" disabled={!shell.touch_id} onClick={() => void testTouchId().then(setTouchResult)}>
            <FingerprintPattern size={13} /> {shell.touch_id ? "Test" : "Unavailable"}
          </Button>
        </Row>
        <Row label="Goes deaf when your Mac locks" hint="Screen lock and screensaver stop the mic and cancel any task.">
          <Badge color="var(--ok)">On</Badge>
        </Row>
        <Row label="Kill switch" hint="⌘⌥Esc stops everything and denies pending approvals.">
          <Button size="sm" onClick={() => send({ type: "lock" })}>
            <Lock size={13} /> Lock now
          </Button>
        </Row>
      </Group>

      <Group title="Connection">
        <Row label="Local only" hint="The agent core listens on 127.0.0.1 with a new 256-bit token each launch, passed privately.">
          <Badge color="var(--ok)">
            <Link2 size={11} /> {sec.data?.bind ?? "127.0.0.1"}
          </Badge>
        </Row>
        <Row label="Locked-down windows" hint="Strict content policy; the robot window can only talk, move and ask for Touch ID.">
          <Badge color="var(--ok)">On</Badge>
        </Row>
      </Group>

      <section className="flex flex-col gap-2">
        <h2 className="flex items-center gap-1.5 px-1 text-[13px] font-semibold">
          <FileClock size={14} /> Audit log
        </h2>
        <Card className="max-h-[420px] overflow-y-auto">
          {!audit.data?.length ? (
            <p className="px-5 py-8 text-center text-[13px] text-[var(--muted)]">{connected ? "No entries yet." : "Connecting to the core…"}</p>
          ) : (
            <ol className="divide-y divide-[var(--hairline)]">
              {audit.data.map((e) => {
                const k = KIND_STYLE[e.kind] ?? { color: "var(--muted)", label: e.kind };
                return (
                  <motion.li key={e.id} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3 px-4 py-2 text-[12px]">
                    <span className="w-[76px] shrink-0 whitespace-nowrap tabular-nums text-[var(--faint)]">{new Date(e.at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
                    <span className="w-20 shrink-0">
                      <Badge color={k.color}>{k.label}</Badge>
                    </span>
                    <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-[var(--muted)]">{describe(e)}</span>
                    <span className="shrink-0 font-mono text-[10px] text-[var(--faint)]" title={e.hash}>
                      #{e.hash.slice(0, 8)}
                    </span>
                  </motion.li>
                );
              })}
            </ol>
          )}
        </Card>
      </section>
    </div>
  );
}

function describe(e: AuditEntry): string {
  const d = e.data;
  if (e.kind === "command") return String(d.text ?? d.source ?? "");
  if (e.kind === "approval") return `${d.step} · ${d.ok ? "approved" : "denied"} · ${d.prompt}`;
  if (e.kind === "rejected") return `${d.reason}${d.origin ? ` from ${d.origin}` : ""}`;
  if (e.kind === "speaker_rejected") return `voice match ${d.score}`;
  if (e.kind === "lock" || e.kind === "unlock") return String(d.reason);
  return JSON.stringify(d);
}

function Stat({ icon: Icon, color, title, detail }: { icon: typeof Lock; color: string; title: string; detail: string }) {
  return (
    <Card className="flex items-center gap-3 px-4 py-3.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-[10px]" style={{ color, background: `color-mix(in srgb, ${color} 14%, transparent)` }}>
        <Icon size={18} />
      </span>
      <div className="min-w-0">
        <p className="text-[13px] font-semibold">{title}</p>
        <p className="truncate text-[11.5px] text-[var(--muted)]">{detail}</p>
      </div>
    </Card>
  );
}
