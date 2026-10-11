import { useSelector } from "@tanstack/react-store";
import { useState } from "react";
import { settingsStore, updateSettings } from "../robot/settings";
import { Group, Row } from "../ui/Card";
import { Switch } from "../ui/Switch";

function TextField({ value, placeholder, onSave }: { value: string; placeholder: string; onSave: (v: string) => void }) {
  const [draft, setDraft] = useState(value);
  return (
    <input
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => draft !== value && onSave(draft.trim())}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      placeholder={placeholder}
      className="h-8 w-[200px] rounded-[8px] bg-[var(--sunken)] px-3 text-[12.5px] outline-none placeholder:text-[var(--faint)] focus:shadow-[0_0_0_3px_var(--accent-glow)]"
    />
  );
}

/** Settings → Personal: the robot's name, home city, nudges and festivals. */
export function PersonalSettings() {
  const s = useSelector(settingsStore);
  return (
    <Group title="Personal" description="Make Sasu yours.">
      <Row label="Robot name" hint="Extra names it answers to, comma separated. “Hey Sasu” always works too.">
        <TextField value={s.robotName} placeholder="Chitti, சிட்டி" onSave={(robotName) => updateSettings({ robotName })} />
      </Row>
      <Row label="Home city" hint="For the weather in “Good morning” briefings. Uses free Open-Meteo.">
        <TextField value={s.city} placeholder="Chennai" onSave={(city) => updateSettings({ city })} />
      </Row>
      <Row label="Heads-ups" hint="Speaks up when the battery is low or a meeting starts in 5 minutes.">
        <Switch label="Heads-ups" checked={s.nudges} onChange={(nudges) => updateSettings({ nudges })} />
      </Row>
      <Row label="Clipboard memory" hint="Remembers your last 50 copies (encrypted, skips codes and passwords). Ask “what did I copy?”">
        <Switch label="Clipboard memory" checked={s.clipboardMemory} onChange={(clipboardMemory) => updateSettings({ clipboardMemory })} />
      </Row>
      <Row label="Festival mode" hint="Pongal, Tamil New Year, Deepavali, Christmas: a festive hello and outfit.">
        <Switch label="Festival mode" checked={s.festivals} onChange={(festivals) => updateSettings({ festivals })} />
      </Row>
    </Group>
  );
}
