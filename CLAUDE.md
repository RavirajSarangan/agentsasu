# SASU — notes for coding agents

Plan: docs/architecture.md. Work phase by phase (docs/MASTER_PROMPT.md); stop after each.

- Node: use nvm Node 24 (`.nvmrc`); the system default Node 20 breaks pnpm 10 / Vite 7.
  Rust is in `~/.cargo/bin` (may not be on PATH).
- Protocol: `core/sasu_core/protocol.py` is the source of truth. After changing it run
  `pnpm protocol:gen`, then update `apps/desktop/src/agent/protocol.ts`;
  `protocol.test.ts` fails on drift.
- Robot state is derived only in `apps/desktop/src/robot/stateMachine.ts` (pure, tested).
  Timers (settle, sleep) live in `agent/store.ts`.
- Windows load `index.html`; `main.tsx` routes by Tauri window label (`overlay` | `panel`)
  using hash history. Never put `overflow: hidden` around `<RobotHead>`.
- Core handshake: first stdout line `{"port","token"}`; `--watch-stdin` exits with the app.
  Dev spawns `uv run --project core python -m sasu_core` (`src-tauri/src/sidecar.rs`).
- Settings sync between windows via localStorage + Tauri event `robot-settings`.
- Sounds are synthesized (packages/brand). Agent cues play only in the overlay window
  (sound/player.ts) so they never double. UI tokens live in apps/desktop/src/styles/index.css.
- Security invariants: never put secrets in argv/env; unlock + auth results only via the
  Rust stdin channel (Core::control); every new tool must go through security/policy.py and
  audit.append. New Tauri commands must be added to build.rs AND a capabilities/*.json file.
- Debug builds keep the vault key in a 0600 file (Keychain re-prompts on every re-sign);
  release builds use the Keychain.
- Landing: apps/web; deployed via a copy of dist named `sasu-web` (Vercel project sasu-web).
- Brain: one OpenAI-compatible client (core/sasu_core/brain/providers.py) for Gemini/Groq/
  Anthropic/Ollama. Keys: Rust keys.rs → stdin `secret` control; never on WS, disk (release) or logs.
- Every tool call goes through brain/agent.py Executor: policy → approve → run → journal → audit.
  New tools: add to core/sasu_core/tools/*, record undo with journal.record + @inverse.
  AppleScript gets user data ONLY via argv (runtime.applescript).
- Voice: sherpa-onnx (no PyTorch) — VAD, Whisper tiny (wake) + turbo int8 (commands), wespeaker
  voiceprint. Models in <data_dir>/models, downloaded on "Turn on voice". Wake matching is
  sound-shape based (voice/wake.py) because tiny Whisper mangles "Hey Sasu".
- Tests set core.speaker.enabled=False so nothing speaks; WS handshake = ready, brain_status, voice_status.
- Swift migration (apps/mac, SwiftPM, CLT only): phase 1 = server + audit + redaction. Keep it
  byte-compatible with Python (PyJSON.dumps mirrors json.dumps(sort_keys, ensure_ascii=False);
  digest = sha256(prev|at:.6f|kind|data)). core/tests/test_swift_core.py is the parity contract.
- Mac release: scripts/release-mac.sh (PyInstaller core → Resources/sasu-core, appdmg DMG).
