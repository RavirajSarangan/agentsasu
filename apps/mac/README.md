# Sasu native core (Swift)

The Python core works, but shipping it means bundling a whole Python runtime (145 MB).
This package is its replacement, built **one piece at a time**. Each piece speaks the same
protocol and file formats as the Python core, and is checked against it by
`core/tests/test_swift_core.py`, so the app never breaks during the move.

| Phase | What | Status |
| --- | --- | --- |
| 1 | Local server (127.0.0.1, token, origin checks, rate limits), stdin control channel, hash-chained audit log (same SQLite file), secret redaction | ✅ done |
| 2a | Policy (paths, shell commands incl. a faithful `shlex` port), roles, trap files, leak guard, instant-command parser, undo journal | ✅ done — parity-tested on large corpora |
| 2b | All 23 tools with undo; the Executor (traps → leak guard → policy → role → approval / Touch ID → run → journal → audit); turns, undo, cancel and lock over the WebSocket | ✅ done — a 12-command script matches Python event for event |
| 3a | Speech engine: the same sherpa-onnx build as Python (PyPI, pinned); Whisper tiny/turbo, voice activity, voiceprints, wake and stop words | ✅ done — same transcripts, segments and voiceprints on the same audio |
| 3b | Listening state machine, encrypted voiceprint vault, live mic (AVAudioEngine), spoken replies (Tara/Vani, half-duplex), voice turns for owner / family / kid / guest, push-to-talk | ✅ done — spoken requests end to end with a Python-enrolled voice |
| 4 | AI brain (URLSession, OpenAI-compatible); briefing, focus, memory, meetings and the other assistants; then the app switches to this core | next |
| 5 | Optional: SwiftUI shell, App Intents / Shortcuts | |

```bash
scripts/fetch-sherpa.sh          # speech engine, pinned to the Python core's build
swift build -c release            # needs only the Xcode command-line tools
.build/release/sasu-core-swift --verify-audit ~/Library/Application\ Support/dev.sasu.desktop/audit.sqlite
cd ../../core && uv run pytest tests/test_swift_core.py
```
