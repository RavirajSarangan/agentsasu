import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { Play, Sparkles, Wand2 } from "lucide-react";
import { motion } from "motion/react";
import { apiGet, send } from "../agent/connection";
import { agentStore } from "../agent/store";
import { Button } from "../ui/Button";
import { Card, Kbd } from "../ui/Card";

export const Route = createFileRoute("/panel/skills")({ component: SkillsPage });

type Skill = { name: string; steps: number };

/** Routines taught by voice: do something once, then "Sasu, save that as <name>". */
function SkillsPage() {
  const connected = useSelector(agentStore, (s) => s.connection === "open");
  const logSize = useSelector(agentStore, (s) => s.log.length);
  const skills = useQuery({ queryKey: ["skills", logSize], queryFn: () => apiGet<Skill[]>("/api/skills"), enabled: connected });

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-[22px] font-semibold tracking-tight">Skills</h1>
        <p className="text-[13px] text-[var(--muted)]">Teach Sasu a routine once, then run it with one word.</p>
      </header>

      <Card className="flex items-start gap-4 px-6 py-5">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] bg-[var(--accent)] text-white">
          <Wand2 size={20} />
        </span>
        <ol className="flex flex-col gap-1.5 text-[13px]">
          <li>
            <b>1.</b> Ask Sasu to do something — e.g. <i>“volume 20, open Spotify and play”</i>.
          </li>
          <li>
            <b>2.</b> Say <Kbd>Sasu, save that as morning</Kbd>
          </li>
          <li>
            <b>3.</b> Any time later just say <Kbd>Sasu, morning</Kbd> — you'll see the plan first.
          </li>
        </ol>
      </Card>

      {skills.data?.length ? (
        <div className="grid grid-cols-2 gap-3">
          {skills.data.map((sk, i) => (
            <motion.div key={sk.name} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card className="flex items-center gap-3 px-4 py-3.5">
                <Sparkles size={16} className="text-[var(--accent)]" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-semibold capitalize">{sk.name}</p>
                  <p className="text-[11.5px] text-[var(--muted)]">{sk.steps} steps</p>
                </div>
                <Button size="sm" variant="primary" onClick={() => send({ type: "skill_run", name: sk.name })}>
                  <Play size={11} fill="currentColor" /> Run
                </Button>
              </Card>
            </motion.div>
          ))}
        </div>
      ) : (
        <Card className="px-6 py-10 text-center text-[13px] text-[var(--muted)]">{connected ? "No skills yet." : "Connecting…"}</Card>
      )}
    </div>
  );
}
