import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { disable as disableAutostart, enable as enableAutostart, isEnabled as autostartEnabled } from "@tauri-apps/plugin-autostart";
import {
  AppWindow,
  ArrowLeft,
  ArrowRight,
  Check,
  FingerprintPattern,
  Keyboard,
  Mic,
  MonitorUp,
  PartyPopper,
  Rocket,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { RobotHead, robotHeadShapes, type RobotHeadState } from "robot-heads";
import { useEffect, useState } from "react";
import { Halo } from "../robot/Halo";
import { settingsStore, updateSettings } from "../robot/settings";
import { themes, type ThemeName } from "../robot/themes";
import { play } from "../sound/player";
import { inTauri, permissionsStatus, requestPermission, testTouchId, type PermissionKind, type Permissions } from "../tauri";
import { Button } from "../ui/Button";
import { Badge, Card, Kbd } from "../ui/Card";
import { cx } from "../ui/cx";
import { Segmented } from "../ui/Segmented";
import { BrainSettings } from "../settings/BrainSettings";
import { VoiceSettings } from "../settings/VoiceSettings";
import { Switch } from "../ui/Switch";

export const Route = createFileRoute("/onboarding")({ component: Onboarding });

type Step = { id: string; robot: RobotHeadState; title: string; ta: string };

const STEPS: Step[] = [
  { id: "welcome", robot: "happy", title: "Hey, I'm Sasu", ta: "வணக்கம், நான் சாசு" },
  { id: "permissions", robot: "searching", title: "Let me help on your Mac", ta: "உங்க Mac-ல உதவ அனுமதி" },
  { id: "brain", robot: "thinking", title: "Give me a brain", ta: "எனக்கு ஒரு மூளை குடுங்க" },
  { id: "voice", robot: "listening", title: "Teach me your voice", ta: "உங்க குரலை சொல்லிக்கொடுங்க" },
  { id: "security", robot: "thinking", title: "Keep it yours", ta: "பாதுகாப்பு" },
  { id: "robot", robot: "happy", title: "Pick your robot", ta: "உங்க robot-ஐ தேர்ந்தெடுங்க" },
  { id: "done", robot: "happy", title: "All set!", ta: "எல்லாம் தயார்!" },
];

function Onboarding() {
  const [index, setIndex] = useState(0);
  const [dir, setDir] = useState(1);
  const navigate = useNavigate();
  const s = useSelector(settingsStore);
  const step = STEPS[index]!;
  const theme = themes[s.theme];

  const go = (delta: number) => {
    const next = index + delta;
    if (next < 0) return;
    if (next >= STEPS.length) {
      updateSettings({ onboarded: true });
      play("success", { force: true });
      void navigate({ to: "/panel" });
      return;
    }
    play(delta > 0 ? "toggle" : "click");
    setDir(delta);
    setIndex(next);
  };

  useEffect(() => {
    if (step.id === "done") play("success", { force: true });
  }, [step.id]);

  return (
    <div className="flex h-full flex-col bg-[var(--bg)]">
      <div className="h-[44px] shrink-0" data-tauri-drag-region />
      <div className="flex min-h-0 flex-1 items-stretch gap-10 px-12 pb-8">
        {/* left: the robot reacts to every step */}
        <div className="relative flex w-[300px] shrink-0 flex-col items-center justify-center">
          <div className="relative">
            <Halo state={step.robot} size={170} />
            <RobotHead
              size={170}
              shape={s.shape}
              state={step.robot}
              color={theme.color}
              trimColor={theme.trimColor}
              screenColor={theme.screen[s.uiLang]}
            />
          </div>
          <div className="mt-10 flex gap-1.5">
            {STEPS.map((st, i) => (
              <motion.span
                key={st.id}
                animate={{ width: i === index ? 22 : 6, opacity: i <= index ? 1 : 0.35 }}
                className="h-1.5 rounded-full bg-[var(--accent)]"
              />
            ))}
          </div>
        </div>

        {/* right: the step content slides */}
        <div className="relative flex min-w-0 flex-1 flex-col">
          <div className="relative min-h-0 flex-1">
            <AnimatePresence mode="wait" custom={dir} initial={false}>
              <motion.div
                key={step.id}
                custom={dir}
                initial={{ opacity: 0, x: 40 * dir, filter: "blur(6px)" }}
                animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, x: -40 * dir, filter: "blur(6px)" }}
                transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
                className="absolute inset-0 flex flex-col justify-center overflow-y-auto"
              >
                <p className="mb-1 text-[13px] font-medium text-[var(--accent)]" lang="ta">
                  {step.ta}
                </p>
                <h1 className="mb-5 text-[30px] font-semibold leading-tight tracking-tight">{step.title}</h1>
                <StepBody id={step.id} />
              </motion.div>
            </AnimatePresence>
          </div>
          <div className="flex items-center justify-between pt-4">
            <Button variant="ghost" quiet onClick={() => go(-1)} disabled={index === 0}>
              <ArrowLeft size={14} /> Back
            </Button>
            <Button variant="primary" size="lg" quiet onClick={() => go(1)}>
              {index === STEPS.length - 1 ? (
                <>
                  Start using Sasu <Rocket size={15} />
                </>
              ) : (
                <>
                  Continue <ArrowRight size={15} />
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StepBody({ id }: { id: string }) {
  switch (id) {
    case "welcome":
      return <Welcome />;
    case "permissions":
      return <PermissionsStep />;
    case "brain":
      return <BrainStep />;
    case "voice":
      return <VoiceStep />;
    case "security":
      return <SecurityStep />;
    case "robot":
      return <RobotStep />;
    default:
      return <DoneStep />;
  }
}

function Welcome() {
  const lang = useSelector(settingsStore, (s) => s.uiLang);
  return (
    <div className="flex flex-col gap-5">
      <p className="max-w-md text-[15px] leading-relaxed text-[var(--muted)]">
        I live on your desktop. Say <b className="text-[var(--text)]">“Hey Sasu”</b> and tell me what to do — in English, தமிழ், or a mix of both. I'll open
        apps, find files, change settings and more.
      </p>
      <div className="flex items-center gap-3">
        <span className="text-[13px] text-[var(--muted)]">I'll speak</span>
        <Segmented
          value={lang}
          onChange={(uiLang) => updateSettings({ uiLang })}
          options={[
            { value: "en", label: "English" },
            { value: "ta", label: "தமிழ்" },
          ]}
        />
      </div>
    </div>
  );
}

const PERMS: { kind: PermissionKind; Icon: typeof Mic; title: string; why: string }[] = [
  { kind: "microphone", Icon: Mic, title: "Microphone", why: "To hear “Hey Sasu” and your commands. Audio never leaves this Mac." },
  { kind: "accessibility", Icon: Keyboard, title: "Accessibility", why: "To click buttons, fill fields and arrange windows for you, one step at a time and only after you say yes. Never password fields." },
  { kind: "screen_recording", Icon: MonitorUp, title: "Screen Recording", why: "To read what's on screen when you ask about it." },
  { kind: "automation", Icon: AppWindow, title: "Automation", why: "To control apps like Safari, Music and Calendar. macOS asks per app." },
];

function PermissionsStep() {
  const [perms, setPerms] = useState<Permissions | null>(null);
  useEffect(() => {
    const load = () => void permissionsStatus().then(setPerms);
    load();
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex max-w-xl flex-col gap-2.5">
      {PERMS.map(({ kind, Icon, title, why }) => {
        const st = perms?.[kind] ?? "unknown";
        const granted = st === "granted";
        return (
          <Card key={kind} className="flex items-center gap-3.5 px-4 py-3">
            <span className={cx("flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px]", granted ? "text-[var(--ok)]" : "text-[var(--accent)]")} style={{ background: "var(--sunken)" }}>
              <Icon size={18} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13.5px] font-medium">{title}</p>
              <p className="text-[12px] text-[var(--muted)]">{why}</p>
            </div>
            <AnimatePresence mode="wait" initial={false}>
              {granted ? (
                <motion.span key="ok" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 500, damping: 20 }}>
                  <Badge color="var(--ok)">
                    <Check size={11} strokeWidth={3} /> Allowed
                  </Badge>
                </motion.span>
              ) : (
                <Button key="grant" size="sm" disabled={!inTauri} onClick={() => void requestPermission(kind)}>
                  {kind === "automation" ? "Open Settings" : "Allow…"}
                </Button>
              )}
            </AnimatePresence>
          </Card>
        );
      })}
      {!inTauri && <p className="text-[12px] text-[var(--muted)]">Permissions can only be granted in the desktop app.</p>}
    </div>
  );
}

function VoiceStep() {
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <p className="text-[15px] leading-relaxed text-[var(--muted)]">
        Sasu only obeys <b className="text-[var(--text)]">your</b> voice. Turn voice on (a one-time download that stays on this Mac), then read five short
        phrases so Sasu knows it's you. Anyone else is treated as a guest.
      </p>
      <VoiceSettings compact />
    </div>
  );
}

function BrainStep() {
  return (
    <div className="flex max-w-xl flex-col gap-3">
      <p className="text-[15px] leading-relaxed text-[var(--muted)]">
        Sasu needs an AI brain to understand you. Google Gemini is free — get a key in a minute and paste it here.
      </p>
      <BrainSettings />
    </div>
  );
}

function SecurityStep() {
  const [result, setResult] = useState<boolean | null>(null);
  return (
    <div className="flex max-w-xl flex-col gap-3">
      <p className="text-[15px] leading-relaxed text-[var(--muted)]">Before anything risky — deleting files, changing system settings — Sasu asks for Touch ID. Voice alone is never enough.</p>
      <Card className="flex items-center gap-3.5 px-4 py-3.5">
        <motion.span
          animate={result === true ? { scale: [1, 1.2, 1] } : {}}
          className="flex h-10 w-10 items-center justify-center rounded-full"
          style={{ background: "var(--sunken)", color: result ? "var(--ok)" : "var(--danger)" }}
        >
          <FingerprintPattern size={22} />
        </motion.span>
        <div className="flex-1">
          <p className="text-[13.5px] font-medium">Try Touch ID</p>
          <p className="text-[12px] text-[var(--muted)]">Falls back to your login password on Macs without Touch ID.</p>
        </div>
        {result !== null && <Badge color={result ? "var(--ok)" : "var(--danger)"}>{result ? "Works!" : "Not passed"}</Badge>}
        <Button size="sm" disabled={!inTauri} onClick={() => void testTouchId().then((ok) => (setResult(ok), play(ok ? "success" : "error", { force: true })))}>
          Test
        </Button>
      </Card>
      <ul className="mt-1 flex flex-col gap-1.5 text-[12.5px] text-[var(--muted)]">
        <li>• Sasu goes deaf the moment your Mac locks.</li>
        <li>
          • <Kbd>⌘</Kbd> <Kbd>⌥</Kbd> <Kbd>Esc</Kbd> stops everything instantly.
        </li>
        <li>• Every action is written to a tamper-evident log you can check anytime.</li>
      </ul>
    </div>
  );
}

function RobotStep() {
  const s = useSelector(settingsStore);
  const theme = themes[s.theme];
  return (
    <div className="flex max-w-xl flex-col gap-5">
      <div className="grid grid-cols-4 gap-2.5">
        {(Object.keys(themes) as ThemeName[]).map((name) => (
          <Pick key={name} active={s.theme === name} label={themes[name].label} onClick={() => updateSettings({ theme: name })}>
            <span className="h-7 w-7 rounded-full shadow-inner" style={{ background: themes[name].color, boxShadow: `inset 0 0 0 3px ${themes[name].trimColor}` }} />
          </Pick>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-2.5">
        {robotHeadShapes.map((shape) => (
          <Pick key={shape} active={s.shape === shape} label={shape} onClick={() => updateSettings({ shape })}>
            <RobotHead size={44} shape={shape} state="idle" color={theme.color} trimColor={theme.trimColor} screenColor={theme.screen.en} interactive={false} antenna={false} floorShadow={false} />
          </Pick>
        ))}
      </div>
    </div>
  );
}

function Pick({ active, label, onClick, children }: { active: boolean; label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <motion.button
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.96 }}
      onClick={() => {
        play("click");
        onClick();
      }}
      className={cx(
        "flex flex-col items-center gap-2 rounded-[12px] bg-[var(--surface)] py-3 text-[12px] capitalize transition-shadow",
        active ? "shadow-[0_0_0_2px_var(--accent),var(--shadow)]" : "shadow-[var(--shadow-sm)]",
      )}
    >
      {children}
      <span className={active ? "font-semibold" : "text-[var(--muted)]"}>{label}</span>
    </motion.button>
  );
}

function DoneStep() {
  const [autostart, setAutostart] = useState(false);
  useEffect(() => {
    if (inTauri) void autostartEnabled().then(setAutostart);
  }, []);
  return (
    <div className="flex max-w-lg flex-col gap-4">
      <motion.div initial={{ rotate: -20, scale: 0 }} animate={{ rotate: 0, scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 12 }}>
        <PartyPopper size={34} className="text-[var(--accent)]" />
      </motion.div>
      <p className="text-[15px] leading-relaxed text-[var(--muted)]">
        Say <b className="text-[var(--text)]">“Hey Sasu”</b>, click the robot, or press <Kbd>⌥</Kbd> <Kbd>Space</Kbd>. Double-click the robot to come back here.
      </p>
      <Card className="flex items-center justify-between px-4 py-3">
        <div>
          <p className="text-[13.5px] font-medium">Open Sasu at login</p>
          <p className="text-[12px] text-[var(--muted)]">So I'm always ready when you are.</p>
        </div>
        <Switch
          label="Open at login"
          checked={autostart}
          onChange={(on) => {
            setAutostart(on);
            if (inTauri) void (on ? enableAutostart() : disableAutostart());
          }}
        />
      </Card>
    </div>
  );
}
