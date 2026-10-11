# SASU

Open-source voice desktop agent for macOS. A small robot floats on your desktop; say
**"Hey Sasu"** and a command in English or Tamil, and it does it on your Mac.

> **v0.3** — hands-free voice in English, தமிழ் and Tanglish ("Hey Sasu" → instant local
> commands in ~1.5 s, AI for everything else), girl/boy voices, undo for every action,
> owner-only voiceprint + guest mode, trap files, leak guard, panic word, away lock,
> intruder log, music dancing and more. Site: <https://sasu-web.vercel.app>

## Requirements
- macOS 13+, Apple Silicon
- Node 22+ (`nvm use` reads `.nvmrc`), pnpm 10
- Rust (stable), [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 itself)

## Run
```bash
pnpm install
cd core && uv sync && cd ..

pnpm dev                 # the app (Tauri + Vite + Python core)
SASU_DEMO=1 pnpm dev     # same, robot cycles through scripted turns
```
UI only, in a browser: `pnpm core:demo` in one terminal, `pnpm dev:ui` in another, then open
<http://localhost:1420/#/overlay> or `#/panel`.

| Action | How |
|---|---|
| Talk | click the robot, or ⌥Space |
| Stop everything | ⌘⌥Esc |
| Move the robot | drag it |
| Open the panel | double-click / right-click the robot, or the tray icon |

Landing site: `pnpm web` → <http://localhost:5173>. Brand assets (DMG background, OG
image, favicons) are rendered from it with `pnpm assets` while it runs.

## First run
1. Settings → **AI brain**: paste a free key from <https://aistudio.google.com/apikey>
   (stored in the Keychain; release builds) — or pick Ollama for offline.
2. Settings → **Voice** → *Turn on voice* (one-time ~700 MB download), then *Enrol my voice*.
3. Say “Hey Sasu, open Safari”. Try “Sasu, undo”, “Sasu, save that as morning”.

Just say **“Hey Sasu”** (or “சாசு”). Instant: “play some music”, “paattu podu”, “volume 30”,
“சத்தம் குறை”, “Safari open pannu”, “what's the time”. Anything else goes to the AI.
After Sasu answers it keeps listening a few seconds for a follow-up — no wake word needed.

Hotkeys (optional): ⌥Space talk · ⌘⌥Z undo · ⌘⌥Esc stop everything.

## Security model (short)
- Core listens on 127.0.0.1 only; a fresh 256-bit token per launch is passed on **stdin**
  (never argv/env). WebSocket checks token + Origin and rate-limits.
- The **stdin channel is trusted**: only the Rust shell can unlock Sasu or report Touch ID
  results. Web windows can lock, never unlock.
- Risk tiers: safe → confirm (owner yes) → dangerous (Touch ID). Policy denies `sudo`,
  `curl | sh`, `~/.ssh`, Keychains, `/System`…
- Screen lock / screensaver locks the core. ⌘⌥Esc kills the running turn from Rust.
- Every decision goes to an append-only, hash-chained SQLite log (0600), visible on the
  Security page. Voiceprint (Phase 2) is AES-GCM encrypted, key in the Keychain.
- Strict CSP, per-window command allowlists (`src-tauri/capabilities`), frozen prototypes.

## Layout
```
apps/desktop/          React + TanStack UI, src-tauri/ = Rust shell
apps/web/              landing site (Vite + motion), DMG/OG asset pages
core/                  Python sidecar (FastAPI, later voice + brain + tools)
packages/protocol/     schema.json generated from core/sasu_core/protocol.py
packages/brand/        robot themes + synthesized sound kit (app and site share it)
docs/                  architecture plan + master prompt
```

## Checks
```bash
pnpm test                                   # vitest + pytest
pnpm typecheck
cd core && uv run ruff check . && uv run mypy
cd apps/desktop/src-tauri && cargo clippy --all-targets -- -D warnings && cargo test
```

## License
MIT. Robot by [robot-heads](https://github.com/fayazara/robot-heads) (MIT).
