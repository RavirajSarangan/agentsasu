import { useSelector } from "@tanstack/react-store";
import { Check, Download, LoaderCircle, Mic, ShieldCheck, TriangleAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { send } from "../agent/connection";
import { agentStore } from "../agent/store";
import { ListeningBars } from "../robot/StateChip";
import { Button } from "../ui/Button";
import { Badge, Card, Group, Row } from "../ui/Card";

const STATE: Record<string, { label: string; color: string }> = {
  missing: { label: "Off", color: "var(--muted)" },
  downloading: { label: "Downloading", color: "var(--accent)" },
  loading: { label: "Starting", color: "var(--accent)" },
  listening: { label: "Listening", color: "var(--ok)" },
  error: { label: "Problem", color: "var(--danger)" },
};

/** Settings → Voice: one-time model download, then owner voice enrolment. */
export function VoiceSettings({ compact = false }: { compact?: boolean }) {
  const voice = useSelector(agentStore, (s) => s.voice);
  const enroll = useSelector(agentStore, (s) => s.enroll);
  const level = useSelector(agentStore, (s) => s.level);
  const st = STATE[voice?.state ?? "missing"]!;
  const enrolling = enroll && !enroll.done;

  const body = (
    <>
      <Row
        label={
          <span className="flex items-center gap-2">
            <Mic size={14} className="text-[var(--accent)]" /> Voice input
          </span>
        }
        hint={
          voice?.state === "listening"
            ? "Say “Hey Sasu”, press ⌥Space or click the robot. Speech is turned into text on this Mac."
            : `One-time download of on-device models (~${voice?.size_mb ?? 700} MB). Nothing you say is uploaded.`
        }
      >
        {voice?.state === "missing" || voice?.state === "error" || !voice ? (
          <Button variant="primary" size="sm" onClick={() => send({ type: "voice_setup" })}>
            <Download size={13} /> Turn on voice
          </Button>
        ) : (
          <Badge color={st.color}>
            {voice.state === "downloading" || voice.state === "loading" ? <LoaderCircle size={10} className="animate-spin" /> : null}
            {st.label}
          </Badge>
        )}
      </Row>

      {voice?.state === "downloading" && (
        <div className="py-3">
          <div className="h-1.5 overflow-hidden rounded-full bg-[var(--sunken)]">
            <motion.div className="h-full rounded-full bg-[var(--accent)]" animate={{ width: `${Math.round(voice.progress * 100)}%` }} />
          </div>
          <p className="mt-1.5 text-[11.5px] text-[var(--muted)]">
            {Math.round(voice.progress * 100)}% · {voice.detail === "stt" ? "speech model" : voice.detail === "wake" ? "wake-word model" : voice.detail}
          </p>
        </div>
      )}
      {voice?.state === "error" && (
        <p className="flex items-center gap-1.5 py-2 text-[12px] text-[var(--danger)]">
          <TriangleAlert size={13} /> {voice.detail}
        </p>
      )}

      {voice?.state === "listening" && (
        <Row
          label={
            <span className="flex items-center gap-2">
              <ShieldCheck size={14} className="text-[var(--accent)]" /> Owner voice
            </span>
          }
          hint={voice.enrolled ? "Only your voice gets full access. Others are treated as guests." : "Teach Sasu your voice so nobody else can command it."}
        >
          {voice.enrolled && !enrolling && <Badge color="var(--ok)"><Check size={10} strokeWidth={3} /> Enrolled</Badge>}
          {!enrolling && (
            <Button size="sm" variant={voice.enrolled ? "secondary" : "primary"} onClick={() => send({ type: "enroll_start" })}>
              {voice.enrolled ? "Re-enrol" : "Enrol my voice"}
            </Button>
          )}
        </Row>
      )}

      <AnimatePresence>
        {enrolling && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <Card className="my-3 flex flex-col items-center gap-3 px-5 py-5 text-center">
              <p className="text-[11.5px] font-semibold text-[var(--accent)]">
                Phrase {enroll.n + 1} of {enroll.total} — read it out loud
              </p>
              <motion.p key={enroll.phrase} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="text-[18px] font-semibold tracking-tight" lang={/[஀-௿]/.test(enroll.phrase) ? "ta" : "en"}>
                “{enroll.phrase}”
              </motion.p>
              <ListeningBars level={level || 0.05} />
              <div className="flex gap-1.5">
                {Array.from({ length: enroll.total }, (_, i) => (
                  <motion.span key={i} animate={{ scale: i === enroll.n ? 1.3 : 1 }} className="h-2 w-2 rounded-full" style={{ background: i < enroll.n ? "var(--ok)" : "var(--hairline-strong)" }} />
                ))}
              </div>
              <Button size="sm" variant="ghost" onClick={() => send({ type: "enroll_cancel" })}>
                Cancel
              </Button>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );

  if (compact) return <Card className="divide-y divide-[var(--hairline)] px-4">{body}</Card>;
  return (
    <Group title="Voice" description="Hear “Hey Sasu”, understand English & தமிழ், know it's you — all on this Mac.">
      {body}
    </Group>
  );
}
