// Finds sasu-core (via the Tauri shell, or VITE_CORE_URL in a plain browser) and keeps a
// WebSocket open to it with backoff. Every window has its own connection.
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { CoreEvent, type UiCommand } from "./protocol";
import { coreSettings, settingsStore } from "../robot/settings";
import { applyEvent, setConnection } from "./store";

type Endpoint = { port: number; token: string };

let socket: WebSocket | null = null;
let started = false;
let retries = 0;
let current: { http: string; token: string } | null = null;

async function endpointUrl(): Promise<string> {
  if (!isTauri()) {
    const base = import.meta.env.VITE_CORE_URL ?? "ws://127.0.0.1:8765";
    const token = import.meta.env.VITE_CORE_TOKEN ?? "dev";
    current = { http: base.replace(/^ws/, "http"), token };
    return `${base}/ws?t=${encodeURIComponent(token)}`;
  }
  for (;;) {
    const ep = await invoke<Endpoint | null>("core_endpoint");
    if (ep) {
      current = { http: `http://127.0.0.1:${ep.port}`, token: ep.token };
      return `ws://127.0.0.1:${ep.port}/ws?t=${encodeURIComponent(ep.token)}`;
    }
    let wake = () => {};
    const unlisten = await listen("core-ready", () => wake());
    await new Promise<void>((resolve) => {
      wake = resolve;
      setTimeout(resolve, 1000);
    });
    unlisten();
  }
}

async function connect(): Promise<void> {
  setConnection("connecting");
  const url = await endpointUrl();
  const ws = new WebSocket(url);
  socket = ws;

  ws.onopen = () => {
    retries = 0;
    setConnection("open");
    ws.send(JSON.stringify({ type: "set_settings", settings: coreSettings(settingsStore.get()) }));
  };
  ws.onmessage = (msg) => {
    const parsed = CoreEvent.safeParse(JSON.parse(String(msg.data)));
    if (parsed.success) applyEvent(parsed.data);
    else console.warn("sasu: unknown event", msg.data, parsed.error.issues);
  };
  ws.onclose = () => {
    if (socket !== ws) return;
    socket = null;
    setConnection("closed");
    const wait = Math.min(500 * 2 ** retries++, 8000);
    setTimeout(() => void connect(), wait);
  };
}

export function startAgent() {
  if (started) return;
  started = true;
  void connect();
}

export function send(cmd: UiCommand): boolean {
  if (socket?.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(cmd));
  return true;
}

/** Authenticated GET against the core's REST API (for TanStack Query). */
export async function apiGet<T>(path: string): Promise<T> {
  if (!current) throw new Error("core not connected");
  const res = await fetch(current.http + path, { headers: { Authorization: `Bearer ${current.token}` } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

/** Authenticated request to the core (photos, memory). */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!current) throw new Error("core not connected");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${current.token}`);
  return fetch(current.http + path, { ...init, headers });
}

// Keep the core in sync when brain/voice settings change in any window.
let lastSent = "";
settingsStore.subscribe((s) => {
  const payload = JSON.stringify(coreSettings(s));
  if (payload !== lastSent && send({ type: "set_settings", settings: coreSettings(s) })) lastSent = payload;
});
