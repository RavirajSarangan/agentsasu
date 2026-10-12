// Mirror of core/sasu_core/protocol.py (the source of truth).
// protocol.test.ts fails if this drifts from packages/protocol/schema.json.
import { z } from "zod";

export const Lang = z.enum(["en", "ta"]);
export const Risk = z.enum(["safe", "confirm", "dangerous"]);
export const LockReason = z.enum(["screen", "disabled", "user", "panic", "canary", "away", "intruder"]);
export type Lang = z.infer<typeof Lang>;
export type LockReason = z.infer<typeof LockReason>;
export type Risk = z.infer<typeof Risk>;

export const CoreEvent = z.discriminatedUnion("type", [
  z.object({ type: z.literal("ready"), version: z.string(), demo: z.boolean() }),
  z.object({ type: z.literal("wake"), source: z.enum(["wakeword", "hotkey", "click", "demo"]) }),
  z.object({ type: z.literal("listening") }),
  z.object({ type: z.literal("partial_transcript"), text: z.string() }),
  z.object({ type: z.literal("transcript"), text: z.string(), lang: Lang }),
  z.object({ type: z.literal("thinking") }),
  z.object({
    type: z.literal("tool_start"),
    id: z.string(),
    name: z.string(),
    args: z.record(z.string(), z.unknown()).default({}),
    risk: Risk.default("safe"),
  }),
  z.object({ type: z.literal("tool_end"), id: z.string(), ok: z.boolean(), summary: z.string().default("") }),
  z.object({ type: z.literal("confirm_request"), id: z.string(), prompt: z.string(), lang: Lang, risk: Risk }),
  z.object({ type: z.literal("say_start"), text: z.string(), lang: Lang, big: z.boolean().default(false) }),
  z.object({ type: z.literal("say_chunk"), text: z.string() }),
  z.object({ type: z.literal("say_end") }),
  z.object({ type: z.literal("turn_done"), ok: z.boolean() }),
  z.object({ type: z.literal("error"), code: z.string(), message: z.string() }),
  z.object({ type: z.literal("sleep") }),
  z.object({ type: z.literal("speaker_rejected"), score: z.number() }),
  z.object({ type: z.literal("locked"), reasons: z.array(LockReason) }),
  z.object({ type: z.literal("unlocked") }),
  z.object({ type: z.literal("auth_required"), id: z.string(), reason: z.string(), risk: Risk }),
  z.object({ type: z.literal("plan_preview"), id: z.string(), steps: z.array(z.string()) }),
  z.object({ type: z.literal("focus_app"), app: z.string() }),
  z.object({ type: z.literal("undo_available"), turn_id: z.string(), actions: z.array(z.string()) }),
  z.object({ type: z.literal("undone"), turn_id: z.string(), ok: z.boolean(), summary: z.string() }),
  z.object({ type: z.literal("privacy"), provider: z.string(), chars: z.number(), images: z.number().default(0), audio: z.number().default(0) }),
  z.object({ type: z.literal("level"), rms: z.number() }),
  z.object({ type: z.literal("enroll_progress"), n: z.number(), total: z.number(), phrase: z.string(), done: z.boolean().default(false) }),
  z.object({
    type: z.literal("voice_status"),
    state: z.enum(["missing", "downloading", "loading", "listening", "error"]),
    progress: z.number().default(0),
    detail: z.string().default(""),
    size_mb: z.number().default(0),
    enrolled: z.boolean().default(false),
    profiles: z.array(z.string()).default([]),
  }),
  z.object({ type: z.literal("focus"), remaining: z.number(), total: z.number() }),
  z.object({ type: z.literal("translate_mode"), on: z.boolean() }),
  z.object({ type: z.literal("snap_request"), id: z.string(), reason: z.string() }),
  z.object({ type: z.literal("caption"), text: z.string(), lang: Lang }),
  z.object({ type: z.literal("meeting"), on: z.boolean(), seconds: z.number().default(0), lines: z.number().default(0) }),
  z.object({ type: z.literal("alarm"), kind: z.enum(["canary", "leak", "panic", "siren", "sos"]), detail: z.string() }),
  z.object({ type: z.literal("intruder"), text: z.string(), score: z.number(), count: z.number() }),
  z.object({ type: z.literal("fun"), kind: z.enum(["dance", "joke", "night", "briefing", "festival"]), on: z.boolean().default(true), detail: z.string().default("") }),
  z.object({ type: z.literal("care"), kind: z.enum(["due", "taken", "missed", "help"]), who: z.string(), what: z.string().default(""), time: z.string().default("") }),
  z.object({ type: z.literal("watch"), id: z.string(), kind: z.enum(["download", "battery", "page", "file", "command"]), label: z.string(), state: z.enum(["started", "fired", "stopped"]) }),
  z.object({ type: z.literal("task"), id: z.string(), state: z.enum(["running", "done", "needs_you", "failed"]), summary: z.string().default("") }),
  z.object({ type: z.literal("scam"), verdict: z.enum(["scam", "suspicious", "looks_ok"]), reasons: z.array(z.string()).default([]), guard: z.boolean().default(false) }),
  z.object({ type: z.literal("idle") }),
  z.object({ type: z.literal("brain_status"), provider: z.string(), model: z.string(), ready: z.boolean(), keys: z.array(z.string()), voice: z.boolean() }),
]);
export type CoreEvent = z.infer<typeof CoreEvent>;

export type UiCommand =
  | { type: "ptt_start" }
  | { type: "ptt_stop" }
  | { type: "text_command"; text: string }
  | { type: "confirm_response"; id: string; approved: boolean }
  | { type: "cancel" }
  | { type: "set_settings"; settings: Record<string, unknown> }
  | { type: "lock" }
  | { type: "undo"; turn_id?: string | null }
  | { type: "enroll_start"; name?: string; role?: "owner" | "family" | "elder" | "kid" }
  | { type: "profile_remove"; name: string }
  | { type: "enroll_cancel" }
  | { type: "skill_run"; name: string }
  | { type: "voice_setup" }
  | { type: "say_preview" };

export const UI_COMMAND_TYPES = [
  "ptt_start",
  "ptt_stop",
  "text_command",
  "confirm_response",
  "cancel",
  "set_settings",
  "lock",
  "undo",
  "enroll_start",
  "enroll_cancel",
  "skill_run",
  "voice_setup",
  "say_preview",
  "profile_remove",
] as const satisfies readonly UiCommand["type"][];
