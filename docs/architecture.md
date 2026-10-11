# SASU — Voice‑controlled Desktop Agent (macOS first)

## Context
Build **SASU**, an open‑source desktop agent for macOS. A small animated robot (from `robot-heads`) floats on the desktop. You say **"Hey Sasu"**, then a command in **English or Tamil (incl. Tanglish)**, and SASU uses full PC access (apps, files, shell, browser, keyboard/mouse, screen) to do it, then answers by voice. Stack: **Tauri v2 + React + TanStack + Python**. The directory `~/Downloads/agnentsasu` is an empty git repo — greenfield.

Verified `robot-heads@0.3.0` API (MIT, React ≥18, canvas, no deps):
`<RobotHead model="tv" shape state size color trimColor screenColor speed paused interactive antenna floorShadow seed aria-label ref />`
- shapes: `rectangle | square | circle | hexagon` (`robotHeadShapes`)
- states: `idle | thinking | searching | listening | speaking | working | happy | error | sleeping` (`robotHeadStates`)
- Canvas overflows its box (hops/glow) → overlay window must be larger than `size` and never `overflow:hidden` around it.

---

## 1. Architecture

```
┌──────────────────────── Tauri v2 app (Rust core) ─────────────────────────┐
│  Windows:                                                                 │
│   • overlay  – transparent, frameless, always-on-top, all Spaces, 220×260 │
│                renders <RobotHead> + caption bubble                       │
│   • panel    – normal window: chat, history, settings, permissions, logs  │
│  Rust:  sidecar lifecycle · global hotkeys · tray · autostart · keychain  │
│         macOS permission checks (AX, mic, screen) · window positioning    │
│  Plugins: shell(sidecar), global-shortcut, store, autostart, updater,     │
│           log, single-instance, positioner, notification, opener          │
└───────────────▲───────────────────────────────────────▲───────────────────┘
                │ Tauri IPC (invoke/events)              │ WebSocket ws://127.0.0.1:<port>
                │                                        │ (token auth, JSON events)
┌───────────────┴─────────────── React UI ──────────────┴───────────────────┐
│ TanStack Router (routes) · Query (REST) · Store (live agent state)        │
│ TanStack Form (settings) · Table (audit log) · Virtual (transcripts)      │
└───────────────────────────────────────────────────────────────────────────┘
                                         │
┌────────────────────── Python sidecar "sasu-core" (FastAPI) ───────────────┐
│  audio/   mic stream (sounddevice) → Silero VAD                           │
│  wake/    openWakeWord custom model "hey_sasu.onnx" (always on, local)    │
│  stt/     mlx-whisper large-v3-turbo (Apple Silicon), lang ∈ {ta,en}      │
│  brain/   agent loop: LLM provider + tool calling + memory + planner      │
│           providers: Claude (default) | Ollama (offline) | OpenAI-compat  │
│  tools/   mac_apps, applescript, shell, files, browser(Playwright),      │
│           screen(screenshot+vision), input(mouse/keyboard), system,       │
│           clipboard, calendar/reminders/notes, web_search, MCP client     │
│  safety/  risk tiers, voice/click confirmation, sandbox paths, audit log  │
│  tts/     en: Kokoro-82M · ta: Indic Parler-TTS (fallback edge-tts ta-IN) │
│  store/   SQLite (history, memory, audit), settings JSON                  │
└───────────────────────────────────────────────────────────────────────────┘
```

**Why this split:** Rust/Tauri owns windows, OS integration and process lifecycle (small, fast, signed). Python owns everything ML + automation where the ecosystem lives (whisper, wake word, TTS, pyobjc, Playwright). UI is a thin, reactive view of agent state.

### Voice pipeline (one turn)
1. `wake` detects "Hey Sasu" (score > threshold, 1.5 s cooldown) → event `wake` → robot `listening`, chime.
   Alternatives: hotkey `⌥Space` (push‑to‑talk) or clicking the robot.
2. Audio buffered until Silero VAD sees 800 ms silence (max 15 s) → robot `thinking`.
3. STT → `{text, lang: "ta"|"en", confidence}`; Tanglish handled by whisper; transcript shown in bubble.
4. Brain loop (max 12 steps): LLM chooses tools → each tool emits `tool_start/tool_end` → robot `working` (or `searching` for web/file search/screen reading).
5. Risky tool → `confirm_request` → robot `listening`, asks "Shall I delete 3 files? Say yes / ஆமா" or click ✓/✗.
6. Final answer in the user’s language → TTS streamed sentence‑by‑sentence → robot `speaking`.
7. Success → `happy` (1.2 s) → `idle`; failure → `error` (2 s) → `idle`; 5 min no activity → `sleeping` (wake word still works).

### Robot state machine (UI, TanStack Store)
| Agent event | RobotHead state | Antenna/extra |
|---|---|---|
| boot / idle | `idle` | |
| wake, confirm_request | `listening` | chime |
| stt_done, llm_thinking | `thinking` | |
| tool_start (web_search, files.find, screen.read, browser) | `searching` | |
| tool_start (others) | `working` | progress in bubble |
| tts_start | `speaking` | caption streams |
| turn_done ok | `happy` → `idle` | |
| error / denied | `error` → `idle` | |
| idle 5 min / DND | `sleeping` | DND also sets `paused` |

### Using every robot-heads feature
- **shape**: user picks skin in Settings (all 4 via `robotHeadShapes`); optional "mode shapes" — `rectangle` normal, `circle` offline/local model, `hexagon` admin/full‑access mode, `square` safe mode.
- **state**: all 9 mapped above. A "Robot Lab" panel page renders all states × shapes (`robotHeadStates`) for testing/demo.
- **color/trimColor/screenColor**: themes (Midnight Blue default, Tamil "Kumkum" red/gold, Mint, Mono, light/dark aware); `screenColor` tinted per language (cool white = EN, warm amber = TA) so you can see which language SASU heard.
- **size**: overlay sizes S/M/L (96/140/180); panel header avatar 40 px with `antenna={false}`; history list avatars 24 px with `antenna={false} floorShadow={false}` and per‑row `seed`.
- **speed**: 1.0 normal, 1.4 while `working`, 0.7 when `sleeping`/battery saver.
- **paused**: Do‑Not‑Disturb / low power / screen sharing.
- **interactive**: on in overlay (eyes follow cursor; click = push‑to‑talk, right‑click = menu, drag = move window via `data-tauri-drag-region` wrapper).
- **seed**: random per avatar instance.
- **aria-label**: `"Sasu, listening"` etc. for VoiceOver.
- **ref** (canvas): used to snapshot the robot for the tray/dock icon state and for share cards.

---

## 2. Project structure (pnpm monorepo)

```
sasu/
├─ package.json                # pnpm workspaces, root scripts
├─ pnpm-workspace.yaml
├─ README.md  LICENSE(MIT)  CONTRIBUTING.md  CLAUDE.md
├─ .github/workflows/{ci.yml,release.yml}
├─ apps/
│  └─ desktop/
│     ├─ index.html  vite.config.ts  tsconfig.json
│     ├─ src/
│     │  ├─ main.tsx                  # Router + QueryClient providers
│     │  ├─ routes/                   # TanStack Router file routes
│     │  │  ├─ __root.tsx
│     │  │  ├─ overlay.tsx            # robot window
│     │  │  ├─ panel.tsx              # layout with sidebar
│     │  │  ├─ panel.chat.tsx
│     │  │  ├─ panel.history.tsx
│     │  │  ├─ panel.settings.tsx
│     │  │  ├─ panel.permissions.tsx  # macOS permission wizard
│     │  │  ├─ panel.tools.tsx        # enable/disable tools, risk tiers
│     │  │  ├─ panel.audit.tsx        # TanStack Table
│     │  │  └─ panel.robot-lab.tsx
│     │  ├─ robot/
│     │  │  ├─ SasuRobot.tsx          # wraps <RobotHead>, all props
│     │  │  ├─ stateMachine.ts        # event → state, timers
│     │  │  ├─ themes.ts
│     │  │  └─ Bubble.tsx             # caption / confirm buttons
│     │  ├─ agent/
│     │  │  ├─ socket.ts              # WS client, reconnect, token
│     │  │  ├─ protocol.ts            # zod schemas (mirror of python)
│     │  │  └─ store.ts               # TanStack Store
│     │  ├─ api/                      # TanStack Query hooks (REST)
│     │  ├─ i18n/{en.json,ta.json}
│     │  └─ styles/
│     └─ src-tauri/
│        ├─ Cargo.toml  tauri.conf.json  Info.plist  Entitlements.plist
│        ├─ capabilities/{overlay.json,panel.json}
│        ├─ binaries/sasu-core-aarch64-apple-darwin   # built sidecar
│        └─ src/
│           ├─ main.rs  lib.rs
│           ├─ sidecar.rs      # spawn/restart python, port+token handshake
│           ├─ windows.rs      # overlay/panel creation, positioning
│           ├─ hotkeys.rs  tray.rs
│           ├─ permissions.rs  # AXIsProcessTrusted, mic, CGPreflightScreenCaptureAccess
│           └─ secrets.rs      # keychain (API keys)
├─ core/                        # Python sidecar (uv project)
│  ├─ pyproject.toml  uv.lock
│  ├─ sasu_core/
│  │  ├─ __main__.py            # prints {"port","token"} on stdout → Rust
│  │  ├─ server.py              # FastAPI: /ws, /api/*
│  │  ├─ protocol.py            # pydantic event models (single source)
│  │  ├─ config.py
│  │  ├─ audio/{mic.py,vad.py}
│  │  ├─ wake/{detector.py,models/hey_sasu.onnx}
│  │  ├─ stt/{whisper_mlx.py,base.py}
│  │  ├─ tts/{kokoro_en.py,parler_ta.py,edge_fallback.py,base.py}
│  │  ├─ brain/
│  │  │  ├─ agent.py            # loop, step limit, cancellation
│  │  │  ├─ prompts.py          # system prompt (bilingual persona)
│  │  │  ├─ memory.py           # SQLite + simple facts store
│  │  │  └─ providers/{claude.py,ollama.py,openai_compat.py,base.py}
│  │  ├─ tools/
│  │  │  ├─ registry.py         # @tool decorator, JSON schema, risk tier
│  │  │  ├─ apps.py  applescript.py  shell.py  files.py
│  │  │  ├─ browser.py  screen.py  input.py  system.py
│  │  │  ├─ clipboard.py  productivity.py  web.py  mcp_client.py
│  │  ├─ safety/{policy.py,confirm.py,audit.py}
│  │  └─ store/db.py
│  ├─ tests/
│  └─ build_sidecar.py          # PyInstaller → src-tauri/binaries/
├─ packages/
│  └─ protocol/                 # generated TS types from pydantic JSON schema
└─ tools/wakeword/              # notebook + script to train hey_sasu.onnx
```

---

## 3. Key contracts

**WS events (python → UI):** `ready`, `wake`, `listening`, `partial_transcript{text}`, `transcript{text,lang}`, `thinking`, `tool_start{id,name,args,risk}`, `tool_end{id,ok,summary}`, `confirm_request{id,prompt,lang,risk}`, `say_start{text,lang}`, `say_chunk`, `say_end`, `turn_done{ok}`, `error{code,message}`, `sleep`.
**UI → python:** `ptt_start`, `ptt_stop`, `text_command{text}`, `confirm_response{id,approved}`, `cancel`, `set_settings{...}`.
Pydantic is the source of truth → `packages/protocol` TS generated with `datamodel-code-generator`/`json-schema-to-zod` in CI.

**Tool risk tiers (safety/policy.py):**
- `safe` (auto): open app, volume, brightness, read clipboard, web search, screenshot, list files, time/weather.
- `confirm` (voice/click yes): write/move files, send messages/email, type into apps, run shell commands from allowlist, browser form submit, quit apps.
- `dangerous` (always confirm + show full command, never by voice alone): `rm`, `sudo`, arbitrary shell, system settings, purchases, anything outside `~`.
- Global kill switch `⌘⌥Esc` cancels the turn and all running tools. Every tool call written to `audit` table.

**Permissions (Info.plist + wizard):** `NSMicrophoneUsageDescription`, `NSAppleEventsUsageDescription`, Accessibility (input control), Screen Recording (screen reading), optional Full Disk Access, Calendars/Reminders. Wizard checks each via Rust and deep‑links to System Settings panes.

**Tauri overlay config:** `transparent: true, decorations: false, alwaysOnTop: true, visibleOnAllWorkspaces: true, skipTaskbar: true, shadow: false, resizable: false`, `app.macOSPrivateApi: true`, `ActivationPolicy::Accessory` (no Dock icon; tray only).

**LLM default:** Claude via Anthropic SDK with tool use — `claude-sonnet-5-5` for normal turns (fast), escalate to `claude-opus-5-5` for multi‑step planning; `ollama` (e.g. Qwen3) for offline/private mode. API key stored in macOS Keychain, never in files.

---

## 4. Development workflow (phases)

| Phase | Goal | Done when |
|---|---|---|
| 0. Spike (1–2 d) | Verify: Tauri transparent overlay + RobotHead; mlx-whisper Tamil accuracy; Tamil TTS quality; openWakeWord on mac mic | Each spike has a script + note in `docs/spikes.md` |
| 1. Skeleton | Monorepo, Tauri app with 2 windows, Python FastAPI sidecar spawned by Rust, WS handshake, robot cycles states from fake events | `pnpm dev` shows robot reacting to `python -m sasu_core --demo` |
| 2. Voice I/O | Mic + VAD + push‑to‑talk + STT + TTS (en/ta) echo bot | Say something in Tamil → robot repeats it in Tamil |
| 3. Brain | Provider abstraction, agent loop, 5 safe tools (apps, system, web search, files list, clipboard) | "Open Safari", "volume 30", "Spotify open pannu" work |
| 4. Wake word | Train `hey_sasu.onnx` (synthetic Piper samples + own recordings, en+ta accents), tune threshold, false‑wake test | <1 false wake/hr on 1 h of background audio, >90% hit rate |
| 5. Full access + safety | shell, files write, browser (Playwright), screen+vision, input, productivity; confirm flow, audit, kill switch | Risky actions always ask; audit table shows all calls |
| 6. Panel UI | Chat, history (Virtual), settings (Form), tools, audit (Table), permissions wizard, robot lab, themes, i18n | All routes functional, settings persisted |
| 7. Memory & polish | User facts, recent context, streaming TTS, interruption ("Sasu stop"), DND, sleep, battery saver | Barge‑in works; idle CPU < 3% |
| 8. Ship | PyInstaller sidecar, signed + notarized `.dmg`, updater, GitHub Releases, docs | Fresh Mac installs, grants perms, works offline with Ollama |

Daily loop: `pnpm dev` (Vite + Tauri) with `uv run python -m sasu_core --dev` started by Rust in dev (plain python, hot reload) and the PyInstaller binary only in builds. Tests: `pytest` (tools with mocked osascript, agent loop with fake provider), `vitest` (state machine, protocol), Playwright‑for‑Tauri smoke later. CI: lint (ruff, mypy, eslint, tsc, clippy) + tests on `macos-14`.

---

## 5. Deployment
- Sidecar: `uv run python build_sidecar.py` → PyInstaller `--onedir` (models downloaded on first run to `~/Library/Application Support/Sasu/models`, not bundled — keeps dmg small).
- Tauri `bundle.externalBin: ["binaries/sasu-core"]`, `bundle.macOS.entitlements`, hardened runtime, `signingIdentity` (Developer ID), notarize with `APPLE_ID/APPLE_PASSWORD/APPLE_TEAM_ID` in `release.yml`.
- `tauri-plugin-updater` with signed `latest.json` on GitHub Releases.
- Without a paid Apple dev account: ship unsigned dev builds, document `xattr -cr`.

---

## 6. Master prompt (paste into Claude Code / Antigravity)

```
You are building SASU, an open-source (MIT) voice-controlled desktop agent for macOS (Apple Silicon first).

PRODUCT
- A small animated robot floats on the desktop (transparent always-on-top Tauri window) using the npm
  package `robot-heads@0.3.0` (<RobotHead shape state size color trimColor screenColor speed paused
  interactive antenna floorShadow seed aria-label ref/>; shapes rectangle|square|circle|hexagon;
  states idle|thinking|searching|listening|speaking|working|happy|error|sleeping). Its canvas
  overflows its box, so never clip it.
- User says "Hey Sasu" (or presses ⌥Space, or clicks the robot), then speaks English, Tamil or
  Tanglish. SASU transcribes, plans with an LLM, uses tools with full Mac access, and replies by
  voice in the same language the user used.

STACK (do not substitute)
- Tauri v2 (Rust) shell: windows `overlay` + `panel`, tray, global shortcuts, autostart, keychain,
  permission checks, spawns/restarts the Python sidecar. Plugins: shell, global-shortcut, store,
  autostart, updater, log, single-instance, positioner, notification, opener.
- React 18 + TypeScript + Vite; TanStack Router (file routes), Query, Store, Form, Table, Virtual;
  zod for protocol validation; Tailwind for styles.
- Python 3.12 sidecar managed with uv: FastAPI + websockets, sounddevice, silero-vad,
  openwakeword (custom hey_sasu.onnx), mlx-whisper (large-v3-turbo), Kokoro (EN TTS),
  Indic Parler-TTS (TA TTS) with edge-tts fallback, anthropic SDK (default provider,
  claude-sonnet-5-5, escalate to claude-opus-5-5), ollama provider for offline, pyobjc,
  Playwright, mss, SQLite.
- pnpm monorepo: apps/desktop, core, packages/protocol, tools/wakeword.

ARCHITECTURE RULES
1. Python pydantic models in core/sasu_core/protocol.py are the single source of truth for WS
   events; generate TS types/zod into packages/protocol. Never hand-edit generated files.
2. Sidecar binds 127.0.0.1 on a random port and prints {"port","token"} as the first stdout line;
   Rust reads it and passes it to the UI. Every WS/REST call requires the token.
3. UI is a pure view of agent state: robot state is derived in robot/stateMachine.ts from events
   (mapping table in docs/architecture.md). No business logic in components.
4. Every tool is registered with @tool(name, schema, risk="safe"|"confirm"|"dangerous").
   confirm/dangerous tools must go through safety/confirm.py (voice yes/ஆமா/no/வேண்டாம் or click).
   dangerous ones require a click and show the exact command. Every call is audited.
5. ⌘⌥Esc and saying "Sasu stop / நிறுத்து" cancel the turn and all running tools.
6. Secrets only in macOS Keychain via Rust. Nothing sensitive in logs.
7. Everything works offline with the ollama provider (degraded quality is fine).

WORK IN PHASES. Do one phase at a time, end each with passing tests, a short demo script,
and a commit. Stop and ask me before moving to the next phase.
  0 Spikes: overlay+RobotHead, mlx-whisper Tamil, Tamil TTS, openWakeWord. Write docs/spikes.md.
  1 Skeleton: monorepo, two windows, sidecar handshake, `--demo` mode cycling all 9 states.
  2 Voice I/O: mic, VAD, push-to-talk, STT, TTS echo in en+ta.
  3 Brain: provider abstraction, agent loop (max 12 steps, cancellable), tools: apps, system,
    web_search, files.list, clipboard.
  4 Wake word: training script in tools/wakeword, detector with cooldown and threshold setting.
  5 Full access + safety: shell, files write, browser, screen+vision, input, calendar/reminders/
    notes, MCP client; confirm flow, audit log, kill switch.
  6 Panel: chat, history, settings, tools, audit, permissions wizard, robot lab (all shapes ×
    states), themes, en/ta i18n.
  7 Memory, barge-in, DND (paused), sleep, battery saver, idle CPU < 3%.
  8 Ship: PyInstaller sidecar to src-tauri/binaries, signed+notarized dmg, updater, CI release.

QUALITY BAR
- ruff + mypy strict, eslint + tsc strict, cargo clippy -D warnings, pytest, vitest.
- Mock osascript/subprocess in tool tests; fake LLM provider for agent tests.
- Keep files small and focused; follow the folder structure in docs/architecture.md exactly.
Start with Phase 0. First create docs/architecture.md from this prompt, then the spikes.
```

---

## 7. Verification (end‑to‑end)
1. `pnpm dev` → robot appears bottom‑right on all Spaces, transparent, eyes follow cursor.
2. `--demo` mode → robot cycles all 9 states; Robot Lab shows 4 shapes × 9 states.
3. Say "Hey Sasu, open Safari" → listening → thinking → working → speaking → happy; Safari opens.
4. Say "Hey Sasu, Downloads la irukura PDF ellam list pannu" → Tamil reply listing files.
5. Say "Delete those files" → confirm prompt; "வேண்டாம்" cancels; audit shows denied.
6. Press ⌘⌥Esc mid‑task → turn cancelled, robot `error` → `idle`.
7. Turn off Wi‑Fi, switch to Ollama → simple commands still work.
8. Build `.dmg`, install on a clean user account, run permission wizard, repeat 3–5.
