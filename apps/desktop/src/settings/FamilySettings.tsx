import { useSelector } from "@tanstack/react-store";
import { Trash2, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { send } from "../agent/connection";
import { agentStore } from "../agent/store";
import { Button } from "../ui/Button";
import { Badge, Row } from "../ui/Card";
import { Segmented } from "../ui/Segmented";

const ROLE_HINT = {
  owner: "Everything (risky steps still need Touch ID)",
  family: "Everything except risky steps and terminal commands",
  kid: "Music, volume, time, jokes and YouTube only",
} as const;
type Role = keyof typeof ROLE_HINT;

/** Family profiles: who Sasu knows by voice, and what each may do. */
export function FamilySettings() {
  const voice = useSelector(agentStore, (s) => s.voice);
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("family");
  if (voice?.state !== "listening") return null;
  const people = voice.profiles ?? [];

  return (
    <div className="flex flex-col gap-2 py-3.5">
      <p className="flex items-center gap-2 text-[13px]">
        <Users size={14} className="text-[var(--accent)]" /> Family
      </p>
      {people.length > 0 && (
        <ul className="flex flex-col gap-1">
          {people.map((p) => {
            const [who, r] = [p.replace(/\s*\(.*\)$/, ""), p.match(/\((\w+)\)/)?.[1] ?? ""];
            return (
              <li key={p} className="flex items-center gap-2 rounded-[8px] bg-[var(--sunken)] px-3 py-1.5 text-[12.5px]">
                <span className="flex-1 font-medium">{who}</span>
                <Badge color={r === "owner" ? "var(--accent)" : r === "kid" ? "var(--warn)" : "var(--ok)"}>{r}</Badge>
                {r !== "owner" && (
                  <button aria-label={`Remove ${who}`} onClick={() => send({ type: "profile_remove", name: who })} className="text-[var(--muted)] hover:text-[var(--danger)]">
                    <Trash2 size={13} />
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <Row label="Add a person" hint={ROLE_HINT[role]}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Amma"
          maxLength={40}
          className="h-8 w-[110px] rounded-[8px] bg-[var(--sunken)] px-3 text-[12.5px] outline-none focus:shadow-[0_0_0_3px_var(--accent-glow)]"
        />
        <Segmented
          size="sm"
          value={role}
          onChange={setRole}
          options={[
            { value: "family", label: "Family" },
            { value: "kid", label: "Kid" },
          ]}
        />
        <Button
          size="sm"
          variant="primary"
          disabled={!name.trim()}
          onClick={() => {
            send({ type: "enroll_start", name: name.trim(), role });
            setName("");
          }}
        >
          <UserPlus size={13} /> Enrol
        </Button>
      </Row>
    </div>
  );
}
