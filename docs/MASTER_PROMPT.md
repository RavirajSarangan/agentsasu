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
