import { useSelector } from "@tanstack/react-store";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, HeartPulse, Pill, Plus, Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { apiFetch, apiGet } from "../agent/connection";
import { agentStore } from "../agent/store";
import { settingsStore, updateSettings } from "../robot/settings";
import { Button } from "../ui/Button";
import { Badge, Card, Group, Row } from "../ui/Card";

type Dose = { id: string; who: string; what: string; hour: number; minute: number; status: "upcoming" | "asked" | "taken" | "missed" };

const field =
  "h-8 rounded-[8px] bg-[var(--sunken)] px-3 text-[12.5px] outline-none placeholder:text-[var(--faint)] focus:shadow-[0_0_0_3px_var(--accent-glow)]";

const STATUS = {
  upcoming: { label: "Later", color: "var(--muted)" },
  asked: { label: "Asked", color: "var(--warn)" },
  taken: { label: "Taken", color: "var(--ok)" },
  missed: { label: "Missed", color: "var(--danger)" },
} as const;

const clock = (d: Dose) => `${d.hour % 12 || 12}:${String(d.minute).padStart(2, "0")} ${d.hour >= 12 ? "PM" : "AM"}`;

function useDoses() {
  const connected = useSelector(agentStore, (s) => s.connection === "open");
  const careAt = useSelector(agentStore, (s) => s.careAt);
  return useQuery({ queryKey: ["care", careAt], queryFn: () => apiGet<Dose[]>("/api/care"), enabled: connected, refetchInterval: 60_000 });
}

function DoseList({ doses, onRemove }: { doses: Dose[]; onRemove?: (id: string) => void }) {
  return (
    <ul className="flex flex-col gap-1">
      {doses.map((d) => (
        <li key={d.id} className="flex items-center gap-2.5 rounded-[8px] bg-[var(--sunken)] px-3 py-1.5 text-[12.5px]">
          <Pill size={13} className="text-[var(--accent)]" />
          <span className="w-[64px] tabular-nums text-[var(--muted)]">{clock(d)}</span>
          <span className="flex-1 truncate">
            <span className="font-medium capitalize">{d.who}</span> · {d.what}
          </span>
          <Badge color={STATUS[d.status].color}>
            {d.status === "taken" ? <Check size={10} strokeWidth={3} /> : d.status === "missed" ? <TriangleAlert size={10} /> : null} {STATUS[d.status].label}
          </Badge>
          {onRemove && (
            <button aria-label={`Remove ${d.what} for ${d.who}`} onClick={() => onRemove(d.id)} className="text-[var(--muted)] hover:text-[var(--danger)]">
              <Trash2 size={13} />
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Home: today's medicine schedule (only when Amma mode has reminders). */
export function CareCard() {
  const doses = useDoses();
  if (!doses.data?.length) return null;
  return (
    <Card className="flex flex-col gap-2.5 px-5 py-4">
      <p className="flex items-center gap-2 text-[13px] font-semibold">
        <HeartPulse size={15} className="text-[var(--accent)]" /> Care today
      </p>
      <DoseList doses={doses.data} />
    </Card>
  );
}

/** Settings → Amma mode: medicine reminders and who "son" / "daughter" are. */
export function CareSettings() {
  const s = useSelector(settingsStore);
  const qc = useQueryClient();
  const doses = useDoses();
  const [who, setWho] = useState("amma");
  const [what, setWhat] = useState("");
  const [time, setTime] = useState("08:00");
  const refresh = () => qc.invalidateQueries({ queryKey: ["care"] });

  const add = async () => {
    const [hour, minute] = time.split(":").map(Number);
    await apiFetch("/api/care", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ who: who.trim(), what: what.trim(), hour, minute }),
    });
    setWhat("");
    void refresh();
  };

  return (
    <Group
      title="Amma mode"
      description="Sasu looks after elders: slow Tamil, big text, medicine reminders, calling family by voice and a “help” alert. Enrol them as Elder under Voice → Family."
    >
      <div className="flex flex-col gap-2 py-3.5">
        <p className="text-[12px] text-[var(--muted)]">
          Medicine reminders — or just say “Amma-ku 8 mani BP maathirai reminder vai”. Sasu asks at the time, repeats once after 15 minutes, then texts your emergency contact.
        </p>
        {doses.data && doses.data.length > 0 && (
          <DoseList doses={doses.data} onRemove={(id) => void apiFetch(`/api/care/${id}`, { method: "DELETE" }).then(refresh)} />
        )}
        <div className="flex flex-wrap items-center gap-2">
          <input aria-label="Who" value={who} onChange={(e) => setWho(e.target.value)} placeholder="amma" maxLength={40} className={`${field} w-[90px]`} />
          <input aria-label="Medicine" value={what} onChange={(e) => setWhat(e.target.value)} placeholder="BP tablet" maxLength={80} className={`${field} min-w-0 flex-1`} />
          <input aria-label="Time" type="time" value={time} onChange={(e) => setTime(e.target.value)} className={`${field} w-[122px]`} />
          <Button size="sm" variant="primary" disabled={!who.trim() || !what.trim() || !time} onClick={() => void add()}>
            <Plus size={13} /> Add
          </Button>
        </div>
      </div>
      <Row label="Son" hint="“magan-ku call pannu” calls this contact.">
        <NameField value={s.sonName} placeholder="Raviraj" onSave={(sonName) => updateSettings({ sonName })} />
      </Row>
      <Row label="Daughter" hint="“magal-ku call pannu” calls this contact.">
        <NameField value={s.daughterName} placeholder="Name in Contacts" onSave={(daughterName) => updateSettings({ daughterName })} />
      </Row>
    </Group>
  );
}

function NameField({ value, placeholder, onSave }: { value: string; placeholder: string; onSave: (v: string) => void }) {
  const [draft, setDraft] = useState(value);
  return (
    <input
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => draft !== value && onSave(draft.trim())}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      placeholder={placeholder}
      maxLength={60}
      className={`${field} w-[200px]`}
    />
  );
}
