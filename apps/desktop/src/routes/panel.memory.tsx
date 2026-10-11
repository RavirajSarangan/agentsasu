import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { BookHeart, Lock, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { apiFetch, apiGet } from "../agent/connection";
import { agentStore } from "../agent/store";
import { Card, Kbd } from "../ui/Card";

export const Route = createFileRoute("/panel/memory")({ component: MemoryPage });

type Fact = { id: string; text: string; at: number };

/** Things you asked Sasu to remember. Encrypted on this Mac; only your voice can read them. */
function MemoryPage() {
  const connected = useSelector(agentStore, (s) => s.connection === "open");
  const logSize = useSelector(agentStore, (s) => s.log.length);
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const facts = useQuery({ queryKey: ["memory", logSize], queryFn: () => apiGet<Fact[]>("/api/memory"), enabled: connected });
  const shown = (facts.data ?? []).filter((f) => f.text.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-[22px] font-semibold tracking-tight">Memory</h1>
        <p className="flex items-center gap-1.5 text-[13px] text-[var(--muted)]">
          <Lock size={12} /> Encrypted on this Mac. Only your voice can save or ask for these.
        </p>
      </header>
      <Card className="flex items-start gap-4 px-6 py-5 text-[13px]">
        <BookHeart size={22} className="mt-0.5 shrink-0 text-[var(--accent)]" />
        <div className="flex flex-col gap-1.5">
          <p>
            Save: <Kbd>Sasu, remember amma's birthday is June 3</Kbd>
          </p>
          <p>
            Ask: <Kbd>what did I tell you about amma's birthday?</Kbd> · Forget: <Kbd>forget amma's birthday</Kbd>
          </p>
        </div>
      </Card>
      <div className="flex h-9 items-center gap-2 rounded-[10px] bg-[var(--sunken)] px-3">
        <Search size={14} className="text-[var(--muted)]" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search memories" className="flex-1 bg-transparent text-[13px] outline-none" />
      </div>
      <Card>
        {!shown.length ? (
          <p className="px-6 py-10 text-center text-[13px] text-[var(--muted)]">{connected ? "Nothing remembered yet." : "Connecting…"}</p>
        ) : (
          <ul className="divide-y divide-[var(--hairline)]">
            {shown.map((f) => (
              <li key={f.id} className="flex items-center gap-3 px-5 py-3 text-[13.5px]">
                <span className="flex-1">{f.text}</span>
                <span className="text-[11px] text-[var(--faint)]">{new Date(f.at * 1000).toLocaleDateString()}</span>
                <button
                  aria-label="Forget this"
                  className="text-[var(--muted)] hover:text-[var(--danger)]"
                  onClick={() => void apiFetch(`/api/memory/${f.id}`, { method: "DELETE" }).then(() => qc.invalidateQueries({ queryKey: ["memory"] }))}
                >
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
