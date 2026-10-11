// Thin wrappers over Tauri so the UI also runs in a plain browser (`pnpm dev:ui`).
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";

export const inTauri = isTauri();

export const windowLabel: string | null = inTauri ? getCurrentWindow().label : null;

export function showPanel() {
  if (inTauri) void invoke("show_panel");
  else window.open("#/panel", "sasu-panel");
}

export function startDragging() {
  if (inTauri) void getCurrentWindow().startDragging();
}

type ShellEvent = "hotkey-talk" | "hotkey-stop" | "hotkey-undo" | "request-enable" | "disabled-changed" | "session-locked";

/** Events from the Rust shell. Returns an unsubscribe. */
export function onShell<T = void>(name: ShellEvent, fn: (payload: T) => void): () => void {
  if (!inTauri) return () => {};
  const pending = listen<T>(name, (e) => fn(e.payload));
  return () => void pending.then((unlisten) => unlisten());
}

export const onHotkey = (name: "hotkey-talk" | "hotkey-stop" | "hotkey-undo", fn: () => void) => onShell(name, fn);

// ── permissions ───────────────────────────────────────────────────────────────
export type PermissionKind = "microphone" | "accessibility" | "screen_recording" | "automation";
export type PermissionStatus = "granted" | "denied" | "not_determined" | "unknown";
export type Permissions = Record<PermissionKind, PermissionStatus>;

export async function permissionsStatus(): Promise<Permissions> {
  if (!inTauri) return { microphone: "unknown", accessibility: "unknown", screen_recording: "unknown", automation: "unknown" };
  return invoke<Permissions>("permissions_status");
}

export async function requestPermission(kind: PermissionKind) {
  if (inTauri) await invoke("request_permission", { kind });
}

// ── security ──────────────────────────────────────────────────────────────────
export type ShellSecurity = { locks: string[]; touch_id: boolean };

export async function shellSecurity(): Promise<ShellSecurity> {
  if (!inTauri) return { locks: [], touch_id: false };
  return invoke<ShellSecurity>("shell_security");
}

/** Touch ID for a pending dangerous action; the verdict goes to the core via the shell. */
export async function authorizeAction(id: string, reason: string): Promise<boolean> {
  if (!inTauri) return false;
  return invoke<boolean>("authorize_action", { id, reason });
}

export async function testTouchId(): Promise<boolean> {
  if (!inTauri) return false;
  return invoke<boolean>("test_touch_id");
}

/** Disabling is instant; enabling again asks for Touch ID. Resolves false if refused. */
export async function setDisabled(disabled: boolean): Promise<boolean> {
  if (!inTauri) return false;
  return invoke<boolean>("set_disabled", { disabled });
}

// ── feel ──────────────────────────────────────────────────────────────────────
export function haptic(kind: "generic" | "alignment" | "level" = "generic") {
  if (inTauri) void invoke("haptic", { kind });
}

/** The robot glides next to the app it's working in, then home. */
export function flyToApp(name: string) {
  if (inTauri) void invoke("fly_to_app", { name });
}

export function flyHome() {
  if (inTauri) void invoke("fly_home");
}

// ── AI keys (stored by the shell; the UI never reads them back) ───────────────
export type Provider = "gemini" | "groq" | "anthropic" | "ollama";

export async function apiKeys(): Promise<string[]> {
  if (!inTauri) return [];
  return invoke<string[]>("api_keys");
}

export async function setApiKey(provider: Provider, key: string): Promise<void> {
  if (!inTauri) throw new Error("Keys can only be saved in the desktop app.");
  await invoke("set_api_key", { provider, key });
}

export async function removeApiKey(provider: Provider): Promise<void> {
  if (inTauri) await invoke("remove_api_key", { provider });
}

export type HelpPage = "gemini-key" | "groq-key" | "anthropic-key" | "ollama";

export function openHelp(page: HelpPage) {
  if (inTauri) void invoke("open_help", { page });
  else window.open({ "gemini-key": "https://aistudio.google.com/apikey", "groq-key": "https://console.groq.com/keys", "anthropic-key": "https://console.anthropic.com/settings/keys", ollama: "https://ollama.com/download" }[page], "_blank", "noopener");
}
