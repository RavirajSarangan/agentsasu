import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { CalendarClock, CircleAlert, CircleCheck, CircleX, LoaderCircle, Play, Plus, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { apiFetch, apiGet } from "../agent/connection";
import { agentStore } from "../agent/store";
import { Button } from "../ui/Button";
import { Badge, Card, Kbd } from "../ui/Card";
import { Switch } from "../ui/Switch";

export const Route = createFileRoute("/panel/tasks")({ component: TasksPage });

type Task = {
  id: string;
  request: string;
  days: number[];
  hour: number;
  minute: number;
  enabled: boolean;
  when: string;
  last_state: "" | "done" | "needs_you" | "failed";
  last_summary: string;
};

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const field =
  "h-8 rounded-[8px] bg-[var(--sunken)] px-3 text-[12.5px] outline-none placeholder:text-[var(--faint)] focus:shadow-[0_0_0_3px_var(--accent-glow)]";

/** Scheduled tasks: "Daily 9 mani-ku mail summary pannu". Risky steps always wait for you. */
function TasksPage() {
  const connected = useSelector(agentStore, (s) => s.connection === "open");
  // refetch whenever a task event arrives
  const lastTask = useSelector(agentStore, (s) => s.log.find((l) => l.event.type === "task")?.at ?? 0);
  const running = useSelector(agentStore, (s) => {
    const e = s.log.find((l) => l.event.type === "task")?.event;
    return e?.type === "task" && e.state === "running" ? e.id : null;
  });
  const qc = useQueryClient();
  const tasks = useQuery({ queryKey: ["tasks", lastTask], queryFn: () => apiGet<Task[]>("/api/tasks"), enabled: connected });
  const refresh = () => qc.invalidateQueries({ queryKey: ["tasks"] });
  const post = (path: string) => apiFetch(path, { method: "POST" }).then(refresh);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-[22px] font-semibold tracking-tight">Tasks</h1>
        <p className="text-[13px] text-[var(--muted)]">Things Sasu does on a schedule. Anything risky waits for your yes.</p>
      </header>

      <Card className="flex items-start gap-4 px-6 py-5">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] bg-[var(--accent)] text-white">
          <CalendarClock size={20} />
        </span>
        <div className="flex flex-col gap-1.5 text-[13px]">
          <p>Just say it:</p>
          <p className="flex flex-wrap gap-1.5">
            <Kbd>Daily 9 mani-ku mail summary pannu</Kbd>
            <Kbd>every Sunday Desktop clean pannu</Kbd>
            <Kbd>weekdays 8:30-ku good morning sollu</Kbd>
          </p>
          <p className="text-[12px] text-[var(--muted)]">
            If a task needs your OK while you're away, it stops and tells you. Say <Kbd>Sasu, run it</Kbd> or press Run.
          </p>
        </div>
      </Card>

      {tasks.data && tasks.data.length > 0 && (
        <Card className="flex flex-col divide-y divide-[var(--hairline)] px-5 py-1">
          {tasks.data.map((t, i) => (
            <motion.div key={t.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }} className="flex items-center gap-3 py-3">
              <Switch checked={t.enabled} onChange={() => void post(`/api/tasks/${t.id}/toggle`)} label={`Enable ${t.request}`} />
              <div className="min-w-0 flex-1">
                <p className={`truncate text-[13px] font-medium ${t.enabled ? "" : "text-[var(--muted)] line-through"}`}>“{t.request}”</p>
                <p className="truncate text-[11.5px] text-[var(--muted)]">
                  {t.when}
                  {t.last_summary && ` · ${t.last_summary}`}
                </p>
              </div>
              <Status task={t} running={running === t.id} />
              <Button size="sm" variant={t.last_state === "needs_you" ? "primary" : "ghost"} onClick={() => void post(`/api/tasks/${t.id}/run`)} aria-label={`Run ${t.request} now`}>
                <Play size={12} /> {t.last_state === "needs_you" ? "Run it" : "Run"}
              </Button>
              <button aria-label={`Delete ${t.request}`} onClick={() => void apiFetch(`/api/tasks/${t.id}`, { method: "DELETE" }).then(refresh)} className="text-[var(--muted)] hover:text-[var(--danger)]">
                <Trash2 size={14} />
              </button>
            </motion.div>
          ))}
        </Card>
      )}

      <AddTask onAdded={refresh} />
    </div>
  );
}

function Status({ task, running }: { task: Task; running: boolean }) {
  if (running)
    return (
      <Badge color="var(--accent)">
        <LoaderCircle size={10} className="animate-spin" /> Running
      </Badge>
    );
  if (task.last_state === "done")
    return (
      <Badge color="var(--ok)">
        <CircleCheck size={10} /> Done
      </Badge>
    );
  if (task.last_state === "needs_you")
    return (
      <Badge color="var(--warn)">
        <CircleAlert size={10} /> Needs you
      </Badge>
    );
  if (task.last_state === "failed")
    return (
      <Badge color="var(--danger)">
        <CircleX size={10} /> Failed
      </Badge>
    );
  return null;
}

function AddTask({ onAdded }: { onAdded: () => void }) {
  const [request, setRequest] = useState("");
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6]);
  const [time, setTime] = useState("09:00");
  const add = async () => {
    const [hour, minute] = time.split(":").map(Number);
    await apiFetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request: request.trim(), days, hour, minute }),
    });
    setRequest("");
    onAdded();
  };
  return (
    <Card className="flex flex-col gap-3 px-5 py-4">
      <p className="text-[13px] font-semibold">Add a task</p>
      <input aria-label="What should Sasu do" value={request} onChange={(e) => setRequest(e.target.value)} placeholder="Desktop clean pannu" maxLength={200} className={field} />
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Days" className="flex gap-1">
          {DAYS.map((d, i) => {
            const on = days.includes(i);
            return (
              <button
                key={d}
                aria-pressed={on}
                onClick={() => setDays(on ? days.filter((x) => x !== i) : [...days, i].sort())}
                className="h-7 w-9 rounded-[7px] text-[11.5px] font-semibold"
                style={{ background: on ? "var(--accent)" : "var(--sunken)", color: on ? "white" : "var(--muted)" }}
              >
                {d}
              </button>
            );
          })}
        </div>
        <input aria-label="Time" type="time" value={time} onChange={(e) => setTime(e.target.value)} className={`${field} w-[122px]`} />
        <Button size="sm" variant="primary" disabled={request.trim().length < 3 || !days.length || !time} onClick={() => void add()}>
          <Plus size={13} /> Add
        </Button>
      </div>
    </Card>
  );
}
