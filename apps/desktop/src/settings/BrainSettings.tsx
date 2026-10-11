import { useSelector } from "@tanstack/react-store";
import { ArrowUpRight, Brain, Check, KeyRound, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { agentStore } from "../agent/store";
import { settingsStore, updateSettings } from "../robot/settings";
import { play } from "../sound/player";
import { apiKeys, inTauri, openHelp, removeApiKey, setApiKey, type HelpPage, type Provider } from "../tauri";
import { Button } from "../ui/Button";
import { Badge, Group, Row } from "../ui/Card";
import { Segmented } from "../ui/Segmented";
import { Switch } from "../ui/Switch";

const PROVIDERS: Record<Provider, { label: string; free: boolean; help: HelpPage; note: string; needsKey: boolean }> = {
  gemini: {
    label: "Gemini",
    free: true,
    help: "gemini-key",
    needsKey: true,
    note: "Free key from Google AI Studio. Great at Tamil. On the free tier Google may use prompts to improve its products.",
  },
  groq: { label: "Groq", free: true, help: "groq-key", needsKey: true, note: "Free key, very fast. Good English, okay Tamil." },
  anthropic: { label: "Claude", free: false, help: "anthropic-key", needsKey: true, note: "Paid, most careful with tools. Prompts aren't used for training." },
  ollama: { label: "Ollama", free: true, help: "ollama", needsKey: false, note: "Runs fully on this Mac — nothing leaves it. Needs ~5 GB of disk and the Ollama app." },
};

/** Settings → AI brain: which model thinks for Sasu, and its key (kept in the Keychain). */
export function BrainSettings() {
  const s = useSelector(settingsStore);
  const brain = useSelector(agentStore, (st) => st.brain);
  const [keys, setKeys] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const p = PROVIDERS[s.provider];
  const hasKey = keys.includes(s.provider) || (brain?.keys.includes(s.provider) ?? false);

  useEffect(() => {
    void apiKeys().then(setKeys);
  }, [brain]);

  const save = async () => {
    setError(null);
    try {
      await setApiKey(s.provider, draft);
      setDraft("");
      setSaved(true);
      play("success", { force: true });
      setTimeout(() => setSaved(false), 2500);
      setKeys(await apiKeys());
    } catch (e) {
      setError(String(e));
      play("error", { force: true });
    }
  };

  return (
    <div id="brain">
      <Group title="AI brain" description="The model that understands you and decides what to do. Keys go straight to your Mac's Keychain.">
        <Row
          label={
            <span className="flex items-center gap-2">
              <Brain size={14} className="text-[var(--accent)]" /> Status
            </span>
          }
          hint={brain ? `${PROVIDERS[brain.provider as Provider]?.label ?? brain.provider} · ${brain.model}` : "Connecting to the core…"}
        >
          <Badge color={brain?.ready ? "var(--ok)" : "var(--warn)"}>{brain?.ready ? "Ready" : "Needs a key"}</Badge>
        </Row>
        <Row label="Provider" hint={p.note}>
          <Segmented
            size="sm"
            value={s.provider}
            onChange={(provider) => updateSettings({ provider })}
            options={(Object.keys(PROVIDERS) as Provider[]).map((id) => ({
              value: id,
              label: (
                <>
                  {PROVIDERS[id].label}
                  {PROVIDERS[id].free && <span className="ml-1 text-[9.5px] font-bold text-[var(--ok)]">FREE</span>}
                </>
              ),
            }))}
          />
        </Row>
        {p.needsKey ? (
          <div className="flex flex-col gap-2 py-3.5">
            <div className="flex items-center gap-2">
              <div className="flex h-8 flex-1 items-center gap-2 rounded-[8px] bg-[var(--sunken)] px-3 shadow-[inset_0_0_0_0.5px_var(--hairline-strong)] focus-within:shadow-[0_0_0_3px_var(--accent-glow)]">
                <KeyRound size={13} className="text-[var(--muted)]" />
                <input
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && draft && void save()}
                  placeholder={hasKey ? "•••••••••••• saved in Keychain — paste to replace" : `Paste your ${p.label} API key`}
                  className="h-full flex-1 bg-transparent font-mono text-[12px] outline-none placeholder:font-sans placeholder:text-[var(--faint)]"
                />
              </div>
              <Button variant="primary" size="sm" disabled={!draft || !inTauri} onClick={() => void save()}>
                {saved ? <Check size={13} /> : null} {saved ? "Saved" : "Save"}
              </Button>
              {hasKey && (
                <Button size="sm" aria-label="Remove key" onClick={() => void removeApiKey(s.provider).then(() => apiKeys().then(setKeys))}>
                  <Trash2 size={13} />
                </Button>
              )}
            </div>
            <div className="flex items-center justify-between text-[11.5px]">
              <button onClick={() => openHelp(p.help)} className="flex items-center gap-1 font-medium text-[var(--accent)] hover:underline">
                Get a {p.free ? "free " : ""}{p.label} key <ArrowUpRight size={11} />
              </button>
              {error && <span className="text-[var(--danger)]">{error}</span>}
              {!inTauri && <span className="text-[var(--muted)]">Keys can only be saved in the desktop app.</span>}
            </div>
          </div>
        ) : (
          <Row label="Ollama" hint="Install Ollama, then run: ollama pull qwen3:8b">
            <Button size="sm" onClick={() => openHelp("ollama")}>
              Get Ollama <ArrowUpRight size={12} />
            </Button>
          </Row>
        )}
        <Row label="Speak replies" hint="Uses the Mac's own voices: Vani for Tamil, Rishi for English. No download.">
          <Switch label="Speak replies" checked={s.tts} onChange={(tts) => updateSettings({ tts })} />
        </Row>
        <Row label="Unknown voices" hint="Guest: someone else may only check the time or play music. Ignore: nothing at all.">
          <Segmented
            size="sm"
            value={s.guestMode}
            onChange={(guestMode) => updateSettings({ guestMode })}
            options={[
              { value: "guest", label: "Guest" },
              { value: "reject", label: "Ignore" },
            ]}
          />
        </Row>
      </Group>
    </div>
  );
}
