import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useSelector } from "@tanstack/react-store";
import { Check, Play, Volume2, VolumeX } from "lucide-react";
import { motion } from "motion/react";
import { RobotHead, robotHeadShapes } from "robot-heads";
import { useState } from "react";
import { MODE_SHAPE, SIZES, settingsStore, updateSettings, type Mode } from "../robot/settings";
import { themes, type ThemeName } from "../robot/themes";
import { CUES, type Cue } from "../sound/cues";
import { setVolume } from "@sasu/brand";
import { play } from "../sound/player";
import { Button } from "../ui/Button";
import { Group, Row } from "../ui/Card";
import { cx } from "../ui/cx";
import { Segmented } from "../ui/Segmented";
import { Slider } from "../ui/Slider";
import { Switch } from "../ui/Switch";
import { BrainSettings } from "../settings/BrainSettings";
import { PersonalSettings } from "../settings/PersonalSettings";
import { VoiceSettings } from "../settings/VoiceSettings";

export const Route = createFileRoute("/panel/settings")({ component: SettingsPage });

const CUE_LABEL: Record<Cue, string> = {
  wake: "Wake",
  listen: "Listen",
  think: "Think",
  tool: "Tool",
  confirm: "Confirm",
  success: "Success",
  error: "Error",
  sleep: "Sleep",
  click: "Click",
  toggle: "Toggle",
};

function SettingsPage() {
  const s = useSelector(settingsStore);
  const theme = themes[s.theme];
  const navigate = useNavigate();

  return (
    <div className="flex flex-col gap-7">
      <h1 className="text-[22px] font-semibold tracking-tight">Settings</h1>

      <BrainSettings />
      <VoiceSettings />
      <PersonalSettings />

      <Group title="Appearance" description="How Sasu looks on your desktop.">
        <div className="py-4">
          <p className="mb-2.5 text-[12px] text-[var(--muted)]">Theme</p>
          <div className="grid grid-cols-4 gap-2.5">
            {(Object.keys(themes) as ThemeName[]).map((name) => (
              <Choice key={name} active={s.theme === name} onClick={() => updateSettings({ theme: name })} label={themes[name].label}>
                <RobotHead
                  size={52}
                  shape={s.shape}
                  state={s.theme === name ? "happy" : "idle"}
                  color={themes[name].color}
                  trimColor={themes[name].trimColor}
                  screenColor={themes[name].screen.en}
                  interactive={false}
                  antenna={false}
                />
              </Choice>
            ))}
          </div>
        </div>
        <div className="py-4">
          <p className="mb-2.5 text-[12px] text-[var(--muted)]">Shape {s.modeShapes && "(following mode)"}</p>
          <div className="grid grid-cols-4 gap-2.5">
            {robotHeadShapes.map((shape) => (
              <Choice key={shape} active={s.shape === shape} disabled={s.modeShapes} onClick={() => updateSettings({ shape })} label={shape}>
                <RobotHead
                  size={52}
                  shape={shape}
                  state="idle"
                  color={theme.color}
                  trimColor={theme.trimColor}
                  screenColor={theme.screen.en}
                  interactive={false}
                  antenna={false}
                />
              </Choice>
            ))}
          </div>
        </div>
        <Row label="Size">
          <Segmented
            value={String(s.size)}
            onChange={(v) => updateSettings({ size: Number(v) })}
            options={Object.entries(SIZES).map(([k, v]) => ({ value: String(v), label: k }))}
          />
        </Row>
        <Row label="Mode" hint="Normal, offline (local AI), safe (read-only) or full access.">
          <Segmented value={s.mode} onChange={(mode) => updateSettings({ mode })} options={(Object.keys(MODE_SHAPE) as Mode[]).map((m) => ({ value: m, label: m }))} />
        </Row>
        <Row label="Shape follows mode" hint="Rectangle normal · circle offline · square safe · hexagon full access">
          <Switch label="Shape follows mode" checked={s.modeShapes} onChange={(modeShapes) => updateSettings({ modeShapes })} />
        </Row>
      </Group>

      <Group title="Sound" description="Little chimes so you know what Sasu is doing without looking.">
        <Row label="Sound effects">
          <Switch label="Sound effects" checked={s.sound} onChange={(sound) => updateSettings({ sound })} />
        </Row>
        <Row label="Volume">
          <div className="flex w-56 items-center gap-2.5 text-[var(--muted)]">
            <VolumeX size={14} />
            <VolumeSlider />
            <Volume2 size={14} />
          </div>
        </Row>
        <Row label="Sound pack" hint="Kovil: temple bells in raga Mayamalavagowla · Toon: slide whistle, kazoo, sad trombone.">
          <Segmented
            value={s.soundPack}
            onChange={(soundPack) => {
              updateSettings({ soundPack });
              setTimeout(() => play("success", { force: true }), 30);
            }}
            options={[
              { value: "soft", label: "Soft" },
              { value: "robo", label: "Robo" },
              { value: "kovil", label: "Kovil" },
              { value: "toon", label: "Toon 🤪" },
            ]}
          />
        </Row>
        <div className="py-3.5">
          <p className="mb-2 text-[12px] text-[var(--muted)]">Preview</p>
          <div className="grid grid-cols-5 gap-1.5">
            {CUES.map((cue) => (
              <Button key={cue} size="sm" quiet onClick={() => play(cue, { force: true })} className="justify-start">
                <Play size={10} fill="currentColor" className="text-[var(--accent)]" />
                {CUE_LABEL[cue]}
              </Button>
            ))}
          </div>
        </div>
      </Group>

      <Group title="Behaviour">
        <Row label="Do not disturb" hint="Robot freezes and stays silent.">
          <Switch label="Do not disturb" checked={s.dnd} onChange={(dnd) => updateSettings({ dnd })} />
        </Row>
        <Row label="Dance to music" hint="When Spotify or Music plays, Sasu dances and shows the song.">
          <Switch label="Dance to music" checked={s.dance} onChange={(dance) => updateSettings({ dance })} />
        </Row>
        <Row label="Fun replies" hint="A little Tamil masala in replies: “Semma!”, “Done, boss!”">
          <Switch label="Fun replies" checked={s.funReplies} onChange={(funReplies) => updateSettings({ funReplies })} />
        </Row>
        <Row label="Break buddy" hint="A friendly stretch and water reminder.">
          <Segmented
            size="sm"
            value={String(s.breakMinutes)}
            onChange={(v) => updateSettings({ breakMinutes: Number(v) })}
            options={[
              { value: "0", label: "Off" },
              { value: "30", label: "30 min" },
              { value: "60", label: "1 hour" },
            ]}
          />
        </Row>
        <Row label="Trackpad haptics" hint="A tap you can feel when Sasu needs you or finishes.">
          <Switch label="Trackpad haptics" checked={s.haptics} onChange={(haptics) => updateSettings({ haptics })} />
        </Row>
        <Row label="Robot flies to the app" hint="Sasu glides next to the window it's working in, then comes home.">
          <Switch label="Robot flies to the app" checked={s.flyToApps} onChange={(flyToApps) => updateSettings({ flyToApps })} />
        </Row>
        <Row label="Battery saver" hint="Slower animations, less CPU.">
          <Switch label="Battery saver" checked={s.batterySaver} onChange={(batterySaver) => updateSettings({ batterySaver })} />
        </Row>
        <Row label="Language" hint="Sasu always replies in the language you speak.">
          <Segmented
            value={s.uiLang}
            onChange={(uiLang) => updateSettings({ uiLang })}
            options={[
              { value: "en", label: "English" },
              { value: "ta", label: "தமிழ்" },
            ]}
          />
        </Row>
        <Row label="Setup assistant" hint="Permissions, voice, security and robot.">
          <Button size="sm" onClick={() => void navigate({ to: "/onboarding" })}>
            Run again…
          </Button>
        </Row>
      </Group>
      <p className="pb-2 text-center text-[11.5px] text-[var(--muted)]">
        Sasu 0.4.0 · Developed by <span className="font-semibold text-[var(--text)]">Sarangan Raviraj</span> · MIT License
      </p>
    </div>
  );
}

/** Volume moves the sound live but only saves (and syncs windows) on release. */
function VolumeSlider() {
  const saved = useSelector(settingsStore, (s) => s.volume);
  const [live, setLive] = useState<number | null>(null);
  return (
    <Slider
      label="Volume"
      value={live ?? saved}
      onChange={(v) => {
        setLive(v);
        setVolume(v);
      }}
      onCommit={(v) => {
        setLive(null);
        updateSettings({ volume: v });
        play("toggle", { force: true });
      }}
    />
  );
}

function Choice({
  active,
  disabled,
  onClick,
  label,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <motion.button
      whileHover={disabled ? undefined : { y: -2 }}
      whileTap={disabled ? undefined : { scale: 0.97 }}
      disabled={disabled}
      onClick={() => {
        play("click");
        onClick();
      }}
      className={cx(
        "relative flex flex-col items-center gap-1.5 rounded-[12px] bg-[var(--surface-2)] pb-2.5 pt-4 text-[12px] capitalize transition-shadow disabled:opacity-40",
        active ? "shadow-[0_0_0_2px_var(--accent)]" : "shadow-[0_0_0_0.5px_var(--hairline-strong)]",
      )}
    >
      {children}
      <span className={active ? "font-semibold" : "text-[var(--muted)]"}>{label}</span>
      {active && (
        <motion.span layoutId={`choice-${label}`} className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--accent)] text-white">
          <Check size={10} strokeWidth={3.5} />
        </motion.span>
      )}
    </motion.button>
  );
}
